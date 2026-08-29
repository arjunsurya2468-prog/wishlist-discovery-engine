"""Embedding cache — P2 (§7.2). The mandate: clustering is tuned many times, so
re-clustering must NEVER re-embed.

Keyed by sha256(scrubbed_text + model_id). Stored per model as a float32 matrix
(`vectors.npy`) plus a parallel `hashes.json` (row i <-> hash i). A run embeds
only the texts whose hash is missing, appends them, and persists.
"""
from __future__ import annotations

import hashlib
import json
import logging

import numpy as np

from .. import config
from . import client

log = logging.getLogger(__name__)

# Flush cached vectors to disk every N batches (see get_embeddings).
CHECKPOINT_EVERY = 10


def _slug(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def _dir(model: str):
    d = config.EMBED_DIR / _slug(model)
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{text}\x00{model}".encode("utf-8")).hexdigest()


def _load(model: str):
    d = _dir(model)
    hp, vp = d / "hashes.json", d / "vectors.npy"
    if hp.exists() and vp.exists():
        hashes = json.loads(hp.read_text(encoding="utf-8"))
        return hashes, np.load(vp)
    return [], None


def _save(model: str, hashes: list[str], vecs: np.ndarray) -> None:
    d = _dir(model)
    (d / "hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
    np.save(d / "vectors.npy", vecs)


def get_embeddings(texts: list[str], model: str | None = None,
                   batch_size: int | None = None) -> np.ndarray:
    """Return an [N, D] float32 matrix aligned to `texts`. Embeds only cache
    misses; a fully-cached corpus makes zero API calls."""
    model = model or config.EMBEDDING_MODEL
    batch_size = batch_size or config.EMBED_BATCH_SIZE

    hashes, vecs = _load(model)
    idx = {h: i for i, h in enumerate(hashes)}
    keys = [cache_key(t, model) for t in texts]

    missing: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, key in zip(texts, keys):
        if key not in idx and key not in seen:
            seen.add(key)
            missing.append((key, text))

    if missing:
        log.info("embedding %d new texts (%d already cached) via %s",
                 len(missing), len(idx), model)
        # CHECKPOINTED. On a rate-limited free tier a full pass can take hours; saving
        # only at the end means one failure at batch 130 of 136 discards everything and
        # the quota spent on it. Flushing every CHECKPOINT_EVERY batches makes the run
        # resumable — a re-run embeds only what is still missing.
        new_vecs: list[list[float]] = []
        done_keys: list[str] = []
        since_flush = 0

        def _flush(v, h, nv, dk):
            if not nv:
                return v, h
            arr = np.asarray(nv, dtype=np.float32)
            v = arr if v is None else np.vstack([v, arr])
            h = h + dk
            _save(model, h, v)
            log.info("  checkpoint: %d vectors persisted", len(h))
            return v, h

        for i in range(0, len(missing), batch_size):
            chunk = missing[i:i + batch_size]
            try:
                new_vecs.extend(client.embed_batch([t for _, t in chunk], model))
            except Exception:
                vecs, hashes = _flush(vecs, hashes, new_vecs, done_keys)
                log.error("  embedding aborted at %d/%d — progress checkpointed, "
                          "re-run to resume", len(done_keys), len(missing))
                raise
            done_keys.extend(k for k, _ in chunk)
            since_flush += 1
            log.info("  embedded %d/%d", min(i + batch_size, len(missing)), len(missing))
            if since_flush >= CHECKPOINT_EVERY:
                vecs, hashes = _flush(vecs, hashes, new_vecs, done_keys)
                new_vecs, done_keys, since_flush = [], [], 0

        vecs, hashes = _flush(vecs, hashes, new_vecs, done_keys)
        idx = {h: i for i, h in enumerate(hashes)}
    else:
        log.info("all %d embeddings served from cache (%s)", len(texts), model)

    return np.asarray([vecs[idx[k]] for k in keys], dtype=np.float32)
