"""YouTube ingest — two-stage, quota-aware, brand-inheriting.

QUOTA ASYMMETRY IS THE WHOLE DESIGN
===================================
search.list costs 100 units. commentThreads.list costs 1. The bottleneck is therefore
VIDEO RESOLUTION, never comment volume — pulling 200 comments from a video costs 2
units, or 2% of the single search that found it.

Two consequences shape this module:

1. Stage A and Stage B are SEPARATE, and Stage A's output is persisted. Re-running
   comment collection must never re-pay 100 units/query to rediscover video ids it
   already has.
2. Keeping 50 results per search instead of 25 is nearly free. search.list bills the
   same 100 units either way, so truncating throws away results already paid for.

BRAND ATTRIBUTION IS INHERITED FROM THE VIDEO
=============================================
This is the yield-critical decision. Reddit attributes brands by scanning the record's
own text (see reddit.emit_for_brands). Applying that rule to YouTube comments would
discard most of the corpus: a comment under a Myntra haul says "the third one is so
pretty, been eyeing it for weeks" — deliberation, on-thesis, and it never says
"Myntra". The VIDEO carries the brand context; the comment inherits it.

A comment naming a DIFFERENT brand adds that brand rather than replacing it, and both
records share thread_id=videoId so the cross-brand comparison is not double-counted.

Nykaa Fashion is excluded structurally via config.apps_for("youtube") — "nykaa" in
community text is overwhelmingly the beauty vertical. Never add it back here by hand.
"""
from __future__ import annotations

import json
import logging
import re
import time

import requests

from ... import config
from ...lexicon_audit import assert_axis_coverage
from . import raw_record

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"
SOURCE = "youtube"

SEARCH_UNITS = 100      # per search.list call
COMMENT_UNITS = 1       # per commentThreads.list call
VIDEO_UNITS = 1         # per videos.list call (up to 50 ids batched)

DAILY_QUOTA = 10_000    # default project allowance, for reporting only


class QuotaExhausted(RuntimeError):
    """Raised when the API reports the daily quota is gone.

    Distinct from an ordinary error because the remedy is a CALENDAR DAY, not a retry:
    YouTube quota resets at midnight Pacific. On this deadline that is the expensive
    failure, which is why config.YOUTUBE_MAX_SEARCH_CALLS caps spend before the API
    ever has to say no.
    """


def _new_meta() -> dict:
    return {"quota_units": 0, "search_calls": 0, "comment_calls": 0, "video_calls": 0,
            "queries": 0, "videos_resolved": 0, "comments_raw": 0,
            "comments_disabled": 0, "errors": 0, "per_query": {}, "stopped_early": None}


# ---- brand attribution -------------------------------------------------------------

def _brand_tokens() -> dict[str, str]:
    return {spec.key: "|".join(spec.community_terms)
            for spec in config.apps_for(SOURCE) if spec.community_terms}


def brands_in(text: str) -> list[str]:
    """Apps named in a piece of text (word-boundary)."""
    t = (text or "").lower()
    return [app for app, tok in _brand_tokens().items()
            if re.search(rf"\b(?:{tok})\b", t)]


# ---- HTTP ---------------------------------------------------------------------------

def _get(endpoint: str, params: dict, meta: dict, units: int) -> dict | None:
    if not config.YOUTUBE_API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY is unset. config.py loads .env (NOT .env.example), so the "
            "key must be in a .env file at the repo root. It is the only variable "
            "YouTube ingest requires."
        )
    try:
        r = requests.get(f"{API}/{endpoint}",
                         params=dict(params, key=config.YOUTUBE_API_KEY), timeout=30)
    except requests.RequestException as e:
        meta["errors"] += 1
        log.warning("youtube %s: transport error: %s", endpoint, e)
        return None

    meta["quota_units"] += units
    if r.status_code == 200:
        return r.json()

    body = {}
    try:
        body = r.json()
    except ValueError:
        pass
    errs = (body.get("error", {}).get("errors") or [{}])
    reason = errs[0].get("reason", "")

    if reason in ("commentsDisabled",):
        meta["comments_disabled"] += 1
        return None
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        meta["stopped_early"] = f"quota: {reason}"
        raise QuotaExhausted(
            f"YouTube quota exhausted ({reason}) after {meta['quota_units']} units this "
            f"run. Quota resets at midnight Pacific — this costs a day, not a retry."
        )
    meta["errors"] += 1
    log.warning("youtube %s: HTTP %s reason=%s", endpoint, r.status_code, reason or "?")
    return None


