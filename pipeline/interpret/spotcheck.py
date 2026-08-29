"""Spot-check protocol — P3 (§8.1).

Stratified sample of ~25–30 reviews across named themes; the researcher judges
cluster coherence and theme fit. Agreement % and disagreements are human-owned —
code samples and computes stats, never generates judgments.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .. import config

_DEFAULT_PATH = config.INTERPRET_DIR / "spotcheck.json"
_PER_THEME = 2
_TARGET_TOTAL = 28


def sample_reviews(clustered_rows: list[dict], themes: list[dict], *,
                   seed: int = 42, per_theme: int = _PER_THEME,
                   target: int = _TARGET_TOTAL) -> list[dict]:
    """Pick a stratified sample: up to `per_theme` reviews per named theme."""
    by_cluster: dict[int, list[dict]] = {}
    for row in clustered_rows:
        cid = row.get("cluster_id")
        if cid is not None and cid != -1:
            by_cluster.setdefault(cid, []).append(row)

    rng = random.Random(seed)
    picked: list[dict] = []
    seen: set[str] = set()

    for theme in themes:
        if theme.get("omitted"):
            continue
        cid = theme["cluster_id"]
        pool = by_cluster.get(cid, [])
        if not pool:
            continue
        rng.shuffle(pool)
        for row in pool[:per_theme]:
            rid = row["review_id"]
            if rid in seen:
                continue
            seen.add(rid)
            picked.append({
                "review_id": rid,
                "cluster_id": cid,
                "theme_name": theme.get("theme_name", ""),
                "theme_key": theme.get("theme_key", ""),
                "app": row["app"],
                "text": row["text"][:300],
                "agrees_with_theme": None,
                "notes": "",
            })
            if len(picked) >= target:
                return picked

    # Top up from largest clusters if under target
    if len(picked) < target:
        extras = [r for rows in by_cluster.values() for r in rows if r["review_id"] not in seen]
        rng.shuffle(extras)
        for row in extras:
            picked.append({
                "review_id": row["review_id"],
                "cluster_id": row["cluster_id"],
                "theme_name": "",
                "theme_key": "",
                "app": row["app"],
                "text": row["text"][:300],
                "agrees_with_theme": None,
                "notes": "",
            })
            if len(picked) >= target:
                break
    return picked


def load_spotcheck(path: Path | str | None = None) -> dict:
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        raise FileNotFoundError(f"spotcheck not found at {p} — fill in judgments before interpret (§8.1)")
    return json.loads(p.read_text(encoding="utf-8"))


def compute_agreement(spotcheck: dict) -> dict:
    """Return stats from human judgments. Pending (null) rows are excluded."""
    rows = spotcheck.get("samples", [])
    judged = [r for r in rows if r.get("agrees_with_theme") is not None]
    if not judged:
        return {"spotcheck_agreement_pct": None, "judged": 0, "agreements": 0,
                "disagreements": [], "pending": len(rows)}

    agreements = sum(1 for r in judged if r["agrees_with_theme"])
    disagreements = [
        {"review_id": r["review_id"], "theme_name": r.get("theme_name", ""),
         "notes": r.get("notes", "")}
        for r in judged if not r["agrees_with_theme"]
    ]
    pct = round(100 * agreements / len(judged), 1)
    return {
        "spotcheck_agreement_pct": pct,
        "judged": len(judged),
        "agreements": agreements,
        "disagreements": disagreements,
        "pending": len(rows) - len(judged),
    }


def write_template(samples: list[dict], path: Path | str | None = None) -> Path:
    """Write an empty spotcheck template for the researcher to fill."""
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "instructions": "Set agrees_with_theme true/false per row; add notes for disagreements (§8.1).",
        "samples": samples,
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
