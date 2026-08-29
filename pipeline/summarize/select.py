"""Cluster selection + representative sampling — P3.

Union-selection (per the P2 decision): name the union of the top clusters by
SCORE (size x relevance_share) and the top clusters by RELEVANCE_SHARE (size floor
applied), so both big structural themes and small category-signal-rich pockets get
named. Each selected cluster is tagged with its selection_path.
"""
from __future__ import annotations

import numpy as np

SCORE_TOP = 12
REL_TOP = 12
REL_MIN_SIZE = 20


def union_select(ranked: list[dict], score_top=SCORE_TOP, rel_top=REL_TOP,
                 rel_min_size=REL_MIN_SIZE) -> list[dict]:
    """`ranked` is already sorted by score (desc). Returns selected clusters, each
    with a `selection_path` in {'score', 'relevance', 'score+relevance'}."""
    by_score = ranked[:score_top]
    by_rel = sorted([c for c in ranked if c["size"] >= rel_min_size],
                    key=lambda c: c["relevance_share"], reverse=True)[:rel_top]
    score_ids = {c["cluster_id"] for c in by_score}
    rel_ids = {c["cluster_id"] for c in by_rel}

    selected = []
    for c in ranked:
        cid = c["cluster_id"]
        if cid not in score_ids and cid not in rel_ids:
            continue
        paths = []
        if cid in score_ids:
            paths.append("score")
        if cid in rel_ids:
            paths.append("relevance")
        out = dict(c)
        out["selection_path"] = "+".join(paths)
        selected.append(out)
    return selected


def pick_samples(member_idx: list[int], X: np.ndarray, texts: list[str], k: int = 7) -> list[str]:
    """Medoid + greedy-diverse sample of up to k reviews (§7.4: 5-8 representative)."""
    member_idx = list(member_idx)
    if len(member_idx) <= k:
        return [texts[i] for i in member_idx]

    E = X[member_idx]
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    centroid = E.mean(axis=0)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-9)

    picked = [int(np.argmax(E @ centroid))]      # medoid first
    while len(picked) < k:
        max_sim_to_picked = (E @ E[picked].T).max(axis=1)
        max_sim_to_picked[picked] = 2.0           # exclude already-picked
        picked.append(int(np.argmin(max_sim_to_picked)))
    return [texts[member_idx[p]] for p in picked]