# ---- Stage A: resolve video ids ------------------------------------------------------

def resolve_videos(queries: list[str] | None = None, *, date: str | None = None,
                   max_per_query: int | None = None, meta: dict | None = None,
                   persist: bool = True, subdir: str = "") -> list[dict]:
    """Resolve seed queries to a deduped video list. THE EXPENSIVE STAGE.

    Calls assert_axis_coverage() first: an unaudited lexicon reports 0% for axes it
    has no terms for, and that is indistinguishable from the cause being absent. There
    is no point spending 100 units a query to fill a corpus an instrument cannot read.
    """
    assert_axis_coverage()

    date = date or config.today_str()
    meta = meta if meta is not None else _new_meta()
    queries = list(queries if queries is not None else config.YOUTUBE_VIDEO_QUERIES)
    keep = max_per_query or config.YOUTUBE_MAX_VIDEOS_PER_QUERY

    seen: dict[str, dict] = {}
    for q in queries:
        if meta["search_calls"] >= config.YOUTUBE_MAX_SEARCH_CALLS:
            meta["stopped_early"] = (
                f"hit YOUTUBE_MAX_SEARCH_CALLS={config.YOUTUBE_MAX_SEARCH_CALLS}")
            log.warning("youtube: %s — remaining queries skipped", meta["stopped_early"])
            break

        meta["queries"] += 1
        meta["search_calls"] += 1
        data = _get("search", {
            "q": q, "part": "id,snippet", "type": "video", "regionCode": "IN",
            "relevanceLanguage": "en", "order": "relevance",
            "maxResults": min(50, keep),
        }, meta, SEARCH_UNITS)
        if not data:
            meta["per_query"][q] = 0
            continue

        found = 0
        for item in data.get("items", [])[:keep]:
            vid = (item.get("id") or {}).get("videoId")
            if not vid:
                continue
            found += 1
            if vid in seen:
                # Cross-query overlap: record the extra provenance, do not duplicate.
                seen[vid]["queries"].append(q)
                continue
            sn = item.get("snippet", {})
            # Brand from the QUERY that found it, falling back to title+description.
            brands = brands_in(q) or brands_in(f"{sn.get('title','')} {sn.get('description','')}")
            seen[vid] = {
                "video_id": vid,
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "channel_id": sn.get("channelId", ""),
                "published_at": (sn.get("publishedAt") or "")[:10],
                "description": sn.get("description", ""),
                "queries": [q],
                "brands": brands,
            }
        meta["per_query"][q] = found
        time.sleep(config.SCRAPE_PAGE_PAUSE_SEC)

    videos = list(seen.values())
    meta["videos_resolved"] = len(videos)

    if persist:
        d = config.CACHE_DIR / SOURCE / date / subdir if subdir else config.CACHE_DIR / SOURCE / date
        d.mkdir(parents=True, exist_ok=True)
        (d / "videos.json").write_text(
            json.dumps(videos, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("youtube stage A: %d videos from %d queries (%d units, %d search calls)",
             len(videos), meta["queries"], meta["quota_units"], meta["search_calls"])
    return videos


def enrich_videos(videos: list[dict], *, meta: dict) -> None:
    """Attach viewCount/commentCount in batches of 50. 1 unit per batch.

    Cheap, and it is what makes affiliate haul-farms visible in the numbers: a channel
    with high views and near-zero comments is not a deliberation venue. Diagnostic
    only — nothing filters on it.
    """
    ids = [v["video_id"] for v in videos]
    by_id = {v["video_id"]: v for v in videos}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        meta["video_calls"] += 1
        data = _get("videos", {"part": "statistics", "id": ",".join(batch)},
                    meta, VIDEO_UNITS)
        if not data:
            continue
        for item in data.get("items", []):
            st = item.get("statistics", {})
            v = by_id.get(item.get("id"))
            if v is not None:
                v["view_count"] = int(st.get("viewCount", 0) or 0)
                v["comment_count"] = int(st.get("commentCount", 0) or 0)


# ---- Stage B: comments per video id --------------------------------------------------

def fetch_comments(video_id: str, *, date: str | None = None, meta: dict,
                   per_video: int | None = None, persist: bool = True,
                   subdir: str = "") -> list[dict]:
    """Top-level comments for one video, with inline replies.

    part=snippet,replies costs the SAME 1 unit as snippet alone and returns up to 5
    replies per thread for free. Replies are where "which size did you get?" lives, so
    this is pure yield at zero marginal quota.
    """
    date = date or config.today_str()
    want = per_video or config.YOUTUBE_COMMENTS_PER_VIDEO
    out: list[dict] = []
    page = None

    while len(out) < want:
        params = {"videoId": video_id, "part": "snippet,replies",
                  "maxResults": 100, "order": "relevance", "textFormat": "plainText"}
        if page:
            params["pageToken"] = page
        meta["comment_calls"] += 1
        data = _get("commentThreads", params, meta, COMMENT_UNITS)
        if not data:
            break

        for th in data.get("items", []):
            top = ((th.get("snippet") or {}).get("topLevelComment") or {}).get("snippet", {})
            text = (top.get("textOriginal") or "").strip()
            if text:
                out.append({"id": th.get("id", ""), "text": text,
                            "date": (top.get("publishedAt") or "")[:10],
                            "likes": top.get("likeCount", 0), "is_reply": False})
            for rep in (th.get("replies") or {}).get("comments", []):
                rs = rep.get("snippet", {})
                rtext = (rs.get("textOriginal") or "").strip()
                if rtext:
                    out.append({"id": rep.get("id", ""), "text": rtext,
                                "date": (rs.get("publishedAt") or "")[:10],
                                "likes": rs.get("likeCount", 0), "is_reply": True})

        page = data.get("nextPageToken")
        if not page:
            break
        time.sleep(config.SCRAPE_PAGE_PAUSE_SEC)

    meta["comments_raw"] += len(out)
    if persist and out:
        base = config.CACHE_DIR / SOURCE / date / subdir if subdir else config.CACHE_DIR / SOURCE / date
        d = base / "comments"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{video_id}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ---- emission ------------------------------------------------------------------------

def emit(comment: dict, video: dict) -> list[dict]:
    """One raw_record per brand this comment concerns. Brand inherited from the video."""
    inherited = video.get("brands") or []
    named = brands_in(comment.get("text", ""))
    brands = sorted(set(inherited) | set(named))
    if not brands:
        return []
    multi = len(brands) > 1
    text = (comment.get("text") or "")[:config.FORUM_TEXT_MAX_CHARS]
    return [
        raw_record(
            app=b, store=SOURCE, text=text, rating=None,
            posted_date=comment.get("date") or None,
            ext_id=comment.get("id"),
            source_url=f"https://www.youtube.com/watch?v={video['video_id']}",
            source_type=SOURCE, source_detail=video.get("channel"),
            multi_brand=multi, thread_id=video["video_id"],
        )
        for b in brands
    ]


def scrape(meta: dict | None = None) -> list[dict]:
    """Cross-app entry point. ONE pull covering every app in scope for youtube."""
    date = config.today_str()
    meta = meta if meta is not None else _new_meta()

    videos = resolve_videos(date=date, meta=meta)
    if videos:
        enrich_videos(videos, meta=meta)

    out: list[dict] = []
    for v in videos:
        try:
            comments = fetch_comments(v["video_id"], date=date, meta=meta)
        except QuotaExhausted:
            log.error("youtube: quota exhausted mid-run; keeping %d records already "
                      "emitted and stopping honestly", len(out))
            break
        for c in comments:
            out += emit(c, v)

    d = config.CACHE_DIR / SOURCE / date
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log.info("youtube: %d records from %d videos / %d raw comments "
             "(%d units = %.1f%% of daily, %d comments-disabled, %d errors)",
             len(out), meta["videos_resolved"], meta["comments_raw"],
             meta["quota_units"], 100 * meta["quota_units"] / DAILY_QUOTA,
             meta["comments_disabled"], meta["errors"])
    return out


# ---- sample-gate support -------------------------------------------------------------

def resolve_query_selection(spec: list | None, *, k: int = 3) -> list[str]:
    """Turn an EXPLICIT selection into seed query strings.

    Accepts 1-based indices into config.YOUTUBE_VIDEO_QUERIES, or literal query
    strings. Strings must already be members of the approved seed set: the gate exists
    to predict what the full pull returns, so measuring a query the full pull will not
    run measures nothing useful.

    WHY THIS FUNCTION EXISTS: sample() previously did YOUTUBE_VIDEO_QUERIES[:k], which
    silently selected the three most generic haul queries and excluded the only seed
    containing "wishlist". A gate that picks its own sample positionally will
    eventually pick an unrepresentative one and report it as the source's hit-rate.
    With spec=None the fallback is an even SPREAD, never a prefix, and the chosen
    queries are always printed and recorded in meta.
    """
    seeds = list(config.YOUTUBE_VIDEO_QUERIES)
    if spec is None:
        if k >= len(seeds):
            return seeds
        step = len(seeds) / k
        return [seeds[int(i * step)] for i in range(k)]

    out: list[str] = []
    for item in spec:
        if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
            i = int(item)
            if not 1 <= i <= len(seeds):
                raise SystemExit(f"query index {i} out of range 1..{len(seeds)}")
            out.append(seeds[i - 1])
        else:
            if item not in seeds:
                raise SystemExit(
                    f"query {item!r} is not in the approved seed set. The gate may only "
                    f"sample queries the full pull will actually run.\n  Approved: "
                    + "\n            ".join(f"{i+1}. {q}" for i, q in enumerate(seeds))
                )
            out.append(item)
    return out


def sample(n: int = 75, *, queries: list | None = None,
           videos_per_query: int = 4) -> tuple[list[dict], dict]:
    """Gate sample: FEW videos at FULL depth, drawn STRATIFIED across them.

    Two deliberate choices, both about making the gate predictive of the full pull:

    - FULL depth (200/video), not shallow depth across many videos. A gate that reads
      only the top 100 comments while the full pull goes 200 deep measures a
      higher-signal slice than the pull will actually return, and its hit-rate will
      not reproduce.
    - STRATIFIED draw, round-robin across videos. Taking the first 75 records would
      measure one or two creators' comment sections, and haul channels differ enormously
      in whether their audience deliberates or just drops fire emojis.

    Writes under data/cache/youtube/<date>/_sample/ — never a corpus partition, so a
    gate pull can never be mistaken for ingested corpus.
    """
    date = config.today_str()
    meta = _new_meta()
    seeds = resolve_query_selection(queries)
    meta["queries_used"] = seeds

    videos = resolve_videos(seeds, date=date, max_per_query=videos_per_query,
                            meta=meta, subdir="_sample")

    # Primary provenance: the FIRST seed query that surfaced this video. A video found
    # by several queries is attributed once, so per-query counts sum to the video count.
    meta["video_query"] = {v["video_id"]: (v.get("queries") or [""])[0] for v in videos}

    per_video: list[list[dict]] = []
    for v in videos:
        comments = fetch_comments(v["video_id"], date=date, meta=meta,
                                  persist=True, subdir="_sample")
        recs = []
        for c in comments:
            recs += emit(c, v)
        per_video.append(recs)

    # Round-robin so every video contributes before any video contributes twice.
    rows: list[dict] = []
    for i in range(max((len(r) for r in per_video), default=0)):
        for recs in per_video:
            if i < len(recs):
                rows.append(recs[i])
    meta["videos_in_sample"] = len(videos)
    meta["records_available"] = len(rows)
    meta["per_video_records"] = {v["video_id"]: len(r) for v, r in zip(videos, per_video)}
    meta["video_titles"] = {v["video_id"]: v.get("title", "")[:60] for v in videos}

    d = config.CACHE_DIR / SOURCE / date / "_sample"
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return rows, meta
