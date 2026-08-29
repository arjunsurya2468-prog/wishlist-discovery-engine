"""Opportunity-area recommendation card.

THESIS CHANGED FROM THE PREVIOUS BUILD. The old card recommended a product CATEGORY
from competitor whitespace. This brief asks a different question: which OPPORTUNITY
AREA — an uncertainty axis, at a specific gate of the wishlist -> purchase funnel —
has the highest potential to move wishlist conversion.

The opportunity area is an OUTPUT of the engine, never pre-chosen. Scoring rules
R1-R6 below are fixed BEFORE the run and are NOT re-tuned to make a preferred axis
win (anti-backwards-fitting guard). Whichever axis the fixed rules surface ships
as-is — including the honest "no single axis dominates".
"""
from __future__ import annotations

from ..ingest import lexicon

# Gates where a conversion actually dies. "Save" is excluded from opportunity scoring:
# a save that was never purchase intent is a measurement artefact, not a fixable gap —
# it is reported separately (see the bookmarking split in the brief-questions tab).
_FRICTION_GATES = {"Return", "Resolve", "Convert"}

# R2 — an axis is eligible only if this many records stall on it.
_VOLUME_FLOOR = 5
# R4 — multiplier when an independent clustered theme corroborates the axis.
_CONVERGENCE_MULT = 1.5
# R5 — multiplier when users describe leaving the platform to resolve the axis.
# Externalised uncertainty is the strongest signal that the product surface has a hole.
_EXTERNAL_MULT = 1.3
# R6 — "no single axis dominates" if the top two are this close.
_TIE_BAND = 0.10


def _infer_axes(theme: dict) -> list[str]:
    """Axes from cluster stats, else from theme name/summary keywords (R1: no fallback)."""
    axes = list((theme.get("axis_mentions") or theme.get("category_mentions") or {}).keys())
    if axes:
        return axes
    text = f"{theme.get('theme_name', '')} {theme.get('summary', '')}".lower()
    return [axis for axis, terms in lexicon.AXIS_TERMS.items()
            if any(t in text for t in terms[:6])]


def _convergent_themes(themes: list[dict], axis: str) -> list[dict]:
    """Friction-gated clustered themes whose inferred axis == `axis`."""
    out = []
    for t in themes:
        if t.get("funnel_gate") not in _FRICTION_GATES:
            continue
        if axis not in _infer_axes(t):
            continue
        out.append({
            "theme_name": t.get("theme_name", ""),
            "funnel_gate": t.get("funnel_gate", ""),
            "review_count": t.get("review_count", 0) or t.get("size", 0),
            "per_app": t.get("per_app", {}) or {},
        })
    out.sort(key=lambda b: b["review_count"], reverse=True)
    return out


def _dominant_gate(convergent: list[dict]) -> str | None:
    """The gate this axis's themes concentrate in — where the fix has to land."""
    if not convergent:
        return None
    weight: dict[str, int] = {}
    for c in convergent:
        weight[c["funnel_gate"]] = weight.get(c["funnel_gate"], 0) + c["review_count"]
    return max(weight, key=weight.get) if weight else None


def _no_dominant(corpus_usable: int | None, reason: str) -> dict:
    return {
        "axis": None,
        "headline": "No single uncertainty axis dominates",
        "confidence": "low",
        "signal_score": 0.0,
        "stall_score": 0.0,
        "stalled_count": 0,
        "funnel_gate": None,
        "convergent_themes": [],
        "runner_up": None,
        "evidence_counts": {"corpus_usable": corpus_usable},
        "supporting_themes": [],
        "quotes": [],
        "what_this_means": reason,
    }


