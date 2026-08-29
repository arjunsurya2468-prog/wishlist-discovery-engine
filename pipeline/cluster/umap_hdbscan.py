"""UMAP -> HDBSCAN clustering — P2 (§7.3).

Unsupervised: no taxonomy imposed, themes emerge from density. This is the
structural answer to confirmation bias (§5) — the relevance flag is invisible
here, clustering sees everything. random_state=42 makes runs reproducible (§8).
Persists the fitted reducer + clusterer + centroids as the LOCKED taxonomy the
P5 live run assigns against.
"""
from __future__ import annotations

import json
import logging

import joblib
import numpy as np
from hdbscan import HDBSCAN
from umap import UMAP

from .. import config

log = logging.getLogger(__name__)


def _fit(embeddings: np.ndarray, umap_params: dict, hdbscan_params: dict):
    reducer = UMAP(**umap_params)
    reduced = reducer.fit_transform(embeddings)
    clusterer = HDBSCAN(prediction_data=True, **hdbscan_params)
    labels = clusterer.fit_predict(reduced)
    return labels, reduced, reducer, clusterer


def noise_fraction(labels: np.ndarray) -> float:
    labels = np.asarray(labels)
    return float((labels == -1).mean()) if labels.size else 1.0


def cluster(embeddings: np.ndarray):
    """Fit with the configured params, with a single all-noise fallback:
    if noise fraction exceeds the threshold, retry once with a lower
    min_cluster_size (edge-cases §3). Returns (labels, reduced, reducer, clusterer)."""
    labels, reduced, reducer, clusterer = _fit(
        embeddings, dict(config.UMAP_PARAMS), dict(config.HDBSCAN_PARAMS))
    nf = noise_fraction(labels)
    log.info("clustered %d points: %d clusters, noise %.1f%%",
             len(labels), len(set(labels.tolist()) - {-1}), 100 * nf)

    if nf > config.NOISE_RETRY_THRESHOLD:
        lowered = max(2, config.HDBSCAN_PARAMS["min_cluster_size"] // 2)
        log.warning("noise %.1f%% > %.0f%% — retrying once with min_cluster_size=%d (§3)",
                    100 * nf, 100 * config.NOISE_RETRY_THRESHOLD, lowered)
        hp = {**config.HDBSCAN_PARAMS, "min_cluster_size": lowered}
        labels, reduced, reducer, clusterer = _fit(embeddings, dict(config.UMAP_PARAMS), hp)
        log.info("retry: %d clusters, noise %.1f%%",
                 len(set(labels.tolist()) - {-1}), 100 * noise_fraction(labels))

    return labels, reduced, reducer, clusterer


def persist_taxonomy(embeddings: np.ndarray, reduced: np.ndarray, labels: np.ndarray,
                     clusterer=None, out_dir=None, records: list[dict] | None = None) -> None:
    """Save the LOCKED taxonomy the P5 live run assigns against (§7.8, §10).

    Design choice: persist per-cluster centroids in the ORIGINAL embedding space
    (~clusters x 3072, a few MB) so the live run assigns a new review by cosine
    to the nearest centroid on its raw embedding. This deliberately avoids
    pickling the fitted UMAP reducer (~500 MB — it carries its training graph),
    which would be impractical to ship to a lightweight always-on host, and is
    also more stable than UMAP.transform on unseen points. Reduced-space centroids
    are saved too (tiny) for offline inspection.
    """
    d = out_dir or config.TAXONOMY_DIR
    d.mkdir(parents=True, exist_ok=True)

    labels = np.asarray(labels)
    emb_centroids, red_centroids, clabels = [], [], []
    for lab in sorted(set(labels.tolist()) - {-1}):
        mask = labels == lab
        emb_centroids.append(embeddings[mask].mean(axis=0))
        red_centroids.append(reduced[mask].mean(axis=0))
        clabels.append(int(lab))

    emb_arr = np.asarray(emb_centroids, dtype=np.float32)
    np.save(d / "centroids_embedding.npy", emb_arr)
    np.save(d / "centroids_reduced.npy", np.asarray(red_centroids, dtype=np.float32))
    # STEP 7: labels are written WITH the corpus fingerprint. A bare list is the legacy
    # schema and app/backend refuses to boot on it — deliberately, since a bare list is
    # exactly what a taxonomy carried over from another corpus looks like.
    if records is None:
        raise ValueError(
            "persist_taxonomy() requires `records` (the corpus this taxonomy was built "
            "from) so the fingerprint can be computed. Writing an unfingerprinted "
            "taxonomy would produce an artifact the runtime refuses to serve."
        )
    from . import fingerprint as _fp
    _fp.write_labels(d / "centroid_labels.json", clabels,
                     _fp.compute(records, embedding_model=config.EMBEDDING_MODEL))

    # Novelty threshold for the live run (§10): 95th pct intra-cluster cosine distance.
    from . import assign
    threshold = assign.compute_threshold(embeddings, labels, emb_arr, clabels, pct=95.0)
    (d / "assignment_threshold.json").write_text(
        json.dumps({"threshold": threshold, "metric": "cosine_distance", "percentile": 95}),
        encoding="utf-8")

    if clusterer is not None:                       # small (~MBs); kept for reference
        joblib.dump(clusterer, d / "hdbscan_clusterer.joblib")
    log.info("persisted taxonomy: %d embedding-space centroids (novelty thr=%.3f) -> %s",
             len(clabels), threshold, d)
