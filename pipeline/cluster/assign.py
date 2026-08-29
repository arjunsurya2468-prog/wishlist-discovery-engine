"""Centroid assignment in EMBEDDING space with a novelty threshold (§7.8, §10).

Clusters are FORMED in reduced UMAP space, but the live run assigns new reviews by
cosine similarity to per-cluster centroids in the ORIGINAL embedding space (light,
stable, no 500 MB reducer). A cosine-distance threshold yields a 'novel / unassigned'
(-1) outcome so the live demo never force-fits an off-distribution review — plain
nearest-centroid has no noise outcome, which the demo needs.
"""
from __future__ import annotations

import numpy as np

NOVEL = -1


def _l2norm(M: np.ndarray) -> np.ndarray:
    M = np.asarray(M, dtype=np.float32)
    if M.ndim == 1:
        M = M[None, :]
    return M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)


def assign(embeddings: np.ndarray, centroids: np.ndarray, centroid_labels,
           threshold: float | None = None):
    """Return (labels, distances). If threshold given, points whose nearest-centroid
    cosine distance exceeds it get label NOVEL (-1)."""
    E = _l2norm(embeddings)
    C = _l2norm(centroids)
    sims = E @ C.T
    nn = sims.argmax(axis=1)
    dist = 1.0 - sims[np.arange(E.shape[0]), nn]
    labels = np.asarray(centroid_labels, dtype=int)[nn]
    if threshold is not None:
        labels = np.where(dist > threshold, NOVEL, labels)
    return labels, dist


def compute_threshold(embeddings: np.ndarray, labels, centroids: np.ndarray,
                      centroid_labels, pct: float = 95.0) -> float:
    """Threshold = the given percentile of intra-cluster cosine distance (each
    non-noise point to its own cluster centroid) — beyond it reads as novel."""
    E = _l2norm(embeddings)
    C = _l2norm(centroids)
    row = {int(l): i for i, l in enumerate(centroid_labels)}
    labels = np.asarray(labels)
    dists = []
    for i, lab in enumerate(labels):
        lab = int(lab)
        if lab == NOVEL or lab not in row:
            continue
        dists.append(1.0 - float(E[i] @ C[row[lab]]))
    return float(np.percentile(dists, pct)) if dists else 1.0
