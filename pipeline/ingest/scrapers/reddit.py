"""Reddit source — PRIMARY corpus for this brief (STEP 6).

Transport is Apify-first (config.REDDIT_TRANSPORT), with the public RSS/JSON reader
kept as an automatic fallback when Apify errors or no APIFY_API_KEY is set.

Reddit is the highest-signal source in this corpus: it gated at a 15.5% wishlist-relevance
hit-rate versus 1.5% for store reviews and 0.1% for YouTube comments (see
pipeline/sources.py for the recorded gate decisions).

Two transports, JSON preferred with an automatic RSS fallback:
  - JSON  (reddit.com/search.json) — richer, works on residential IPs.
  - RSS   (reddit.com/search.rss)  — the fallback when JSON returns 403 (Reddit blocks
    unauthenticated JSON API reads from datacenter IPs). RSS still serves the honest UA.

Comparison threads emit ONE tagged record per brand they discuss (`multi_brand` + shared
`thread_id`) so the same thread is never double-counted. Author handles/names are never
kept (blind-eval / PII). This never touches clustering — forum rows are a separate corpus.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode, urlparse

from ... import config
from . import raw_record

log = logging.getLogger(__name__)

# Brand detection. Built from config so the Nykaa Fashion community exclusion is
# STRUCTURAL — "nykaa" in community text is overwhelmingly the beauty vertical, and
# config.apps_for("reddit") is what keeps it out. Never add it back here by hand.
def _brand_tokens() -> dict[str, str]:
    return {spec.key: "|".join(spec.community_terms)
            for spec in config.apps_for("reddit") if spec.community_terms}


_SIGNALS = (
    "wishlist", "saved", "cart", "bought", "buy", "purchase", "order",
    "size", "sizing", "fit", "fabric", "quality", "return", "exchange",
    "price", "sale", "discount", "worth", "review", "haul", "vs", "compare",
)
# Behaviour terms that make the brand×term query matrix — from config so the query
# strategy lives in one place.
_TERMS = list(config.REDDIT_QUERY_TERMS)

_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_MD_DIV = re.compile(r'<div class="md">(.*?)</div>', re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


# ---- relevance + attribution (transport-agnostic) --------------------------------

def _relevant(text: str) -> bool:
    """A record is relevant if it names an in-scope platform AND carries behaviour signal.

    The behaviour half matters more here than in the previous build: a bare brand
    name-drop is noise for this brief, since the question is about deliberation, not
    brand sentiment.
    """
    blob = text.lower()
    brands = [t for spec in config.apps_for("reddit") for t in spec.community_terms]
    return any(b in blob for b in brands) and any(s in blob for s in _SIGNALS)


def brands_in(text: str, min_count: int = 1) -> list[str]:
    """Apps substantively mentioned (>= min_count word-boundary hits)."""
    t = text.lower()
    return [app for app, tok in _brand_tokens().items()
            if len(re.findall(rf"\b{tok}\b", t)) >= min_count]


def emit_for_brands(text: str, *, source_url: str, source_type: str,
                    source_detail: str | None = None, posted_date: str | None = None,
                    ext_id: str | None = None, min_count: int = 1) -> list[dict]:
    """One raw_record per brand the text discusses; tagged for no double-count."""
    full = text or ""
    brands = brands_in(full, min_count=min_count)   # detect on FULL text, not the truncated store
    if not brands:
        return []
    stored = full[: config.FORUM_TEXT_MAX_CHARS]
    multi = len(brands) > 1
    tid = ext_id or hashlib.sha256((source_url or stored[:200]).encode("utf-8")).hexdigest()[:16]
    return [
        raw_record(
            app=b, store="forum", text=stored, rating=None, posted_date=posted_date,
            ext_id=ext_id, source_url=source_url, source_type=source_type,
            source_detail=source_detail, multi_brand=multi, thread_id=tid,
        )
        for b in brands
    ]


# ---- query matrix ----------------------------------------------------------------

def _search_urls() -> list[tuple[str | None, str]]:
    """(subreddit_or_None, query) matrix, capped at REDDIT_MAX_QUERIES.

    High-value queries (comparisons, brand/complaint subs) come first so the cap never
    trims them; broad brand×term next; metro subs last.
    """
    brands = [t for spec in config.apps_for("reddit") for t in spec.community_terms]
    brand_or = " OR ".join(brands) if brands else ""

    out: list[tuple[str | None, str]] = []
    # Highest value: brand × behaviour. This is the on-thesis query shape.
    for b in brands:
        for term in _TERMS:
            out.append((None, f"{b} {term}"))
    # Behaviour-only, site-wide: catches deliberation that never names a platform.
    for term in _TERMS[:8]:
        out.append((None, f"{term} online shopping india"))
    # Per-sub sweep last — PROPOSED subs, pending the STEP 8 hit-rate gate.
    if brand_or:
        for sub in config.REDDIT_SUBS_PROPOSED:
            out.append((sub, brand_or))
    return out[: config.REDDIT_MAX_QUERIES]


# ---- shared helpers --------------------------------------------------------------

def _cache_path(key: str):
    d = config.FORUM_DIR / "reddit"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}.json"


def _iso_date(created_utc) -> str | None:
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _strip_html(content: str) -> str:
    """selftext/comment HTML -> clean text. Prefers the <div class="md"> body."""
    m = _MD_DIV.search(content or "")
    body = m.group(1) if m else (content or "")
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", body))).strip()


# ---- JSON transport --------------------------------------------------------------

def _search_endpoint(sub: str | None, query: str) -> str:
    params = {"q": query, "sort": "relevance", "t": config.REDDIT_WINDOW,
              "limit": config.REDDIT_RESULTS_PER_QUERY, "raw_json": 1}
    if sub:
        params["restrict_sr"] = 1
        return f"https://www.reddit.com/r/{quote(sub)}/search.json?{urlencode(params)}"
    return f"https://www.reddit.com/search.json?{urlencode(params)}"


def _get_json(url: str, cache_key: str, meta: dict) -> dict | list | None:
    """Cached JSON GET. Returns None on error; sets meta['json_blocked'] on 403/429."""
    import requests

    p = _cache_path(cache_key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    try:
        resp = requests.get(url, headers={"User-Agent": config.REDDIT_USER_AGENT}, timeout=25)
    except requests.RequestException as e:
        log.warning("Reddit JSON error %s: %s", url, e)
        meta["errors"] += 1
        return None
    if resp.status_code != 200:
        log.warning("Reddit JSON HTTP %d for %s", resp.status_code, url)
        meta["errors"] += 1
        if resp.status_code in (403, 429):
            meta["json_blocked"] = True
        return None
    try:
        data = resp.json()
    except ValueError:
        meta["errors"] += 1
        return None
    p.write_text(json.dumps(data), encoding="utf-8")
    meta["requests"] += 1
    time.sleep(config.REDDIT_RATE_SEC)
    return data


def _json_search(sub: str | None, query: str, meta: dict) -> list[dict] | None:
    data = _get_json(_search_endpoint(sub, query), f"search:{sub}:{query}", meta)
    if not isinstance(data, dict):
        return None
    posts = []
    for child in data.get("data", {}).get("children", []) or []:
        d = child.get("data", {}) or {}
        if d.get("over_18"):
            continue
        posts.append({
            "id": d.get("id"), "title": d.get("title", "") or "",
            "selftext": d.get("selftext", "") or "", "permalink": d.get("permalink", "") or "",
            "subreddit": d.get("subreddit"), "date": _iso_date(d.get("created_utc")),
        })
    return posts


def _json_comments(permalink: str, meta: dict) -> str:
    url = f"https://www.reddit.com{permalink}.json?sort=top&limit={config.REDDIT_TOP_COMMENTS}&raw_json=1"
    data = _get_json(url, f"comments:{permalink}", meta)
    if not isinstance(data, list) or len(data) < 2:
        return ""
    bodies = []
    for child in (data[1].get("data", {}).get("children", []) or [])[: config.REDDIT_TOP_COMMENTS]:
        if child.get("kind") == "t1":
            body = (child.get("data", {}) or {}).get("body", "")
            if body and body not in ("[deleted]", "[removed]"):
                bodies.append(body)
    return "\n".join(bodies)


# ---- RSS transport (fallback) ----------------------------------------------------

def _rss_search_endpoint(sub: str | None, query: str, after: str = "") -> str:
    params = {"q": query, "sort": "relevance", "t": config.REDDIT_WINDOW,
              "limit": config.REDDIT_RESULTS_PER_QUERY}
    if after:
        params["after"] = after
    if sub:
        params["restrict_sr"] = 1
        return f"https://www.reddit.com/r/{quote(sub)}/search.rss?{urlencode(params)}"
    return f"https://www.reddit.com/search.rss?{urlencode(params)}"


def _get_rss(url: str, cache_key: str, meta: dict) -> str | None:
    """Cached RSS/Atom GET. 429 -> bounded backoff+retry; 403 -> meta['rss_blocked']."""
    import requests

    p = _cache_path(cache_key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("xml")
        except ValueError:
            pass
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": config.REDDIT_USER_AGENT}, timeout=25)
        except requests.RequestException as e:
            log.warning("Reddit RSS error %s: %s", url, e)
            meta["errors"] += 1
            return None
        if resp.status_code == 200:
            xml = resp.text
            p.write_text(json.dumps({"xml": xml}), encoding="utf-8")
            meta["requests"] += 1
            time.sleep(config.REDDIT_RSS_RATE_SEC)
            return xml
        if resp.status_code == 429 and attempt < 2:
            meta["rss_backoffs"] += 1
            log.info("Reddit RSS 429 — backing off %ss (attempt %d)", config.REDDIT_RSS_BACKOFF_SEC, attempt + 1)
            time.sleep(config.REDDIT_RSS_BACKOFF_SEC)
            continue
        log.warning("Reddit RSS HTTP %d for %s", resp.status_code, url)
        meta["errors"] += 1
        if resp.status_code == 403:
            meta["rss_blocked"] = True
        return None
    return None


def _atom_raw(xml_text: str) -> list[dict]:
    """Raw Atom entries: id/title/permalink/subreddit/date/content. Author dropped."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    entries = []
    for e in root.findall("a:entry", _ATOM_NS):
        link = e.find("a:link", _ATOM_NS)
        cat = e.find("a:category", _ATOM_NS)
        updated = (e.findtext("a:updated", "", _ATOM_NS) or "")
        entries.append({
            "id": (e.findtext("a:id", "", _ATOM_NS) or "").strip(),
            "title": (e.findtext("a:title", "", _ATOM_NS) or "").strip(),
            "permalink": urlparse(link.get("href") if link is not None else "").path,
            "subreddit": cat.get("term") if cat is not None else None,
            "date": updated[:10] if len(updated) >= 10 else None,
            "content": e.findtext("a:content", "", _ATOM_NS) or "",
        })
    return entries


