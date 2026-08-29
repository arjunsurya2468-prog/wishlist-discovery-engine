"""Resolution-template card.

THESIS CHANGED FROM THE PREVIOUS BUILD. The old card compared competitor positive
voice per product category to find category whitespace. This brief asks nothing about
category whitespace, so that thesis was not ported.

What this card does now: isolates the language of RESOLVED purchase decisions — records
where a user describes an uncertainty actually clearing and the purchase happening —
and contrasts it, per uncertainty axis, against the STALLED records on the same axis.

Why that is the useful contrast for this brief: the metric is wishlist -> purchase
conversion. Knowing what a resolved decision sounds like tells you what the product
surface would have to supply to manufacture that resolution. An axis with heavy stall
volume and almost no resolution language is an axis the platform currently leaves the
user to solve alone — which is exactly the opportunity the brief is asking us to find.

File name kept from the previous build so the rewrite lands in one place rather than
rippling through imports.
"""
from __future__ import annotations

import re
from collections import defaultdict

from ..ingest import lexicon

# A decision that CLOSED — the user bought, or explicitly resolved the doubt.
_RESOLVED = re.compile(
    r"\b(finally (?:bought|ordered|got)|went ahead and|ended up (?:buying|ordering|getting)|"
    r"decided to buy|placed the order|bought it|ordered it|glad i bought|"
    r"took the plunge|pulled the trigger|checked the size chart and|"
    r"the reviews confirmed|photos helped|helped me decide)\b", re.I)

# A decision still OPEN — saved, postponed, abandoned.
_STALLED = re.compile(
    r"\b(still (?:in|sitting in) my|never bought|didn'?t buy|haven'?t bought|"
    r"keep postponing|waiting for|not sure if|can'?t decide|cant decide|"
    r"confused between|gave up|removed it from|abandoned)\b", re.I)


def _axes(row: dict) -> list[str]:
    """Uncertainty axes this record touches, ALWAYS re-derived from the live lexicon.

    Deliberately does NOT trust `axis_mentioned` / `category_mentioned` stored on the
    row. Those labels were written at ingest time under whatever lexicon version was
    current then, and the axis taxonomy changes as the lexicon is tuned. Mixing stored
    labels from an older version with freshly-derived ones from the current version
    produces near-duplicate axes ("Returns" alongside "Returns & Exchange"), which
    splits the evidence for a single uncertainty across two buckets and can hand the
    recommendation to whichever spelling happens to win the split.

    Re-deriving is cheap (regex over text already in memory) and makes the axis
    taxonomy consistent with lexicon.LEXICON_VERSION by construction.
    """
    _, derived = lexicon.flag(row.get("text", ""), row.get("app"))
    return derived


def _state(text: str) -> str | None:
    """resolved / stalled / None. Resolution wins ties — an explicit purchase closes it."""
    if _RESOLVED.search(text):
        return "resolved"
    if _STALLED.search(text):
        return "stalled"
    return None


def extract(rows: list[dict], *, max_quotes: int = 5) -> dict:
    """Build the resolution-template card from the corpus.

    Returns per-axis resolved vs stalled volumes, the quotes for each, and the axes
    where stall volume dominates — the unresolved-uncertainty gaps.
    """
    by_axis: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: {"resolved": [], "stalled": []})

    for row in rows:
        text = row.get("text", "")
        state = _state(text)
        if state is None:
            continue
        for axis in _axes(row):
            by_axis[axis][state].append(row)

    per_axis: dict[str, dict] = {}
    for axis, buckets in by_axis.items():
        n_res = len(buckets["resolved"])
        n_stall = len(buckets["stalled"])
        if not (n_res or n_stall):
            continue
        total = n_res + n_stall
        per_axis[axis] = {
            "axis": axis,
            "resolved_count": n_res,
            "stalled_count": n_stall,
            "resolution_rate": round(n_res / total, 2) if total else 0.0,
            "resolved_quotes": [r["text"][:200] for r in buckets["resolved"][:max_quotes]],
            "stalled_quotes": [r["text"][:200] for r in buckets["stalled"][:max_quotes]],
            # An axis users stall on and almost never describe resolving themselves.
            "unresolved_gap": n_stall >= 5 and n_res <= max(1, n_stall // 5),
        }

    gaps = [a for a, e in per_axis.items() if e["unresolved_gap"]]
    gaps.sort(key=lambda a: per_axis[a]["stalled_count"], reverse=True)

    headline_quotes: list[str] = []
    for axis in gaps[:3]:
        headline_quotes.extend(per_axis[axis]["stalled_quotes"][:2])

    return {
        "lexicon_version": lexicon.LEXICON_VERSION,
        "summary": (
            "Per uncertainty axis: how often users describe a purchase decision closing, "
            "versus how often they describe it stalling. Axes are re-derived from the "
            f"live lexicon ({lexicon.LEXICON_VERSION}), never read from stored labels."
        ),
        "by_axis": per_axis,
        "largest_gaps": gaps[:5],
        "headline_quotes": headline_quotes[:max_quotes],
        "what_this_means": (
            "Axes where users stall in volume but rarely describe resolving the doubt "
            "themselves are the ones the platform currently leaves unanswered — the user "
            "has no workaround good enough to close the decision."
        ),
    }
