"""Cluster-naming call — provider-routed (§7.4).

Pinned config.LLM_MODEL, resolved through config.resolve_llm() so a "groq/" prefix
goes to Groq and anything else to OpenRouter. Exponential backoff on transient
errors; on hard failure falls back to config.LLM_FALLBACK_MODEL and records which
model produced the output, so provenance is auditable. Strict-JSON output with one
repair retry on parse failure. Pre-flight token estimate + hard max_tokens_per_run.
"""
from __future__ import annotations

import json
import logging
import re
import time

import requests

from .. import config

log = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 529}


class TokenBudget:
    """Tracks estimated token spend against MAX_TOKENS_PER_RUN (§7.4)."""

    def __init__(self, max_tokens: int | None = None):
        self.max_tokens = max_tokens or config.MAX_TOKENS_PER_RUN
        self.used = 0

    def estimate_messages(self, messages: list[dict]) -> int:
        text = " ".join(m.get("content", "") for m in messages)
        return max(1, len(text) // 4)

    def charge(self, n: int) -> None:
        self.used += n
        if self.used > self.max_tokens:
            raise RuntimeError(
                f"MAX_TOKENS_PER_RUN exceeded ({self.used}/{self.max_tokens}) — aborting (§7.4)"
            )


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return json.loads(content)


def _post(messages, model, max_tokens):
    url, api_key, provider_model = config.resolve_llm(model)
    if not api_key:
        raise RuntimeError(
            f"no API key for {model!r} — set "
            f"{'GROQ_API_KEY' if model.startswith(config.GROQ_PREFIX) else 'OPENROUTER_API_KEY'}"
        )
    payload = {"model": provider_model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 0}
    # Open-weight models are markedly less reliable than Claude at "reply with JSON and
    # nothing else". Both providers speak the OpenAI json_object mode, so ask for it
    # explicitly rather than relying on the prompt alone and repairing after the fact.
    payload["response_format"] = {"type": "json_object"}
    return requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, timeout=120,
    )


def name_cluster(messages: list[dict], max_tokens: int = 1024,
                 budget: TokenBudget | None = None) -> dict:
    """Return the parsed theme dict with `_model_used`. Tries the pinned model,
    then the degraded fallback."""
    _, _key, _ = config.resolve_llm(config.LLM_MODEL)
    if not _key:
        raise RuntimeError(f"no API key configured for LLM_MODEL={config.LLM_MODEL!r}")

    est = (budget.estimate_messages(messages) + max_tokens) if budget else 0
    if budget:
        budget.charge(est)

    for model in (config.LLM_MODEL, config.LLM_FALLBACK_MODEL):
        delay = 2.0
        for attempt in range(1, 4):
            try:
                resp = _post(messages, model, max_tokens)
            except requests.RequestException as e:
                log.warning("%s network error (try %d): %s", model, attempt, e)
                time.sleep(delay); delay *= 2; continue

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                try:
                    data = _parse_json(content)
                except json.JSONDecodeError:
                    log.warning("%s returned non-JSON (try %d); retrying", model, attempt)
                    time.sleep(1); continue
                data.setdefault("theme_name", "")
                data.setdefault("summary", "")
                data.setdefault("quotes", [])
                data.setdefault("per_app_observation", "")
                data["_model_used"] = model
                return data

            if resp.status_code in _RETRY_STATUS:
                log.warning("%s HTTP %d (try %d) — backoff %.1fs", model, resp.status_code, attempt, delay)
                time.sleep(delay); delay *= 2; continue

            log.warning("%s HTTP %d: %s — trying fallback", model, resp.status_code, resp.text[:150])
            break  # non-retryable -> next model

        if model != config.LLM_FALLBACK_MODEL:
            log.warning("falling back from %s to %s", model, config.LLM_FALLBACK_MODEL)

    raise RuntimeError("cluster naming failed on both primary and fallback models")
