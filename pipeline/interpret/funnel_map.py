"""Funnel mapping loader.

Loads the HUMAN-authored theme -> wishlist-funnel gate mapping + one-line rationale
+ optional what_this_means brief. Code loads it; code never generates it. An unmapped
theme is incomplete.

The funnel is WISHLIST -> PURCHASE (models.FUNNEL_GATES):

    Save     the item enters the wishlist. Failure here = the save was never purchase
             intent in the first place (bookmarking, inspiration, price-watch parking).
    Return   the user comes back to the saved item. Failure here = the wishlist is a
             write-only surface; saved items are never revisited at all.
    Resolve  the remaining uncertainty clears. Failure here = fit/size/quality/price/
             social doubt the product surface never answers, so the decision stalls.
    Convert  the purchase fires. Failure here = intent and confidence exist, but
             something at the final step (price threshold, return risk, checkout) blocks it.

A theme is mapped to the gate whose FAILURE it describes, not the gate it mentions.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..models import FUNNEL_GATES

_DEFAULT_PATH = config.INTERPRET_DIR / "funnel_mapping.json"


def _theme_key(track: str, cluster_id: int) -> str:
    return f"{track}:{cluster_id}"


def load_mapping(path: Path | str | None = None) -> dict[str, dict]:
    """Return {theme_key: {funnel_gate, mapping_rationale, what_this_means?}}."""
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"funnel mapping not found at {p} — create it before running interpret (§7.6)"
        )
    raw = json.loads(p.read_text(encoding="utf-8"))
    entries = raw.get("mappings", raw)
    out: dict[str, dict] = {}
    for key, val in entries.items():
        gate = val.get("funnel_gate", "")
        if gate not in FUNNEL_GATES:
            raise ValueError(f"{key}: invalid funnel_gate {gate!r}; choose from {FUNNEL_GATES}")
        rationale = (val.get("mapping_rationale") or "").strip()
        if not rationale:
            raise ValueError(f"{key}: mapping_rationale is mandatory (§7.6)")
        out[key] = {
            "funnel_gate": gate,
            "mapping_rationale": rationale,
            "what_this_means": (val.get("what_this_means") or "").strip(),
        }
    return out


def apply_mapping(themes: list[dict], mapping: dict[str, dict], track: str) -> tuple[list[dict], list[str]]:
    """Merge human mapping fields into theme dicts. Returns (themes, unmapped_keys)."""
    unmapped: list[str] = []
    for theme in themes:
        if theme.get("omitted"):
            continue
        key = _theme_key(track, theme["cluster_id"])
        entry = mapping.get(key)
        if entry is None:
            unmapped.append(key)
            continue
        theme["funnel_gate"] = entry["funnel_gate"]
        theme["mapping_rationale"] = entry["mapping_rationale"]
        theme["what_this_means"] = entry["what_this_means"]
        theme["theme_key"] = key
    return themes, unmapped


def validate_complete(themes: list[dict]) -> list[str]:
    """Return theme_keys that survived naming but lack a funnel_gate."""
    missing = []
    for t in themes:
        if t.get("omitted"):
            continue
        if not t.get("funnel_gate"):
            missing.append(t.get("theme_key") or str(t.get("cluster_id")))
    return missing