def recommend(themes: list[dict], *, resolution_template: dict | None = None,
              corpus_usable: int | None = None,
              external_refs: dict[str, int] | None = None) -> dict:
    """Return the opportunity-area recommendation card (R1-R6).

    Driven by unresolved stall volume x corroboration x externalisation. A theme with
    no inferable axis contributes nothing to any axis (R1).
    """
    by_axis = (resolution_template or {}).get("by_axis", {})
    friction_themes = [t for t in themes
                       if not t.get("omitted") and t.get("funnel_gate") in _FRICTION_GATES]

    scored: list[dict] = []
    for axis, entry in by_axis.items():
        stalled = entry.get("stalled_count", 0)
        resolved = entry.get("resolved_count", 0)
        if stalled < _VOLUME_FLOOR:                        # R2 volume floor
            continue
        # R3 stall score: stall volume weighted by how rarely users resolve it alone.
        unresolved_share = 1 - entry.get("resolution_rate", 0.0)
        stall = stalled * unresolved_share
        convergent = _convergent_themes(friction_themes, axis)          # R4
        mult = _CONVERGENCE_MULT if convergent else 1.0
        ext_n = (external_refs or {}).get(axis, 0)                      # R5
        if ext_n:
            mult *= _EXTERNAL_MULT
        score = stall * mult
        scored.append({
            "axis": axis,
            "stalled_count": stalled,
            "resolved_count": resolved,
            "resolution_rate": entry.get("resolution_rate", 0.0),
            "stall_score": round(stall, 1),
            "convergent": convergent,
            "external_refs": ext_n,
            "gate": _dominant_gate(convergent),
            "score": round(score, 1),
            "quotes": entry.get("stalled_quotes", [])[:3],
        })

    if not scored:                                          # nothing cleared R2
        return _no_dominant(
            corpus_usable,
            f"No uncertainty axis cleared the stall-volume floor (>={_VOLUME_FLOOR} records "
            "describing a stalled decision) — hesitation is diffuse rather than concentrated "
            "on one axis.",
        )

    scored.sort(key=lambda s: -s["score"])                  # R5 top-scoring eligible
    top = scored[0]
    runner = scored[1] if len(scored) > 1 else None

    # R6 tie band -> honest "no single axis dominates"
    if runner and top["score"] > 0 and (top["score"] - runner["score"]) / top["score"] < _TIE_BAND:
        out = _no_dominant(
            corpus_usable,
            f"The top two axes — {top['axis']} and {runner['axis']} — score within "
            f"~{int(_TIE_BAND * 100)}% of each other, so no single axis dominates. This is a "
            "segmentation result, not a null result: the brief anticipates different segments "
            "being blocked by different axes.",
        )
        out["runner_up"] = runner["axis"]
        out["convergent_themes"] = top["convergent"]
        return out

    # Confidence: how many of the three strength conditions the winner meets.
    conds = [top["resolution_rate"] <= 0.2, bool(top["convergent"]), top["stalled_count"] >= 10]
    n = sum(conds)
    confidence = "high" if n == 3 else ("medium" if n >= 1 else "low")

    conv = top["convergent"]
    conv_line = ""
    if conv:
        c0 = conv[0]
        conv_line = (
            f" An independently clustered theme corroborates it — “{c0['theme_name']}” "
            f"({c0['funnel_gate']}, n={c0['review_count']})."
        )
    ext_line = ""
    if top["external_refs"]:
        ext_line = (
            f" {top['external_refs']} records describe leaving the platform to resolve it, "
            "so the uncertainty is currently answered off-app or not at all."
        )

    what = (
        f"{top['axis']} is the strongest opportunity area: {top['stalled_count']} records "
        f"describe a decision stalling on it, and only {top['resolved_count']} describe "
        f"resolving it ({top['resolution_rate']:.0%} resolution rate)."
        f"{conv_line}{ext_line} The fix has to land at the "
        f"{top['gate'] or 'Resolve'} gate. Axis was derived from the data by fixed rules, "
        "not pre-selected."
    )

    return {
        "axis": top["axis"],
        "headline": top["axis"],
        "confidence": confidence,
        "signal_score": top["score"],
        "stall_score": top["stall_score"],
        "stalled_count": top["stalled_count"],
        "resolved_count": top["resolved_count"],
        "resolution_rate": top["resolution_rate"],
        "external_refs": top["external_refs"],
        "funnel_gate": top["gate"],
        "convergent_themes": conv,
        "runner_up": runner["axis"] if runner else None,
        "runner_up_score": runner["score"] if runner else None,
        "evidence_counts": {
            "stalled_records": top["stalled_count"],
            "resolved_records": top["resolved_count"],
            "convergent_theme_count": len(conv),
            "external_reference_records": top["external_refs"],
            "corpus_usable": corpus_usable,
        },
        "supporting_themes": [
            {"theme_name": b["theme_name"], "funnel_gate": b["funnel_gate"],
             "review_count": b["review_count"], "per_app": b["per_app"]}
            for b in conv[:5]
        ],
        "quotes": top["quotes"],
        "what_this_means": what,
    }
