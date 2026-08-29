"""Apple App Store scraper (§6) via the public iTunes RSS customer-reviews feed.

Deliberately uses the iTunes RSS JSON feed rather than the `app-store-scraper`
library: that library depends on Apple's token-gated amp-api, which is flaky and
frequently returns empty. RSS is public JSON, needs no token, and is reliable —
at the cost of a hard ceiling (~50 reviews/page, ~10 pages, most-recent only).
That ceiling is exactly the kind of scraper cap §6 anticipates; the achieved
count is logged honestly, and Play Store carries the bulk volume.
"""
from __future__ import annotations

import logging
import time

import requests

from ... import config
from ...config import AppSpec
from . import raw_record

log = logging.getLogger(__name__)

_UA = {"User-Agent": "Mozilla/5.0 (compatible; PMGraduationProject/1.0)"}
_RSS = (
    "https://itunes.apple.com/{country}/rss/customerreviews/"
    "id={app_id}/sortBy=mostRecent/page={page}/json"
)


def scrape(spec: AppSpec, max_pages: int | None = None) -> list[dict]:
    max_pages = max_pages or config.APPSTORE_RSS_MAX_PAGES
    out: list[dict] = []

    for page in range(1, max_pages + 1):
        url = _RSS.format(country=config.COUNTRY, app_id=spec.appstore_id, page=page)
        try:
            resp = requests.get(url, headers=_UA, timeout=20)
        except requests.RequestException as e:
            log.warning("[appstore:%s] network error page %d: %s", spec.key, page, e)
            break
        if resp.status_code != 200:
            log.info("[appstore:%s] page %d -> HTTP %d, stopping", spec.key, page, resp.status_code)
            break
        try:
            entries = resp.json().get("feed", {}).get("entry", [])
        except ValueError:
            log.info("[appstore:%s] page %d not JSON, stopping", spec.key, page)
            break

        # Review entries carry im:rating; the app-metadata entry does not.
        review_entries = [e for e in entries if "im:rating" in e]
        if not review_entries:
            break

        for e in review_entries:
            title = e.get("title", {}).get("label", "") or ""
            body = e.get("content", {}).get("label", "") or ""
            text = f"{title}. {body}".strip(". ").strip() if title else body
            try:
                rating = int(e["im:rating"]["label"])
            except (KeyError, ValueError):
                rating = None
            updated = e.get("updated", {}).get("label")
            iso = updated[:10] if updated else None
            out.append(
                raw_record(
                    app=spec.key,
                    store="appstore",
                    text=text,
                    rating=rating,
                    posted_date=iso,
                    ext_id=e.get("id", {}).get("label"),
                )
            )

        time.sleep(config.SCRAPE_PAGE_PAUSE_SEC)

    log.info("[appstore:%s] %d raw reviews", spec.key, len(out))
    return out
