"""Community corroboration strip.

ROLE REVERSED FROM THE PREVIOUS BUILD (STEP 6). Previously this card was a small
supplement: forums were a side corpus that mostly echoed the app-store complaints, and
this module carried a handful of hand-curated quotes corroborating a finding that came
from elsewhere.

For this brief the relationship inverts. Community/discussion text is the PRIMARY
corpus, so the corroboration this card reports runs the other way: it asks whether the
secondary store-review corpus independently echoes a theme the community corpus
produced. A theme visible in both is materially stronger than one visible in either.

The curated-quote list is deliberately EMPTY. It is populated by a human after the
first real clustering run, and every entry is substring-validated against the actual
corpus at build time — the same kill-switch as theme quotes. It is never pre-filled
with quotes from a previous project, and never with quotes that were not read in situ.
"""
from __future__ import annotations

from collections import Counter

from .. import corpus as corpus_mod
from ..summarize import validate_quotes as vq

NOTE = (
    "Community and discussion text (Reddit, YouTube comments, forums) is the primary "
    "corpus for this engine — it is where users narrate their own purchase deliberation. "
    "App and Play Store reviews are retained as a secondary corroboration corpus: they "
    "are written at moments of transactional friction and structurally under-represent "
    "the reasoning behind an unpurchased saved item."
)

# Human-selected corroboration quotes. POPULATE AFTER THE FIRST CLUSTERING RUN.
# Schema: {"quote": str, "source": str, "reads_as": str}
_CURATED: list[dict] = []


def _cross_source_themes(themes: list[dict]) -> list[dict]:
    """Themes carrying records from BOTH weight classes — the strongest evidence."""
    out = []
    for t in themes:
        if t.get("omitted"):
            continue
        per_source = t.get("per_source", {}) or {}
        n_primary = sum(n for s, n in per_source.items() if s in corpus_mod.PRIMARY_SOURCES)
        n_secondary = sum(n for s, n in per_source.items() if s in corpus_mod.SECONDARY_SOURCES)
        if n_primary and n_secondary:
            out.append({
                "theme_name": t.get("theme_name", ""),
                "funnel_gate": t.get("funnel_gate", ""),
                "primary_n": n_primary,
                "secondary_n": n_secondary,
                "corroboration": "cross-source",
            })
    out.sort(key=lambda x: -(x["primary_n"] + x["secondary_n"]))
    return out


def _verdict(themes: list[dict], cross: list[dict]) -> str:
    live = [t for t in themes if not t.get("omitted")]
    if not live:
        return "No themes to assess."
    if not cross:
        return (
            "No theme appears in both the community corpus and the store-review corpus. "
            "The two corpora are describing different things — which is itself the "
            "expected result, and is the reason community text is the quantified base "
            "rather than store reviews."
        )
    share = 100 * len(cross) / len(live)
    return (
        f"{len(cross)} of {len(live)} themes ({share:.0f}%) appear in BOTH the community "
        f"corpus and the store-review corpus. Cross-source themes are the most defensible "
        f"findings in this run; single-source themes are reported with that limitation stated."
    )


def build(records: list[dict], themes: list[dict] | None = None) -> dict:
    """Validate curated quotes against the corpus; report cross-source corroboration.

    `records` is the full record set (both weight classes). `themes` enables the
    cross-source check; omit it and only the composition block is returned.
    """
    texts = [r.get("text", "") for r in records]
    quotes = [
        {**c, "validation_status": "Validated"}
        for c in _CURATED
        if vq.is_valid(c["quote"], texts)          # kill-switch: only real substrings survive
    ]
    themes = themes or []
    cross = _cross_source_themes(themes)
    split = corpus_mod.split_by_weight(records)
    by_source = Counter(r.get("store") for r in records)
    return {
        "note": NOTE,
        "verdict": _verdict(themes, cross),
        "quotes": quotes,
        "cross_source_themes": cross[:10],
        "counts": {
            "total_records": len(records),
            "primary_records": len(split["primary"]),
            "secondary_records": len(split["secondary"]),
            "by_source": dict(by_source),
            "unique_threads": len({r.get("thread_id") for r in records if r.get("thread_id")}),
        },
    }
