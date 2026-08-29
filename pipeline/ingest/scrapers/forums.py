"""Forum orchestrator (§6, docs/forum-ingestion-plan.md) — a separate DEPTH corpus.

Combines two sources into store="forum" raw records (never mixed into clustering):
  1. Reddit  — free public JSON (reddit.py); the backbone.
  2. Firecrawl aggregators — MouthShut / ConsumerComplaints brand pages (seed URLs)
     + a bounded discovery search; the fallback for depth Reddit's JSON won't return.

Everything is bounded: Reddit is free but query-capped; Firecrawl is hard-capped at
config.FORUM_FIRECRAWL_CAP total scrapes, and every URL is cached so re-runs never
re-crawl/re-bill. Every query, URL and yield is logged to a forum manifest — if yield
is poor we record it as poor (§6), never pad. Skips cleanly when a source is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from ... import config
from . import raw_record, reddit

log = logging.getLogger(__name__)


def _source_type(url: str) -> str:
    u = (url or "").lower()
    if "mouthshut" in u:
        return "mouthshut"
    if "consumercomplaints" in u:
        return "consumercomplaints"
    if "reddit.com" in u:
        return "reddit"
    return "web"


def _relevant(title: str, snippet: str) -> bool:
    blob = f"{title} {snippet}".lower()
    return any(b in blob for b in reddit._BRANDS) and any(s in blob for s in reddit._SIGNALS)


def _page_primary_brand(text: str) -> str | None:
    """Dominant brand on an aggregator page (>=3 word-boundary hits), else None."""
    tl = text.lower()
    counts = {app: len(re.findall(rf"\b{tok}\b", tl)) for app, tok in reddit._BRAND_TOKENS.items()}
    app = max(counts, key=counts.get)
    return app if counts[app] >= 3 else None


def _chunk_paragraphs(text: str, target: int = 1400, cap: int = 40) -> list[str]:
    """Greedily pack paragraphs into ~target-char review-sized windows (bounded)."""
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if buf and len(buf) + len(p) + 2 > target:
            chunks.append(buf)
            buf = p
            if len(chunks) >= cap:
                return chunks
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf and len(chunks) < cap:
        chunks.append(buf)
    return chunks


_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def _clean_md(text: str) -> str:
    """Flatten markdown links/images ([label](url) -> label) — cleaner for quotes and
    drops the URLs (which PII-scrub would strip anyway)."""
    return _MD_LINK.sub(r"\1", text)


def _emit_page_chunks(text: str, url: str, source_type: str) -> list[dict]:
    """Split a brand aggregator page into review-sized records under its dominant brand.

    Aggregator pages are brand-specific, so we attribute every chunk to the page's
    dominant brand (avoids sidebar/compare-widget cross-tagging) and keep only
    review-like chunks (>=12 words that name the brand or carry >=2 category signals).
    """
    brand = _page_primary_brand(text)
    if not brand:
        return []
    text = _clean_md(text)
    tok = reddit._BRAND_TOKENS[brand]
    tid = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    out: list[dict] = []
    for i, chunk in enumerate(_chunk_paragraphs(text)):
        low = chunk.lower()
        if len(chunk.split()) < 12:        # too short to be a review (nav/menu fragment)
            continue
        if not (re.search(rf"\b{tok}\b", low) or sum(1 for s in reddit._SIGNALS if s in low) >= 2):
            continue
        out.append(raw_record(
            app=brand, store="forum", text=chunk[: config.FORUM_TEXT_MAX_CHARS], rating=None,
            posted_date=None, ext_id=f"{tid}:{i}", source_url=url, source_type=source_type,
            source_detail=None, multi_brand=False, thread_id=tid,
        ))
    return out


def _fc_cache_path(url: str):
    d = config.FORUM_DIR / "firecrawl"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}.json"


def _fc_scrape(fc, url: str, meta: dict) -> str | None:
    """Firecrawl a URL with caching. Returns markdown text or None. Cache hits are free."""
    p = _fc_cache_path(url)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("text", "") or None
        except ValueError:
            pass
    if meta["scrapes_used"] >= config.FORUM_FIRECRAWL_CAP:
        meta["cap_hit"] = True
        return None
    try:
        page = fc.scrape_url(url, formats=["markdown"])
    except Exception as e:  # noqa: BLE001 — SDK raises a variety of transport errors
        log.warning("Firecrawl scrape failed %s: %s", url, e)
        meta["errors"] += 1
        return None
    meta["scrapes_used"] += 1
    text = (page.get("markdown") if isinstance(page, dict) else getattr(page, "markdown", "")) or ""
    p.write_text(json.dumps({"url": url, "text": text}), encoding="utf-8")
    return text.strip() or None


def _fc_search(fc, query: str, meta: dict) -> list[str]:
    """Discover candidate URLs for a query, keeping only relevant ones."""
    try:
        results = fc.search(query, limit=8)
    except Exception as e:  # noqa: BLE001
        log.warning("Firecrawl search failed for %r: %s", query, e)
        meta["errors"] += 1
        return []
    items = getattr(results, "data", None)
    if items is None and hasattr(results, "get"):
        items = results.get("data", [])
    urls = []
    for item in items or []:
        url = (item.get("url") if isinstance(item, dict) else getattr(item, "url", None)) or ""
        title = (item.get("title") if isinstance(item, dict) else getattr(item, "title", "")) or ""
        snippet = (item.get("description") if isinstance(item, dict) else getattr(item, "description", "")) or ""
        if url and _relevant(title, snippet):
            urls.append(url)
        elif url:
            log.info("Forum gate rejected (no brand+signal): %s", url)
    return urls


def _firecrawl_aggregators(meta: dict) -> list[dict]:
    """Seed brand pages + discovery search -> Firecrawl -> per-brand tagged records."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        log.warning("Firecrawl aggregators skipped: firecrawl-py not installed.")
        return []

    fc = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
    out: list[dict] = []
    seen_urls: set[str] = set()

    # 1. Verified seed brand pages — crawl directly, no search.
    candidate_urls = list(config.FORUM_SEED_URLS)
    # 2. Discover the rest (other brand pages, comparison threads) via bounded search.
    for query in config.FORUM_AGG_QUERIES:
        if meta["scrapes_used"] >= config.FORUM_FIRECRAWL_CAP:
            meta["cap_hit"] = True
            break
        candidate_urls += _fc_search(fc, query, meta)

    for url in candidate_urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if meta["scrapes_used"] >= config.FORUM_FIRECRAWL_CAP:
            meta["cap_hit"] = True
            break
        text = _fc_scrape(fc, url, meta)
        if not text:
            continue
        meta["urls"].append(url)
        recs = _emit_page_chunks(text, url, _source_type(url))
        if not recs:
            log.info("Forum yielded no brand-tagged chunks: %s", url)
        out += recs

    log.info("Firecrawl aggregators: %d records from %d scraped URLs (cap %d, used %d)",
             len(out), len(meta["urls"]), config.FORUM_FIRECRAWL_CAP, meta["scrapes_used"])
    return out


