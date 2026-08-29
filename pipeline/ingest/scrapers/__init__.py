"""Store + forum scrapers. Each emits a uniform *raw record* so downstream
dedupe/normalize is store-agnostic. Scrapers normalize field NAMES only — never
review content (that is normalize.py's job, after PII scrub)."""
from __future__ import annotations

from ...models import STORE_VALUES


class UnknownStoreError(ValueError):
    """Raised when a scraper emits a record for a store the corpus cannot load.

    normalize.py does not validate `store`, and corpus.load_corpus() filters on it.
    A typo or an unregistered source therefore writes cleanly to cache and then
    SILENTLY VANISHES at load time — the record exists on disk, is well-formed, and
    is never analyzed. Fail at emission instead, where the stack trace names the
    scraper that did it.
    """


def raw_record(
    app: str,
    store: str,
    text: str | None,
    rating: int | None,
    posted_date: str | None,
    ext_id: str | None = None,
    source_url: str | None = None,
    source_type: str | None = None,
    source_detail: str | None = None,
    multi_brand: bool = False,
    thread_id: str | None = None,
) -> dict:
    if store not in STORE_VALUES:
        raise UnknownStoreError(
            f"store={store!r} is not in models.STORE_VALUES {STORE_VALUES}. "
            f"A record with an unregistered store writes to cache cleanly and is then "
            f"dropped by corpus.load_corpus() without a warning. Register the source in "
            f"models.STORE_VALUES and corpus.PRIMARY_SOURCES/SECONDARY_SOURCES first."
        )
    return {
        "app": app,
        "store": store,
        "text": text or "",
        "rating": rating,
        "posted_date": posted_date,
        "ext_id": ext_id,
        "source_url": source_url,
        "source_type": source_type,
        "source_detail": source_detail,
        "multi_brand": multi_brand,
        "thread_id": thread_id,
    }