def _parse_atom(xml_text: str) -> list[dict]:
    """Atom search feed -> normalized post dicts (selftext extracted, author dropped)."""
    posts = []
    for e in _atom_raw(xml_text):
        posts.append({
            "id": e["id"].split("_")[-1] if e["id"] else "",   # t3_1abc -> 1abc
            "title": e["title"], "selftext": _strip_html(e["content"]),
            "permalink": e["permalink"], "subreddit": e["subreddit"], "date": e["date"],
        })
    return posts


def _rss_search(sub: str | None, query: str, meta: dict) -> list[dict] | None:
    xml = _get_rss(_rss_search_endpoint(sub, query), f"rss-search:{sub}:{query}", meta)
    return None if xml is None else _parse_atom(xml)


def _rss_comments(permalink: str, meta: dict) -> str:
    url = f"https://www.reddit.com{permalink}.rss?sort=top&limit={config.REDDIT_TOP_COMMENTS}"
    xml = _get_rss(url, f"rss-comments:{permalink}", meta)
    if not xml:
        return ""
    bodies = []
    for e in _atom_raw(xml)[1:]:               # entry[0] is the post itself
        b = _strip_html(e["content"])
        if b and b not in ("[deleted]", "[removed]"):
            bodies.append(b)
    return "\n".join(bodies)


