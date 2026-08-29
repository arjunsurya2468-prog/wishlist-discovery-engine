"""Bounded live run.

Fetch latest ~config.LIVE_RUN_FETCH records for the chosen app -> normalize/PII/flag
via SHARED pipeline code -> embed -> assign each to nearest LOCKED cluster -> return
the delta. NEVER re-clusters (full re-clustering is offline-only).

STEP 7 — BOOT GATE. assert_taxonomy_ready() must pass before this module will serve
anything. It is called at application startup (main.py lifespan) so a mismatched
taxonomy kills the deploy immediately and visibly, and again lazily in _get_taxonomy()
so no code path can reach assignment around it.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np

from pipeline import config
from pipeline.cluster import fingerprint as fp
from pipeline.embed.client import embed_batch
from pipeline.ingest.normalize import normalize_corpus
from pipeline.ingest.scrapers import play_store, raw_record

from . import taxonomy as tax

log = logging.getLogger(__name__)

# Lazy-loaded taxonomy (load once, reuse)
_taxonomy_cache = None

# Shipped cached-review samples — the fallback when a live scrape is blocked from
# the deployed host's datacenter IP (Play Store rate-limits cloud IPs). Honestly
# labelled "cached" downstream; never presented as fresh.
_FALLBACK_DIR = Path(__file__).resolve().parent.parent / "static" / "live_fallback"


def assert_taxonomy_ready() -> dict:
    """STEP 7 HARD GATE — refuse to boot on a taxonomy from the wrong corpus.

    Call this at application startup. It raises TaxonomyFingerprintError (a
    RuntimeError) if the shipped taxonomy carries no corpus fingerprint, or carries one
    that does not describe this deployment's corpus.

    This is deliberately fail-closed. A taxonomy trained on another corpus does not
    error at assignment time — it silently returns a nearest centroid for every input
    and the dashboard fills with plausible, wrong themes. There is no downstream check
    that would catch it, and no user-visible symptom. So the check happens once, at the
    only moment where failing is cheap: before the port binds.

    Returns the verified fingerprint dict (for /healthz to report).
    """
    labels_path = config.TAXONOMY_DIR / "centroid_labels.json"
    if not labels_path.exists():
        raise fp.TaxonomyFingerprintError(
            f"No taxonomy present at {config.TAXONOMY_DIR}. Refusing to boot.\n"
            "  Build the taxonomy from the current corpus before deploying."
        )
    corpus_fp, _labels = fp.read_from_labels(labels_path)
    warnings = fp.verify(corpus_fp)          # raises on mismatch
    for w in warnings:
        log.warning("[taxonomy-gate] %s", w)
    log.info(
        "[taxonomy-gate] OK — domain=%s apps=%s corpus_hash=%s n=%s",
        corpus_fp.get("domain"), corpus_fp.get("apps"),
        corpus_fp.get("corpus_hash"), corpus_fp.get("n_records"),
    )
    return corpus_fp


def _get_taxonomy():
    """Load the locked taxonomy, verifying the fingerprint on first use.

    The startup gate should already have failed the boot for a bad taxonomy; this
    second check means no import order or test harness can route around it.
    """
    global _taxonomy_cache
    if _taxonomy_cache is None:
        _taxonomy_cache = tax.load_taxonomy(verify=True)
    return _taxonomy_cache


def _load_fallback(app_key: str, n: int) -> list[dict]:
    """Load up to n shipped cached reviews for the app (empty list if unavailable)."""
    path = _FALLBACK_DIR / f"{app_key}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data[:n] if isinstance(data, list) else []


def _fetch_recent(app_key: str, n: int) -> tuple[list[dict], str]:
    """Fetch ~n newest Play Store records. Returns (records, source).

    source == "live" when the scrape returned reviews; "cached" when the live scrape
    was empty or raised (datacenter-IP block on the deployed host) and we fell back to
    the shipped sample so the panel stays meaningful instead of dead.
    """
    spec = config.APPS.get(app_key)
    if not spec:
        raise ValueError(f"Unknown app: {app_key}")
    try:
        raw = play_store.scrape(spec, target=n)
    except Exception as e:  # network/library error from a blocked cloud IP
        log.warning("[live-run:%s] live scrape raised (%s) — trying cached sample", app_key, e)
        raw = []
    raw = raw[:n]  # A8: match the "~%d" copy — the scraper overshoots by batch
    if raw:
        log.info("[live-run:%s] fetched %d live reviews", app_key, len(raw))
        return raw, "live"
    fallback = _load_fallback(app_key, n)
    log.warning("[live-run:%s] live scrape empty — using %d cached reviews", app_key, len(fallback))
    return fallback, "cached"


def run(app: str) -> dict:
    """Execute a bounded live run for the given app. Returns delta dict."""
    if app not in config.APPS:
        raise ValueError(f"Unknown app: {app!r}. Choose from: {list(config.APPS)}")

    # 1. Fetch recent reviews (live, or shipped cached sample if the scrape is blocked)
    raw, source = _fetch_recent(app, config.LIVE_RUN_FETCH)
    fetched = len(raw)
    if not raw:
        return {
            "app": app, "fetched": 0, "usable": 0,
            "per_cluster_delta": [], "new_noise_count": 0,
            "model_used": config.EMBEDDING_MODEL, "source": source,
            "message": "No reviews available — try again later",
        }

    # 2. Normalize via shared pipeline code (PII scrub, word floor, etc.)
    reviews, stats = normalize_corpus(app, raw)
    usable = len(reviews)
    log.info("[live-run:%s] %d usable after normalization (from %d, source=%s)", app, usable, fetched, source)
    if not usable:
        return {
            "app": app, "fetched": fetched, "usable": 0,
            "per_cluster_delta": [], "new_noise_count": 0,
            "model_used": config.EMBEDDING_MODEL, "source": source,
            "message": "All reviews filtered during normalization",
        }

    # 3. Embed via shared pipeline code. Live path fails fast (one attempt, short
    #    timeout) so a provider outage returns a contained error, not a multi-minute
    #    hang — the endpoint also bounds total run time (main.py). Offline pipeline
    #    keeps the full 5×/120s retry budget.
    texts = [r.text for r in reviews]
    embeddings = embed_batch(texts, max_retries=1, timeout=config.LIVE_RUN_EMBED_TIMEOUT_SEC)
    emb_matrix = np.array(embeddings, dtype=np.float32)

    # 4. Assign to locked taxonomy (NEVER re-cluster)
    taxonomy = _get_taxonomy()
    centroids, labels, threshold = taxonomy
    assigned_labels, distances = tax._assign.assign(emb_matrix, centroids, labels, threshold=threshold)

    # 5. Build per-cluster delta
    cluster_counts: Counter = Counter()
    noise_count = 0
    for lab in assigned_labels:
        lab = int(lab)
        if lab == -1:
            noise_count += 1
        else:
            cluster_counts[lab] += 1

    per_cluster_delta = sorted(
        [{"cluster_id": cid, "new_reviews": cnt} for cid, cnt in cluster_counts.items()],
        key=lambda x: -x["new_reviews"],
    )

    result = {
        "app": app,
        "fetched": fetched,
        "usable": usable,
        "per_cluster_delta": per_cluster_delta,
        "new_noise_count": noise_count,
        "model_used": config.EMBEDDING_MODEL,
        "source": source,
        "top_clusters": per_cluster_delta[:10],
    }
    log.info("[live-run:%s] done: %d usable → %d assigned, %d noise",
             app, usable, sum(cluster_counts.values()), noise_count)
    return result
