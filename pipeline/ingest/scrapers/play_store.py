"""Google Play scraper (§6) — primary volume source.

Free `google-play-scraper` lib, country='in', newest-first, paginated to the §6
ceiling. Stops at the first of: per-app target, pagination end, or a review older
than SCRAPE_MAX_MONTHS (the feed is newest-first, so the first out-of-window page
means we are done). No language filtering at scrape time (§7.1).
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from ... import config
from ...config import AppSpec
from . import raw_record

log = logging.getLogger(__name__)


def _cutoff_date() -> date:
    return date.today() - timedelta(days=int(config.SCRAPE_MAX_MONTHS * 30.44))


def scrape(spec: AppSpec, target: int | None = None) -> list[dict]:
    from google_play_scraper import Sort, reviews

    target = target or config.SCRAPE_TARGET_PER_APP
    cutoff = _cutoff_date()
    out: list[dict] = []
    token = None
    pages = 0

    while len(out) < target:
        try:
            batch, token = reviews(
                spec.play_package,
                lang="en",            # UI locale only; review texts of all langs return
                country=config.COUNTRY,
                sort=Sort.NEWEST,
                count=config.PLAY_BATCH,
                continuation_token=token,
            )
        except Exception as e:  # transient network / library error — stop gracefully
            log.warning("[play:%s] stopped on error after %d: %s", spec.key, len(out), e)
            break

        if not batch:
            break

        hit_window_end = False
        for r in batch:
            posted = r.get("at")
            iso = posted.date().isoformat() if posted else None
            if posted and posted.date() < cutoff:
                hit_window_end = True
                break
            content = r.get("content")
            if not content:
                continue
            out.append(
                raw_record(
                    app=spec.key,
                    store="play",
                    text=content,
                    rating=r.get("score"),
                    posted_date=iso,
                    ext_id=r.get("reviewId"),
                )
            )

        pages += 1
        if hit_window_end or token is None:
            break
        time.sleep(config.SCRAPE_PAGE_PAUSE_SEC)

    log.info("[play:%s] %d raw reviews across %d pages", spec.key, len(out), pages)
    return out