# ---- orchestration ---------------------------------------------------------------

def _search(transport: str, sub: str | None, query: str, meta: dict) -> list[dict] | None:
    return _json_search(sub, query, meta) if transport == "json" else _rss_search(sub, query, meta)


def _comments(transport: str, permalink: str, meta: dict) -> str:
    return _json_comments(permalink, meta) if transport == "json" else _rss_comments(permalink, meta)


def scrape(meta: dict | None = None) -> list[dict]:
    """Reddit forum records. Apify first; auto-falls back to RSS/JSON on error."""
    if meta is None:
        meta = {}
    transport = config.REDDIT_TRANSPORT
    if transport == "apify" and config.APIFY_API_KEY:
        try:
            return _scrape_apify(meta)
        except Exception as e:
            log.warning("Apify transport failed (%s), falling back to RSS/JSON", e)
            meta["apify_error"] = str(e)
    return _scrape_rss_json(meta)


def _scrape_apify(meta: dict) -> list[dict]:
    """Apify-backed Reddit scrape. Uses trudax/reddit-scraper-lite (pay-per-result)."""
    from apify_client import ApifyClient

    client = ApifyClient(config.APIFY_API_KEY)
    actor = config.APIFY_REDDIT_ACTOR

    # Build search queries from the brand×term matrix
    override = meta.get("queries_override")
    if override:
        searches = override
    else:
        brands = [t for spec in config.apps_for("reddit") for t in spec.community_terms]
        searches = []
        # Brand × behaviour queries (highest value)
        for b in brands:
            for term in config.REDDIT_QUERY_TERMS:
                searches.append(f"{b} {term}")
        # Behaviour-only, site-wide
        for term in config.REDDIT_QUERY_TERMS[:6]:
            searches.append(f"{term} online shopping india")
        # Per-sub queries
        for sub in config.REDDIT_SUBS_PROPOSED:
            for b in brands:
                searches.append(f"r/{sub} {b}")

    meta.update({
        "transport_used": "apify", "queries": len(searches), "requests": 0,
        "errors": 0, "blocked": False, "threads_gated": 0,
        "comment_threads": 0, "apify_runs": 0, "usage_total_usd": 0.0,
        "rss_backoffs": 0, "json_blocked": False, "rss_blocked": False,
    })

    out: list[dict] = []
    seen_posts: set[str] = set()

    # Batch searches into chunks to stay within reasonable run sizes.
    # Each Apify run handles a batch of search queries.
    BATCH_SIZE = 10
    MAX_POSTS_PER_SEARCH = 100  # maximize volume
    MAX_COMMENTS = 50  # deep comment pull per post

    for i in range(0, len(searches), BATCH_SIZE):
        batch = searches[i:i + BATCH_SIZE]
        run_input = {
            "searches": batch,
            "maxItems": MAX_POSTS_PER_SEARCH * len(batch),
            "maxPostCount": MAX_POSTS_PER_SEARCH,
            "maxComments": MAX_COMMENTS,
            "skipComments": False,
        }

        log.info("Apify run %d: queries %d-%d of %d",
                 i // BATCH_SIZE + 1, i + 1, min(i + BATCH_SIZE, len(searches)),
                 len(searches))
        try:
            run = client.actor(actor).call(run_input=run_input)
            meta["apify_runs"] += 1
            if hasattr(run, 'usage_total_usd'):
                meta["usage_total_usd"] += run.usage_total_usd or 0.0
            elif isinstance(run, dict):
                meta["usage_total_usd"] += run.get("usageTotalUsd", 0.0)
        except Exception as e:
            log.warning("Apify run failed for batch %d: %s", i // BATCH_SIZE + 1, e)
            meta["errors"] += 1
            continue

        # Extract results from the dataset
        dataset_id = run.default_dataset_id if hasattr(run, 'default_dataset_id') else run.get("defaultDatasetId")
        if not dataset_id:
            continue

        for item in client.dataset(dataset_id).iterate_items():
            pid = item.get("id") or item.get("postId") or ""
            if not pid or pid in seen_posts:
                continue

            # Exclude spam subs (self-promo, deal-aggregator) per STEP 8 analysis
            subreddit = item.get("subreddit") or item.get("communityName") or ""
            if subreddit.lower() in [s.lower() for s in config.REDDIT_SUBS_EXCLUDED]:
                continue

            seen_posts.add(pid)

            title = item.get("title") or ""
            body = item.get("body") or item.get("selftext") or item.get("text") or ""
            text = f"{title}\n\n{body}".strip()

            # Append comments if available
            comments = item.get("comments") or []
            if comments:
                meta["comment_threads"] += 1
                comment_bodies = []
                for c in comments:
                    cb = c.get("body") or c.get("text") or ""
                    if cb and cb not in ("[deleted]", "[removed]"):
                        comment_bodies.append(cb)
                if comment_bodies:
                    text = f"{text}\n\n" + "\n".join(comment_bodies)

            if not _relevant(text):
                continue
            meta["threads_gated"] += 1

            subreddit = item.get("subreddit") or item.get("communityName") or ""
            permalink = item.get("url") or item.get("permalink") or ""
            posted = item.get("createdAt") or item.get("created_utc") or ""
            if posted and len(posted) >= 10:
                posted = posted[:10]
            else:
                posted = None

            out += emit_for_brands(
                text,
                source_url=permalink if permalink.startswith("http") else f"https://www.reddit.com{permalink}" if permalink else "",
                source_type="reddit", source_detail=subreddit,
                posted_date=posted, ext_id=pid, min_count=1,
            )

    log.info("Reddit (Apify): %d records from %d gated threads across %d queries "
             "(%d runs, $%.4f usage)",
             len(out), meta["threads_gated"], meta["queries"],
             meta["apify_runs"], meta["usage_total_usd"])
    return out


def _scrape_rss_json(meta: dict) -> list[dict]:
    """Reddit forum records via RSS/JSON fallback. Original transport."""
    for k, v in {"requests": 0, "errors": 0, "blocked": False, "queries": 0,
                 "threads_gated": 0, "comment_threads": 0, "transport_used": None,
                 "rss_backoffs": 0, "json_blocked": False, "rss_blocked": False}.items():
        meta.setdefault(k, v)

    out: list[dict] = []
    seen_posts: set[str] = set()
    comment_budget = config.REDDIT_MAX_COMMENT_THREADS
    transport = "json"

    for sub, query in _search_urls():
        if meta["blocked"]:
            log.warning("Reddit blocked on both transports — stopping (yield logged honestly).")
            break
        meta["queries"] += 1

        posts = _search(transport, sub, query, meta)
        if posts is None and transport == "json" and meta["json_blocked"]:
            transport = "rss"
            log.warning("Reddit JSON returns 403 — switching to RSS transport for the rest of the run.")
            posts = _search(transport, sub, query, meta)
        if posts is None:
            if meta["rss_blocked"]:
                meta["blocked"] = True
            continue
        meta["transport_used"] = transport

        for post in posts:
            pid = post.get("id")
            if not pid or pid in seen_posts:
                continue
            # Exclude spam subs per STEP 8 analysis
            post_sub = post.get("subreddit") or ""
            if post_sub.lower() in [s.lower() for s in config.REDDIT_SUBS_EXCLUDED]:
                continue
            text = f"{post['title']}\n\n{post['selftext']}".strip()
            if not _relevant(text):
                continue
            seen_posts.add(pid)
            meta["threads_gated"] += 1
            permalink = post.get("permalink") or ""
            if comment_budget > 0 and permalink and not meta["blocked"]:
                comments = _comments(transport, permalink, meta)
                if comments:
                    text = f"{text}\n\n{comments}"
                    meta["comment_threads"] += 1
                comment_budget -= 1
            records = emit_for_brands(
                text,
                source_url=f"https://www.reddit.com{permalink}" if permalink else "",
                source_type="reddit", source_detail=post.get("subreddit"),
                posted_date=post.get("date"), ext_id=pid, min_count=1,
            )
            for r in records:
                r["query"] = query
            out += records

    log.info("Reddit: %d records from %d gated threads across %d queries "
             "(transport=%s, requests=%d, backoffs=%d, blocked=%s)",
             len(out), meta["threads_gated"], meta["queries"], meta["transport_used"],
             meta["requests"], meta["rss_backoffs"], meta["blocked"])
    return out


def sample(n: int = 75, *, queries: list | None = None) -> tuple[list[dict], dict]:
    """Gate sample: pulls from whichever transport is configured, returns first n."""
    meta = {"queries_override": queries} if queries else {}
    out = scrape(meta)
    return out[:n], meta