def _write_manifest(records: list[dict], reddit_meta: dict, fc_meta: dict) -> None:
    from collections import Counter

    config.FORUM_DIR.mkdir(parents=True, exist_ok=True)
    by_app = Counter(r["app"] for r in records)
    by_source = Counter(r.get("source_type") for r in records)
    unique_threads = len({r.get("thread_id") for r in records})
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records_total": len(records),
        "unique_threads": unique_threads,
        "multi_brand_records": sum(1 for r in records if r.get("multi_brand")),
        "by_app": dict(by_app),
        "by_source_type": dict(by_source),
        "reddit": reddit_meta,
        "firecrawl": fc_meta,
    }
    (config.FORUM_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Forum manifest -> %s (%d records, %d unique threads)",
             config.FORUM_DIR / "manifest.json", len(records), unique_threads)


def scrape(queries: list[str] | None = None) -> list[dict]:
    """Cross-app forum pull: Reddit (free) + Firecrawl aggregators (if key). Bounded + logged."""
    records: list[dict] = []

    reddit_meta: dict = {}
    try:
        records += reddit.scrape(reddit_meta)
    except Exception as e:  # noqa: BLE001 — a forum source must never break ingestion (§6)
        log.warning("Reddit source failed: %s", e)
        reddit_meta["error"] = str(e)

    fc_meta = {"enabled": bool(config.FIRECRAWL_API_KEY), "scrapes_used": 0,
               "cap": config.FORUM_FIRECRAWL_CAP, "urls": [], "errors": 0, "cap_hit": False}
    if config.FIRECRAWL_API_KEY:
        try:
            records += _firecrawl_aggregators(fc_meta)
        except Exception as e:  # noqa: BLE001
            log.warning("Firecrawl aggregators failed: %s", e)
            fc_meta["error"] = str(e)
    else:
        log.info("Firecrawl aggregators skipped: FIRECRAWL_API_KEY unset (Reddit still ran).")

    _write_manifest(records, reddit_meta, fc_meta)
    log.info("Forums: %d records total (%d apps)", len(records),
             len({r["app"] for r in records}))
    return records
