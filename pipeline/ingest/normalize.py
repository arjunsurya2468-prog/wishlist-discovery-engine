"""Normalization: raw records -> canonical Review corpus (§7.1).

Pipeline per app: dedupe -> PII scrub -> strip emoji chars -> collapse whitespace
-> word floor (>=8) -> language tag -> relevance flag -> Review.

Language rule is a deliberate departure from the reference architecture: Hinglish
is KEPT and tagged (it carries the most honest QC signal). Emoji *characters* are
stripped; an emoji-bearing review is kept if it still clears the word floor.
"""
from __future__ import annotations

import hashlib
import re

from .. import config
from ..models import Review
from . import dedupe as dedupe_mod
from . import lexicon, pii

_WS = re.compile(r"\s+")

# Emoji + pictographs + regional indicators + variation selectors + ZWJ.
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F0FF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)

# Distinctive romanized-Hindi markers (curated for precision, not recall).
_HINGLISH_MARKERS = {
    "hai", "nahi", "nhi", "kyu", "kyun", "mera", "meri", "bahut", "bhaut",
    "accha", "acha", "achha", "theek", "thik", "sirf", "liye", "paisa", "paise",
    "kiya", "karo", "yaar", "bhai", "matlab", "kitna", "kitne", "zyada",
    "bakwas", "bekar", "badhiya", "mast", "chahiye", "kharab", "kyunki", "wala",
}
_LATIN_TOKEN = re.compile(r"[a-z]+")


def _strip_emoji(text: str) -> str:
    return _EMOJI.sub("", text)


def _collapse_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def _nonlatin_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    nonlatin = sum(1 for c in letters if ord(c) > 0x024F)  # beyond Latin Extended-B
    return nonlatin / len(letters)


def detect_language(text: str) -> str:
    """Heuristic tag (en / hinglish / other) for slicing — not a classifier."""
    if _nonlatin_ratio(text) > 0.15:      # Devanagari / Tamil / etc.
        return "other"
    tokens = _LATIN_TOKEN.findall(text.lower())
    if not tokens:
        return "other"
    hits = sum(1 for t in tokens if t in _HINGLISH_MARKERS)
    if hits >= 2:
        return "hinglish"
    return "en"


def _review_id(app: str, store: str, text: str) -> str:
    return hashlib.sha256(f"{app}|{store}|{text}".encode("utf-8")).hexdigest()[:16]


def normalize_corpus(app: str, raw_records: list[dict]) -> tuple[list[Review], dict]:
    """Return (usable Reviews, stats dict for the manifest)."""
    deduped, dup_dropped = dedupe_mod.dedupe(raw_records)

    reviews: list[Review] = []
    floor_dropped = 0
    by_language: dict[str, int] = {}
    by_store_usable: dict[str, int] = {}
    relevance_count = 0

    for rec in deduped:
        text = pii.scrub(rec.get("text"))
        text = _collapse_ws(_strip_emoji(text))
        wc = _word_count(text)
        if wc < config.WORD_FLOOR:
            floor_dropped += 1
            continue

        store = rec.get("store", "play")
        language = detect_language(text)
        flagged, categories = lexicon.flag(text, app)   # app-aware: own brand never self-flags
        if flagged:
            relevance_count += 1

        reviews.append(
            Review(
                review_id=_review_id(app, store, text),
                app=app,
                store=store,
                text=text,
                rating=rec.get("rating"),
                posted_date=rec.get("posted_date"),
                language=language,
                word_count=wc,
                relevance_flagged=flagged,
                category_mentioned=categories,
                source_url=rec.get("source_url"),
                source_type=rec.get("source_type"),
                source_detail=rec.get("source_detail"),
                multi_brand=bool(rec.get("multi_brand", False)),
                thread_id=rec.get("thread_id"),
            )
        )
        by_language[language] = by_language.get(language, 0) + 1
        by_store_usable[store] = by_store_usable.get(store, 0) + 1

    raw_by_store: dict[str, int] = {}
    for rec in raw_records:
        s = rec.get("store", "play")
        raw_by_store[s] = raw_by_store.get(s, 0) + 1

    usable = len(reviews)
    raw_n = len(raw_records)
    stats = {
        "raw_scraped": raw_n,
        "raw_by_store": raw_by_store,
        "after_dedupe": len(deduped),
        "dup_dropped": dup_dropped,
        "floor_dropped": floor_dropped,
        "usable": usable,
        "retention_pct": round(100 * usable / raw_n, 1) if raw_n else 0.0,
        "by_language": by_language,
        "by_store_usable": by_store_usable,
        "relevance_flagged": relevance_count,
        "lexicon_version": lexicon.LEXICON_VERSION,
        "word_floor": config.WORD_FLOOR,
    }
    return reviews, stats
