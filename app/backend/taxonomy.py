"""Locked-taxonomy assignment.

Loads the persisted embedding-space centroids + novelty threshold and assigns a new
record embedding to its nearest cluster, or -1 (novel/unassigned) when it lies beyond
the threshold. Read-only: the live run never mutates the taxonomy. Core math lives in
pipeline.cluster.assign so it is identical to the offline path.

STEP 7: loading is gated on the corpus fingerprint. See pipeline.cluster.fingerprint —
a taxonomy that cannot prove which corpus produced it raises here rather than serving
confident nonsense.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from pipeline import config
from pipeline.cluster import assign as _assign
from pipeline.cluster import fingerprint as fp

log = logging.getLogger(__name__)


def load_taxonomy(taxonomy_dir=None, *, verify: bool = True):
    """Load (centroids, labels, threshold), verifying the corpus fingerprint.

    `verify=False` exists for offline inspection tooling ONLY. The serving path must
    never pass it — an unverified taxonomy is precisely the failure this gate exists
    to prevent.
    """
    d = Path(taxonomy_dir or config.TAXONOMY_DIR)
    labels_path = d / "centroid_labels.json"
    if not labels_path.exists():
        raise FileNotFoundError(
            f"no taxonomy at {d} — build one from the current corpus before serving"
        )

    corpus_fp, labels = fp.read_from_labels(labels_path)
    if verify:
        for w in fp.verify(corpus_fp):
            log.warning("[taxonomy] %s", w)

    centroids = np.load(d / "centroids_embedding.npy")
    threshold = json.loads((d / "assignment_threshold.json").read_text(encoding="utf-8"))["threshold"]

    if len(labels) != len(centroids):
        raise ValueError(
            f"taxonomy is inconsistent: {len(labels)} labels vs {len(centroids)} centroids"
        )
    return centroids, labels, threshold


def assign_nearest(embedding, taxonomy=None):
    """Return (cluster_label, cosine_distance). label == -1 means novel/unassigned."""
    centroids, labels, threshold = taxonomy or load_taxonomy()
    lab, dist = _assign.assign(np.atleast_2d(embedding), centroids, labels, threshold=threshold)
    return int(lab[0]), float(dist[0])
