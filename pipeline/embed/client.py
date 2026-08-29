"""Embeddings client — provider-routed (§7.2).

A "gemini/" model prefix routes to Google's generativelanguage batchEmbedContents
endpoint; anything else goes to OpenRouter's OpenAI-compatible /embeddings.

The two APIs have different request/response SHAPES, not just different URLs —
Gemini takes a `requests[]` array of per-item content objects and returns
`embeddings[]` in input order, while OpenAI-compatible takes `input[]` and returns
`data[]` carrying an explicit `index` that may be reordered. Both are normalised
here to "list of vectors in input order" so nothing downstream knows the difference.

Both paths return 3072-dim vectors (verified live 2026-08-27), so the provider can
be switched without changing the geometry the clusterer sees — though switching
still invalidates the cached vectors and the taxonomy fingerprint, by design.
"""
from __future__ import annotations

import logging
import time

import requests

from .. import config

log = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 529}


def _gemini_request(texts: list[str], model: str, timeout: float):
    """Google batchEmbedContents. Returns vectors already in input order."""
    name = model[len(config.GEMINI_PREFIX):]
    url = f"{config.GEMINI_EMBED_BASE}/models/{name}:batchEmbedContents"
    payload = {"requests": [{"model": f"models/{name}",
                             "content": {"parts": [{"text": t}]}} for t in texts]}
    return requests.post(url, params={"key": config.GEMINI_API_KEY},
                         json=payload, timeout=timeout)


def _openrouter_request(texts: list[str], model: str, timeout: float):
    return requests.post(
        config.OPENROUTER_EMBED_URL,
        headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": model, "input": texts}, timeout=timeout)


def _retry_after(resp) -> float | None:
    """Seconds the provider explicitly asked us to wait, if it said so."""
    try:
        for d in resp.json().get("error", {}).get("details", []):
            if d.get("@type", "").endswith("RetryInfo"):
                return float(str(d.get("retryDelay", "0s")).rstrip("s")) + 1.0
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _parse(resp, is_gemini: bool) -> list[list[float]]:
    if is_gemini:
        # Gemini preserves request order and carries no index field.
        return [e["values"] for e in resp.json()["embeddings"]]
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])       # OpenAI-compatible may reorder
    return [d["embedding"] for d in data]


def embed_batch(texts: list[str], model: str | None = None, *,
                max_retries: int = 5, timeout: float = 120) -> list[list[float]]:
    """Embed a batch of texts, preserving input order. Raises on hard failure.

    `max_retries`/`timeout` are tunable so the live-run path can fail fast (one short
    attempt) while the offline pipeline keeps the full retry budget.
    """
    model = model or config.EMBEDDING_MODEL
    is_gemini = model.startswith(config.GEMINI_PREFIX)
    if is_gemini and not config.GEMINI_API_KEY:
        raise RuntimeError(f"GEMINI_API_KEY not set — cannot embed with {model!r}")
    if not is_gemini and not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set — cannot embed (§7.2)")

    delay = 2.0
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            resp = (_gemini_request(texts, model, timeout) if is_gemini
                    else _openrouter_request(texts, model, timeout))
        except requests.RequestException as e:
            last_err = str(e)
            log.warning("embeddings network error (try %d/%d): %s", attempt, max_retries, e)
            time.sleep(delay); delay *= 2; continue

        if resp.status_code == 200:
            return _parse(resp, is_gemini)

        if resp.status_code in _RETRY_STATUS:
            last_err = f"HTTP {resp.status_code}"
            # Gemini's free embed quota is per-MINUTE and the 429 body carries the exact
            # RetryInfo.retryDelay. Honour it: blind exponential doubling either sleeps
            # far too long or retries before the window resets and burns an attempt.
            wait = _retry_after(resp) or delay
            log.warning("embeddings %s (try %d/%d) — waiting %.1fs",
                        last_err, attempt, max_retries, wait)
            time.sleep(wait)
            delay = min(delay * 2, 120)
            continue

        # Log the provider body server-side, but never surface it to the client (it can
        # echo request detail). The raised message carries only the status code.
        log.error("embeddings HTTP %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"embeddings HTTP {resp.status_code}")

    raise RuntimeError(f"embeddings failed after {max_retries} retries ({last_err})")
