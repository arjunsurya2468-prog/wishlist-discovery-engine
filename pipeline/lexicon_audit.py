"""Lexicon audit — the instrument check that runs BEFORE ingest.

WHY THIS IS A GATE AND NOT A REPORT
===================================
The relevance lexicon is the instrument that decides which uncertainty axis a record
is *about*. If an axis has no terms, the instrument reports 0% for it — and 0%-because-
absent is indistinguishable from 0%-because-unmeasurable once the numbers are in a
deck. That is not a cosmetic problem: it is the corpus-blindness failure that sank the
previous attempt, relocated from the corpus into the taxonomy.

So `--static` is a HARD PREREQUISITE, enforced in code. resolve_videos() calls
assert_axis_coverage() and refuses to spend quota if the audit has not passed against
the CURRENT LEXICON_VERSION. Same shape as sources.assert_approved().

Two modes:
  python -m pipeline.lexicon_audit --static    # no corpus, no network. THE GATE.
  python -m pipeline.lexicon_audit --corpus    # firing rates on ingested text. Later.

HISTORY: an earlier version of this module referenced constants and manifest keys that
no longer exist, so it raised AttributeError on contact — and, worse, printed
"LEXICON CLEAN" unconditionally regardless of its own numbers. It could not run, and if
it had, it would have rubber-stamped. Rewritten 2026-08-20.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date

from . import config
from .ingest import lexicon

AUDIT_PATH = config.DATA_DIR / "lexicon_audit.json"

# The axes the engine must be ABLE to report. Keys are the brief-facing names used in
# conversation; values are the AXIS_TERMS keys they must resolve to.
#
# This is a COVERAGE check, not a frequency target. It asserts the instrument has a
# channel for each cause — never that any cause is actually present in the corpus.
# What the corpus says is the corpus's business.
REQUIRED_AXES: dict[str, str] = {
    "price": "Price",
    "fit": "Fit",
    "quality": "Quality",
    "decision-fatigue": "Decision fatigue",
    "forgetting": "Forgetting",
}

MIN_TERMS_PER_AXIS = 5      # below this an axis is present in name only
BALANCE_WARN_RATIO = 4.0    # max/min axis term count above this -> WARN (not FAIL)

# Single tokens common enough in ordinary English that they fire far above their
# term-count weight. Listed so the skew is visible, not auto-corrected.
GENERIC_WATCHLIST = {
    "sale", "deal", "budget", "worth it", "look", "style", "model", "shade",
    "wash", "size", "fit", "price", "return", "returns", "colour", "color",
    "quality", "material", "cloth", "formal", "casual", "party", "interview",
}


def hr(t: str) -> None:
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---- static mode -------------------------------------------------------------------

def _axis_shape() -> dict[str, dict]:
    """Per-axis term count, single-vs-multiword split, and generic-token flags."""
    out = {}
    for axis, terms in lexicon.AXIS_TERMS.items():
        single = [t for t in terms if " " not in t]
        generic = sorted(set(t for t in terms if t in GENERIC_WATCHLIST))
        out[axis] = {
            "n_terms": len(terms),
            "n_single_token": len(single),
            "n_multiword": len(terms) - len(single),
            "generic": generic,
        }
    return out


def _double_counts() -> dict[str, list[str]]:
    """Axis terms that ALSO appear in the postpone/wishlist families.

    A term in two families is counted through two independent channels: the record
    fires `postpone` AND the axis. An axis carrying such terms is structurally
    over-weighted relative to one that does not, before any text is read.
    """
    postpone = {p.lower() for p in lexicon.POSTPONE_PHRASES}
    wishlist = {w.lower() for w in lexicon.WISHLIST_TERMS}
    hits: dict[str, list[str]] = {}
    for axis, terms in lexicon.AXIS_TERMS.items():
        dupes = []
        for t in terms:
            tl = t.lower()
            if any(tl in p or p in tl for p in postpone):
                dupes.append(f"{t} ~ POSTPONE")
            if any(tl in w or w in tl for w in wishlist):
                dupes.append(f"{t} ~ WISHLIST")
        if dupes:
            hits[axis] = dupes
    return hits


def _postpone_lean() -> dict[str, list[str]]:
    """Classify POSTPONE_PHRASES by the axis each one implies.

    This is the asymmetry that matters most: a price-implying postpone phrase resolves
    to (postpone + Price axis) and is counted twice, while a decision-fatigue phrase
    resolved to (postpone + no axis) and vanished from axis reporting entirely until
    the Decision fatigue axis was added in 2026-08-20.2.
    """
    buckets: dict[str, list[str]] = {"price-implying": [], "decision-fatigue": [],
                                     "time-only (no axis)": []}
    price_markers = ("sale", "price", "salary", "discount")
    fatigue_markers = ("decide", "confused", "torn", "fence", "second thoughts",
                       "hesitant", "not sure")
    for p in lexicon.POSTPONE_PHRASES:
        pl = p.lower()
        if any(m in pl for m in price_markers):
            buckets["price-implying"].append(p)
        elif any(m in pl for m in fatigue_markers):
            buckets["decision-fatigue"].append(p)
        else:
            buckets["time-only (no axis)"].append(p)
    return buckets


def static_audit(verbose: bool = True) -> dict:
    shape = _axis_shape()
    counts = {a: s["n_terms"] for a, s in shape.items()}

    axis_results = {}
    for label, axis_key in REQUIRED_AXES.items():
        present = axis_key in lexicon.AXIS_TERMS
        n = counts.get(axis_key, 0)
        ok = present and n >= MIN_TERMS_PER_AXIS
        axis_results[label] = {"axis": axis_key, "present": present,
                               "n_terms": n, "pass": ok}

    passed = all(r["pass"] for r in axis_results.values())
    ratio = (max(counts.values()) / min(counts.values())) if counts else 0.0

    if verbose:
        hr(f"LEXICON STATIC AUDIT — version {lexicon.LEXICON_VERSION}")

        print("\n#1  PER-AXIS SHAPE  (term count is authorship, not evidence)")
        print(f"  {'axis':<20} {'terms':>6} {'1-tok':>6} {'multi':>6}   generic tokens")
        for axis in sorted(shape, key=lambda a: -shape[a]["n_terms"]):
            s = shape[axis]
            g = ", ".join(s["generic"]) if s["generic"] else "—"
            print(f"  {axis:<20} {s['n_terms']:>6} {s['n_single_token']:>6} "
                  f"{s['n_multiword']:>6}   {g[:44]}")
        print(f"\n  total terms: {sum(counts.values())}   "
              f"max/min ratio: {ratio:.1f}  (warn above {BALANCE_WARN_RATIO})")

        print("\n#2  DOUBLE-COUNT CHANNELS  (term lives in an axis AND another family)")
        dc = _double_counts()
        if dc:
            for axis, dupes in dc.items():
                print(f"  {axis:<20} {len(dupes)} overlap(s)")
                for d in dupes[:6]:
                    print(f"      {d}")
        else:
            print("  none")

        print("\n#3  POSTPONE_PHRASES LEAN  (which axis each postpone phrase implies)")
        lean = _postpone_lean()
        for bucket, phrases in lean.items():
            print(f"  {bucket:<24} {len(phrases):>3}   {', '.join(phrases[:5])[:46]}")
        print("\n  Read: phrases in an axis-bearing bucket are counted twice; phrases in")
        print("  'time-only' resolve to postpone with NO axis and are invisible to any")
        print("  axis tally. That asymmetry is a property of this file, not the corpus.")

        print(f"\n#4  REQUIRED-AXIS COVERAGE  (>= {MIN_TERMS_PER_AXIS} terms to pass)")
        for label, r in axis_results.items():
            mark = "PASS" if r["pass"] else "FAIL"
            print(f"  {mark:<6} {label:<18} -> AXIS_TERMS[{r['axis']!r}]  "
                  f"{r['n_terms']} terms" + ("" if r["present"] else "   AXIS MISSING"))

        hr("VERDICT")
        if passed:
            print("  PASS — every required axis has a channel. The instrument can")
            print("  REPORT each cause. It says nothing about whether any is present.")
        else:
            missing = [l for l, r in axis_results.items() if not r["pass"]]
            print(f"  FAIL — no channel for: {', '.join(missing)}")
            print("  The engine would report 0% for these and you could not tell that")
            print("  apart from genuine absence. Ingest is blocked until fixed.")
        if ratio > BALANCE_WARN_RATIO:
            print(f"\n  WARN — axis term counts are unbalanced ({ratio:.1f}x). Frequencies")
            print("  from this lexicon are already barred from being findings; treat any")
            print("  axis tally as attention-allocation only. Clusters carry the taxonomy.")

    return {
        "lexicon_version": lexicon.LEXICON_VERSION,
        "run_on": _date.today().isoformat(),
        "passed": passed,
        "axes": axis_results,
        "term_counts": counts,
        "balance_ratio": round(ratio, 2),
        "double_count_axes": sorted(_double_counts()),
        "postpone_lean": {k: len(v) for k, v in _postpone_lean().items()},
    }


def record_static(result: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")


def load_static() -> dict | None:
    if not AUDIT_PATH.exists():
        return None
    try:
        return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class AxisCoverageError(RuntimeError):
    """Raised when ingest is attempted with an unaudited or failing lexicon."""


def assert_axis_coverage() -> dict:
    """Refuse ingest unless the static audit passed against the CURRENT lexicon.

    Called by scrapers before spending quota. A stale record (audited against an older
    LEXICON_VERSION) is treated as no record: the whole point is that the axes present
    at scrape time are the axes that were checked.
    """
    rec = load_static()
    if rec is None:
        raise AxisCoverageError(
            "lexicon static audit has not been run. Refusing to ingest.\n"
            "  Run:  python -m pipeline.lexicon_audit --static\n"
            "  An unaudited lexicon reports 0% for axes it has no terms for, and that\n"
            "  is indistinguishable from the cause being absent from the corpus."
        )
    if rec.get("lexicon_version") != lexicon.LEXICON_VERSION:
        raise AxisCoverageError(
            f"lexicon audit is STALE: recorded against {rec.get('lexicon_version')!r}, "
            f"current is {lexicon.LEXICON_VERSION!r}. Refusing to ingest.\n"
            f"  Re-run:  python -m pipeline.lexicon_audit --static"
        )
    if not rec.get("passed"):
        failed = [l for l, r in rec.get("axes", {}).items() if not r.get("pass")]
        raise AxisCoverageError(
            f"lexicon audit FAILED for: {', '.join(failed)}. Refusing to ingest.\n"
            f"  The instrument has no channel for these causes. Add terms to "
            f"lexicon.AXIS_TERMS, bump LEXICON_VERSION, re-run the audit."
        )
    return rec


# ---- corpus mode -------------------------------------------------------------------

def corpus_audit(date: str | None = None) -> int:
    """Firing rates over ingested text. Post-ingest only."""
    from . import cache, corpus as corpus_mod

    date = date or corpus_mod.latest_date()
    if date is None:
        print("no ingested corpus found — run ingest first, or use --static")
        return 1
    rows = corpus_mod.load_corpus(date)
    if not rows:
        print(f"corpus for {date} is empty")
        return 1

    hr(f"LEXICON CORPUS AUDIT — {date}  n={len(rows)}")

    print("\n  PER-STAGE RETENTION")
    print(f"  {'app':<16} {'raw':>8} {'usable':>8} {'ret%':>7}")
    for app in config.APPS:
        try:
            m = cache.load_manifest(app, date)
        except (FileNotFoundError, OSError):
            continue
        print(f"  {app:<16} {m.get('raw_scraped', 0):>8} {m.get('usable', 0):>8} "
              f"{m.get('retention_pct', 0.0):>7.1f}")

    from collections import Counter
    axis_hits: Counter = Counter()
    n_wishlist = n_postpone = n_vetoed = 0
    for r in rows:
        d = lexicon.flag_detailed(r.get("text", ""))
        axis_hits.update(d["axes"])
        n_wishlist += bool(d["wishlist"])
        n_postpone += bool(d["postpone"])
        n_vetoed += d.get("postpone_vetoed", 0)

    n = len(rows)
    print(f"\n  AXIS FIRING RATES  — ATTENTION ALLOCATION ONLY, NOT A FINDING")
    for axis, c in axis_hits.most_common():
        print(f"  {axis:<20} {c:>6}  {100 * c / n:>5.1f}%")
    print(f"\n  wishlist language     {n_wishlist:>6}  {100 * n_wishlist / n:>5.1f}%")
    print(f"  postpone (kept)       {n_postpone:>6}  {100 * n_postpone / n:>5.1f}%")
    print(f"  postpone vetoed       {n_vetoed:>6}  content-postponement removed "
          f"(FLOOR, not total — trailing-window veto only)")
    print("\n  Relative axis rates reflect this lexicon's authorship as much as the")
    print("  corpus. Cause frequency comes from cluster sizes, never from this table.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--static", action="store_true",
                   help="instrument check; no corpus needed. THE PRE-INGEST GATE.")
    g.add_argument("--corpus", action="store_true",
                   help="firing rates over ingested text (post-ingest)")
    ap.add_argument("--date", default=None, help="corpus mode: cache date partition")
    args = ap.parse_args(argv)

    if args.corpus:
        return corpus_audit(args.date)

    result = static_audit()
    record_static(result)
    print(f"\n  recorded -> {AUDIT_PATH}")
    if not result["passed"]:
        print("  ingest remains BLOCKED until every required axis passes.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
