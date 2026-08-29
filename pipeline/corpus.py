"""Corpus loader — assembles the combined, cross-app record set for embedding and
clustering. Clustering runs on ALL apps together; per-app splits are tracked per
cluster afterwards for the comparative view.

CORPUS WEIGHTING (STEP 6) — INVERTED FROM THE PREVIOUS BUILD.

Previously, app/Play Store reviews were the quantified base and forum text was a
separate depth corpus excluded from clustering. For this brief that is backwards.

Why: wishlist-abandonment reasoning does not appear in app store reviews. Store
reviews are written at a moment of transactional friction — delivery, refunds,
returns, app bugs, order failures — by users who have already transacted. A user who
saved twelve kurtas and bought none has no reason to open the Play Store and no
review to leave. The reasoning the brief asks for ("why is this still sitting in my
wishlist") lives in community and discussion text, where people narrate their own
purchase deliberation to each other.

So: COMMUNITY text is the spine and the quantified base. STORE reviews are secondary
corroboration. Every coverage and volume figure must be reported against the corpus
it actually came from — see split_by_weight() and the primary/secondary denominators
in diagnostics.py. A percentage quoted against the wrong denominator is the single
easiest way to make this engine's numbers wrong.
"""
from __future__ import annotations

import logging

from . import cache, config

log = logging.getLogger(__name__)


def latest_date() -> str | None:
    """Most recent cache date partition present across any app."""
    dates: set[str] = set()
    if not config.CACHE_DIR.exists():
        return None
    for app_dir in config.CACHE_DIR.iterdir():
        # ONLY app partitions. CACHE_DIR also holds source-keyed raw landings
        # (data/cache/youtube/<date>/, _forums/, and each source's _sample/ dir).
        # Treating those as apps would read a source name as a date.
        if app_dir.is_dir() and app_dir.name in config.APPS:
            for date_dir in app_dir.iterdir():
                if (date_dir / "reviews_normalized.json").exists():
                    dates.add(date_dir.name)
    return max(dates) if dates else None


# ---- Source weighting (STEP 6) ----
# PRIMARY: the deliberation corpus. This is the quantified base — headline percentages
# are computed against this denominator.
PRIMARY_SOURCES = ("reddit", "youtube", "twitter", "forum")
# SECONDARY: transactional store reviews. Clustered alongside (a shared embedding space
# is what lets a theme be shown to appear in both), but never the base for a headline stat.
SECONDARY_SOURCES = ("play", "appstore")

# Everything is clustered together; the split is a REPORTING property, not a
# clustering one. Keeping both in one space is what makes "this theme shows up in
# community text AND in store reviews" a checkable claim rather than an assertion.
CLUSTERING_STORES = PRIMARY_SOURCES + SECONDARY_SOURCES


def load_corpus(date: str | None = None, apps: list[str] | None = None,
                stores: tuple[str, ...] = CLUSTERING_STORES) -> list[dict]:
    """Return the combined normalized corpus for a date, filtered to `stores`.

    Defaults to the latest date, all apps, and ALL sources — community text included,
    because it is the spine of this corpus (see module docstring). Skips apps with no
    cache for the date.
    """
    date = date or latest_date()
    if date is None:
        return []
    apps = apps or list(config.APPS)

    corpus: list[dict] = []
    for app in apps:
        try:
            rows = cache.load_normalized(app, date)
        except (FileNotFoundError, OSError):
            log.warning("no normalized cache for %s @ %s — skipping", app, date)
            continue
        corpus.extend(r for r in rows if r.get("store") in stores)
    log.info("loaded corpus: %d reviews across %d apps @ %s (stores=%s)",
             len(corpus), len(apps), date, list(stores))
    return corpus


def load_primary(date: str | None = None, apps: list[str] | None = None) -> list[dict]:
    """Community/discussion records only — the quantified base for headline stats."""
    return load_corpus(date, apps, stores=PRIMARY_SOURCES)


def load_secondary(date: str | None = None, apps: list[str] | None = None) -> list[dict]:
    """Store reviews only — secondary corroboration, never a headline denominator."""
    return load_corpus(date, apps, stores=SECONDARY_SOURCES)


def split_by_weight(rows: list[dict]) -> dict[str, list[dict]]:
    """Split any row set into {'primary': [...], 'secondary': [...]}.

    Use this before computing ANY percentage. Callers that need a rate should state
    which denominator they used; a figure quoted against the combined corpus is
    almost always misleading for this brief.
    """
    primary, secondary = [], []
    for r in rows:
        (primary if r.get("store") in PRIMARY_SOURCES else secondary).append(r)
    return {"primary": primary, "secondary": secondary}


def weight_summary(rows: list[dict]) -> dict:
    """Composition of a row set, per source and per weight class."""
    from collections import Counter

    per_source = Counter(r.get("store", "unknown") for r in rows)
    split = split_by_weight(rows)
    n_p, n_s = len(split["primary"]), len(split["secondary"])
    total = n_p + n_s
    return {
        "total": total,
        "primary_n": n_p,
        "secondary_n": n_s,
        "primary_pct": round(100 * n_p / total, 1) if total else 0.0,
        "secondary_pct": round(100 * n_s / total, 1) if total else 0.0,
        "per_source": dict(per_source),
        "base_for_headline_stats": "primary (community/discussion)",
    }
