"""Triangulation loader — Pane 2 (§9 Table 5).

Human-owned primary-research layer (survey + interview signals) for Pane 2.
Mirrors funnel_map.py: code LOADS the human file, it never generates it. Unlike
the mandatory funnel mapping this layer is OPTIONAL — no file, or an empty
`rows`, means primary research is still in progress and the UI shows an honest
empty state rather than fabricated rows.

Review-mined and primary-research numbers live in SEPARATE fields and are NEVER
summed or averaged. The review signal is JOINED from the theme by `theme_id`, so
a human never re-types it — that join is what structurally guarantees no blending.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .. import config

log = logging.getLogger(__name__)

_DEFAULT_PATH = config.INTERPRET_DIR / "triangulation.json"

# The only verdicts a row may carry (empty is allowed while a row is still open).
VERDICTS = {"Converged", "Diverged", "Unresolved"}


def _theme_id(t: dict) -> str:
    return f"{t.get('track', 'full')}:{t.get('cluster_id', '')}"


def load_rows(path: Path | str | None = None) -> list[dict]:
    """Return the human-entered primary-research rows (or [] if none yet).

    Missing file or empty `rows` -> [] (primary research is optional / not-yet-done).
    Raises ValueError on a malformed row (missing `theme_id`, or a `verdict`
    outside the enum) so a bad hand-edit fails loud instead of silently dropping
    a row near the deadline.
    """
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    rows = raw.get("rows", [])
    for i, r in enumerate(rows):
        tid = (r.get("theme_id") or "").strip()
        if not tid:
            raise ValueError(f"triangulation.json row {i}: missing theme_id")
        verdict = (r.get("verdict") or "").strip()
        if verdict and verdict not in VERDICTS:
            raise ValueError(
                f"triangulation.json row {i} (theme_id {tid!r}): invalid verdict "
                f"{verdict!r}; choose from {sorted(VERDICTS)}"
            )
    return rows


def build_rows(themes: list[dict], primary_rows: list[dict],
               corpus_usable: int = 0) -> list[dict]:
    """Join each primary-research row to its theme by `theme_id` -> display rows.

    `review_signal` is taken from the THEME (never from the human file);
    survey/interview/verdict/interpretation come from the human file. An unknown
    `theme_id` raises ValueError naming the bad id and listing the valid ones —
    a typo must never silently drop a row from the table.
    """
    index = {_theme_id(t): t for t in themes}
    out: list[dict] = []
    for r in primary_rows:
        tid = (r.get("theme_id") or "").strip()
        theme = index.get(tid)
        if theme is None:
            raise ValueError(
                f"triangulation.json: unknown theme_id {tid!r} — not one of the "
                f"published themes. Valid ids: {sorted(index)}"
            )
        n = theme.get("review_count", theme.get("size", 0))
        pct = theme.get("pct_of_corpus")
        if pct is None:
            pct = round(100 * n / corpus_usable, 1) if corpus_usable else 0.0
        out.append({
            "theme_id": tid,
            "theme_name": theme.get("theme_name", ""),
            "review_signal": {"n": n, "pct": pct},
            "survey_signal": r.get("survey_signal"),        # {n, pct} or None — primary, never blended
            "interview_signal": r.get("interview_signal"),  # "n of N" str or None — primary, never blended
            "verdict": (r.get("verdict") or "").strip(),
            "interpretation": (r.get("interpretation") or "").strip(),
        })
    return out
