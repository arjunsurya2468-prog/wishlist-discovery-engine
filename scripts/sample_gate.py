"""STEP 8 — per-source sample gate. Run BEFORE any full ingestion.

Pulls a small sample (default 75) from ONE source and reports what fraction of it
actually contains wishlist-relevant content. You then decide, per source, whether to
run a full scrape or drop the source.

Why this gate exists: the expensive failure on this project is not a scraper that
breaks, it is a scraper that works perfectly and returns 10,000 records of the wrong
kind of talk. That cost is only visible after embedding and clustering, by which point
the money and the days are gone. A 75-record sample answers it in a minute.

    python -m scripts.sample_gate --source play --app Myntra
    python -m scripts.sample_gate --source reddit          # once reddit.py is rebuilt

This script NEVER writes to the corpus cache. It samples, measures, prints, exits.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from pipeline import config, sources
from pipeline.ingest import lexicon
from pipeline.ingest.normalize import normalize_corpus

# Sources whose scraper is confirmed working for THIS brief. reddit/youtube/twitter/forum
# are deliberately absent — see STEP 5. Attempting them here fails loudly rather than
# reporting a hit-rate from a scraper that was written for a different corpus.
IMPLEMENTED = set(sources.implemented())

# What "wishlist-relevant" means for the gate. Deliberately stricter than the relevance
# lexicon flag: an axis mention alone ("the size was wrong") is a product complaint, not
# evidence of a stalled saved item. We want the deliberation talk.
def _classify(text: str) -> str:
    d = lexicon.flag_detailed(text)
    if d["wishlist"] and (d["axes"] or d["postpone"]):
        return "on_thesis"          # a saved item AND a reason it is stalled
    if d["wishlist"] or d["postpone"]:
        return "adjacent"           # deliberation language, no explicit axis
    if d["axes"]:
        return "axis_only"          # product feedback about an axis, no save/stall framing
    return "off_thesis"


# Sources whose unit of work is a query, not an app — see run.CROSS_APP_SOURCES.
# For these, --app filters AFTER emission rather than selecting what to pull.
CROSS_APP = {"reddit", "youtube", "twitter", "forum"}


def _sample_cross_app(source: str, app_key: str | None, n: int,
                      queries: list | None = None) -> tuple[list[dict], dict]:
    """Pull a community sample. Writes under <source>/<date>/_sample/, never a corpus dir."""
    if source == "youtube":
        from pipeline.ingest.scrapers import youtube
        raw, meta = youtube.sample(n, queries=queries)
    elif source == "reddit":
        from pipeline.ingest.scrapers import reddit
        raw, meta = reddit.sample(n, queries=queries)
    else:
        raise SystemExit(f"cross-app sampler for {source!r} is not built yet.")

    if app_key:
        raw = [r for r in raw if r.get("app") == app_key]

    # normalize_corpus is per-app and order-preserving, so normalizing each app's slice
    # keeps the video-stratified ordering built by youtube.sample(), and interleaving
    # the results round-robin keeps both apps represented in the first n.
    by_app: dict[str, list[dict]] = {}
    for r in raw:
        by_app.setdefault(r["app"], []).append(r)

    normalized: dict[str, list] = {}
    for app, recs in by_app.items():
        reviews, _stats = normalize_corpus(app, recs)
        normalized[app] = reviews

    rows: list[dict] = []
    apps = sorted(normalized)
    for i in range(max((len(v) for v in normalized.values()), default=0)):
        for app in apps:
            if i < len(normalized[app]):
                r = normalized[app][i]
                rows.append({"app": app, "text": r.text,
                             "video": r.thread_id, "channel": r.source_detail})
    meta["raw_records"] = len(raw)
    meta["usable_records"] = sum(len(v) for v in normalized.values())
    return rows[:n], meta


def sample(source: str, app_key: str | None, n: int,
           queries: list | None = None) -> tuple[list[dict], dict]:
    if source not in IMPLEMENTED:
        raise SystemExit(
            f"source {source!r} has no scraper built for this brief yet (STEP 5).\n"
            f"  Implemented: {sorted(IMPLEMENTED)}\n"
            f"  Do not infer a hit-rate from the previous build's scraper — it was "
            f"written against a different corpus and a different query strategy."
        )
    if source in CROSS_APP:
        return _sample_cross_app(source, app_key, n, queries)

    specs = config.apps_for(source)
    if app_key:
        specs = [s for s in specs if s.key == app_key]
        if not specs:
            raise SystemExit(f"{app_key!r} is not valid for source {source!r} "
                             f"(valid: {[s.key for s in config.apps_for(source)]})")

    unverified = config.verify_app_ids()
    rows: list[dict] = []
    for spec in specs:
        if spec.key in unverified:
            print(f"  ⚠️  {spec.key}: store IDs unverified — a wrong id returns an empty "
                  f"scrape that looks like 'no results'. Verify before trusting a 0% rate.")
        if source == "play":
            from pipeline.ingest.scrapers import play_store
            raw = play_store.scrape(spec, target=n)
        else:
            from pipeline.ingest.scrapers import app_store
            # app_store paginates ~50/page; ceil to cover n without overshooting much.
            raw = app_store.scrape(spec, max_pages=max(1, -(-n // 50)))
        reviews, _stats = normalize_corpus(spec.key, raw[:n])
        rows.extend({"app": spec.key, "text": r.text} for r in reviews)
    return rows, {}


def report(source: str, rows: list[dict], meta: dict | None = None) -> tuple[int, float]:
    print("\n" + "=" * 74)
    print(f"STEP 8 SAMPLE GATE — source={source}  n={len(rows)}")
    print("=" * 74)
    if not rows:
        print("\n  NO RECORDS RETURNED. This is not a 0% hit-rate — it is a broken pull.")
        print("  Check the store IDs (config.verify_app_ids()) before concluding anything.")
        return 1, 0.0

    buckets = Counter(_classify(r["text"]) for r in rows)
    n = len(rows)
    on = buckets["on_thesis"]
    adj = buckets["adjacent"]

    for label, desc in [
        ("on_thesis",  "saved item AND a stated reason it is stalled"),
        ("adjacent",   "deliberation language, no explicit uncertainty axis"),
        ("axis_only",  "product feedback on an axis, no save/stall framing"),
        ("off_thesis", "neither"),
    ]:
        c = buckets[label]
        print(f"  {label:<12} {c:>5}  {100*c/n:>5.1f}%   {desc}")

    hit = 100 * (on + adj) / n
    strict = 100 * on / n
    print(f"\n  HIT-RATE (on_thesis + adjacent): {hit:.1f}%")
    print(f"  STRICT   (on_thesis only):       {strict:.1f}%")
    print("  Report BOTH. On a YouTube corpus HIT-RATE runs high on generic postponement")
    print("  language; STRICT is the conservative read. Decide on neither until the")
    print("  lexicon axis-coverage audit has been read (pipeline.lexicon_audit --static).")

    meta = meta or {}
    if meta:
        q = meta.get("quota_units", 0)
        print("\n  PROVENANCE")
        print(f"    queries {meta.get('queries', 0)} · videos {meta.get('videos_in_sample', 0)}"
              f" · raw comments {meta.get('comments_raw', 0)}"
              f" · raw records {meta.get('raw_records', 0)}"
              f" · usable {meta.get('usable_records', 0)}")
        if meta.get("raw_records"):
            ret = 100 * meta.get("usable_records", 0) / meta["raw_records"]
            print(f"    retention {ret:.1f}% after WORD_FLOOR={config.WORD_FLOOR}")
        if q:
            print(f"    quota {q} units ({100 * q / 10000:.1f}% of daily 10,000) · "
                  f"search calls {meta.get('search_calls', 0)}")
        vetoed = sum(lexicon.flag_detailed(r["text"]).get("postpone_vetoed", 0)
                     for r in rows)
        print(f"    postpone hits vetoed as content-postponement: {vetoed}  "
              f"(FLOOR not total — trailing-window veto only)")
        print(f"    comments-disabled {meta.get('comments_disabled', 0)} · "
              f"errors {meta.get('errors', 0)}"
              + (f" · STOPPED EARLY: {meta['stopped_early']}"
                 if meta.get("stopped_early") else ""))

    # Per-QUERY split. Two seed queries can reach entirely different venues — a
    # retrospective framing ("what i actually bought") may pull creators whose audience
    # narrates decisions, while a generic haul query pulls reaction comments. Averaged
    # together that difference is invisible, and it is exactly the difference that
    # decides whether the seed set works.
    vq = (meta or {}).get("video_query", {})
    if vq and any(r.get("video") for r in rows):
        by_query: dict[str, list[dict]] = {}
        for r in rows:
            by_query.setdefault(vq.get(r.get("video"), "?"), []).append(r)
        print("\n  PER-QUERY ON-THESIS SPLIT  (does retrospective framing reach a different venue?)")
        print(f"    {'n':>4} {'on':>4} {'adj':>4} {'on%':>6}  query")
        for qy, rs in sorted(by_query.items(), key=lambda kv: -len(kv[1])):
            onq = sum(_classify(x["text"]) == "on_thesis" for x in rs)
            adjq = sum(_classify(x["text"]) == "adjacent" for x in rs)
            print(f"    {len(rs):>4} {onq:>4} {adjq:>4} {100*onq/len(rs):>5.1f}%  {qy[:52]}")
        for qy in (meta or {}).get("queries_used", []):
            if qy not in by_query:
                print(f"    {0:>4} {0:>4} {0:>4} {'—':>6}  {qy[:52]}  (no videos survived dedupe)")

    # Per-video split. A haul-farm channel and a genuine review channel can return the
    # same record count and wildly different on-thesis rates; averaging them hides that.
    if any(r.get("video") for r in rows):
        by_video: dict[str, list[dict]] = {}
        for r in rows:
            by_video.setdefault(r.get("video") or "?", []).append(r)
        titles = (meta or {}).get("video_titles", {})
        print("\n  PER-VIDEO ON-THESIS SPLIT  (farm vs genuine is visible here, not in the mean)")
        print(f"    {'video':<13} {'n':>4} {'on':>4} {'on%':>6}  channel / title")
        for vid, rs in sorted(by_video.items(),
                              key=lambda kv: -sum(_classify(x["text"]) == "on_thesis"
                                                  for x in kv[1])):
            onv = sum(_classify(x["text"]) == "on_thesis" for x in rs)
            label = (rs[0].get("channel") or "")[:20] or titles.get(vid, "")[:20]
            print(f"    {vid:<13} {len(rs):>4} {onv:>4} {100 * onv / len(rs):>5.1f}%  {label}")

    print("\n  SAMPLE OF ON-THESIS RECORDS:")
    shown = [r for r in rows if _classify(r["text"]) == "on_thesis"][:3]
    for r in shown:
        print(f"    [{r['app']}] {r['text'][:150]}")
    if not shown:
        print("    (none — read a few off_thesis records by hand before deciding)")

    print("\n  This is a REPORT, not a decision. Full scrape or drop is the user's call.")
    print(f"  Record it:  python -m scripts.sample_gate --source {source} "
          f"--approve|--drop --note '...'")
    return 0, hit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, choices=sorted(sources.SOURCES))
    ap.add_argument("--app", default=None, help="limit to one app key")
    ap.add_argument("-n", type=int, default=75, help="sample size (50-100 recommended)")
    ap.add_argument("--queries", default=None,
                    help="cross-app sources: EXPLICIT seed-query selection, comma-separated "
                         "1-based indices into the approved seed set (e.g. '4,5,8'). "
                         "Omitted = an even spread across the seed set, never a prefix.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--approve", action="store_true",
                   help="record a FULL SCRAPE decision for this source")
    g.add_argument("--drop", action="store_true",
                   help="record a DROP decision for this source")
    ap.add_argument("--note", default="", help="rationale, stored with the decision")
    ap.add_argument("--hit-rate", type=float, default=None,
                    help="record a decision from an offline/manual sample without re-pulling")
    args = ap.parse_args()

    # Manual/offline decision path: record a hit-rate measured by hand (e.g. a source
    # with no scraper, sampled in a browser). Keeps every source's call in one ledger.
    if args.hit_rate is not None:
        if not (args.approve or args.drop):
            ap.error("--hit-rate requires --approve or --drop")
        d = sources.record_decision(args.source, approved=args.approve,
                                    hit_rate=args.hit_rate, sample_n=args.n, note=args.note)
        print(f"recorded: {args.source} -> {'APPROVED' if d['approved'] else 'DROPPED'} "
              f"({d['hit_rate_pct']}% on n={d['sample_n']})")
        return 0

    qsel = [s.strip() for s in args.queries.split(",")] if args.queries else None
    rows, meta = sample(args.source, args.app, args.n, qsel)
    rc, hit = report(args.source, rows, meta)
    if rc == 0 and (args.approve or args.drop):
        d = sources.record_decision(args.source, approved=args.approve,
                                    hit_rate=hit, sample_n=args.n, note=args.note)
        print(f"\nrecorded: {args.source} -> {'APPROVED' if d['approved'] else 'DROPPED'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
