"""Cluster ranking — a deliberate departure from the reference architecture.

Rank by `size x share_of_relevance-flagged`, RATING-AGNOSTIC. A rating-weighted rank
(`size x (6 - avg_rating)`) would bury the target signal for this brief: the records
that explain wishlist abandonment are frequently NOT complaints. "Love this brand,
I've had three of their dresses saved for months because I can never tell my size in
their sizing" is a positive, high-rating record and is exactly what we want surfaced.

Rating is also structurally absent from most of this corpus — community and video
records carry no star rating at all — so ranking on it would silently privilege the
secondary store-review corpus over the primary community corpus, inverting the
weighting STEP 6 established.

The relevance flag only allocates summarization budget; it never filters or clusters.
avg_rating is computed and reported, never used to rank. All clusters are kept.
"""
from __future__ import annotations

from collections import defaultdict

from .. import config


def _avg_rating(rows: list[dict]) -> float | None:
    vals = [r["rating"] for r in rows if r.get("rating") is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def rank_clusters(reviews: list[dict]) -> list[dict]:
    """One stats dict per non-noise cluster, sorted by score (desc).

    Each review dict must carry `cluster_id`, `relevance_flagged`, `app`,
    `rating`, `category_mentioned`.
    """
    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for r in reviews:
        by_cluster[r.get("cluster_id")].append(r)

    ranked: list[dict] = []
    for cid, rows in by_cluster.items():
        if cid is None or cid == -1:
            continue
        size = len(rows)
        flagged = sum(1 for r in rows if r.get("relevance_flagged"))
        share = flagged / size if size else 0.0

        per_app = {app: 0 for app in config.APPS}
        cats: dict[str, int] = defaultdict(int)
        for r in rows:
            if r.get("app") in per_app:
                per_app[r["app"]] += 1
            for c in r.get("category_mentioned", []):
                cats[c] += 1

        ranked.append({
            "cluster_id": int(cid),
            "size": size,
            "relevance_flagged": flagged,
            "relevance_share": round(share, 3),
            "score": round(size * share, 2),            # the ranking key
            "avg_rating": _avg_rating(rows),            # reported, NOT ranked
            "per_app": per_app,
            "category_mentions": dict(sorted(cats.items(), key=lambda x: -x[1])),
        })

    ranked.sort(key=lambda c: c["score"], reverse=True)
    return ranked


def giant_cluster_id(ranked: list[dict], total_clustered: int) -> int | None:
    """Return the cluster id that swallows > GIANT_CLUSTER_THRESHOLD of clustered
    volume (candidate for rating-strata re-split, §3), else None."""
    if not ranked or not total_clustered:
        return None
    biggest = max(ranked, key=lambda c: c["size"])
    if biggest["size"] / total_clustered > config.GIANT_CLUSTER_THRESHOLD:
        return biggest["cluster_id"]
    return None
