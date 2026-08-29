"""PII scrub — runs BEFORE any storage, LLM call, or display (§7.1).

emails -> [EMAIL], Indian phone -> [PHONE], long ID-like numerics -> [ID],
URLs -> [URL]. Monetary amounts are KEPT deliberately (theme signal, not PII).

Order matters: URLs and emails are removed before the numeric rules so their
digits can't be misread as a phone or an ID.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)

# Reddit user handles in forum text (u/name, /u/name, /user/name) -> [USER] (blind-eval;
# subreddit r/ mentions are public community names and are kept).
_REDDIT_HANDLE = re.compile(r"(?<![A-Za-z0-9])/?(?:u|user)/[A-Za-z0-9_-]{3,20}", re.IGNORECASE)

# Indian mobile: optional +91/91/0 prefix, then a 10-digit number starting 6-9,
# optionally split 5+5 by a space or dash. Guarded so it isn't part of a longer run.
_PHONE_CONTIG = re.compile(r"(?<!\d)(?:\+?91[\s\-]?|0)?[6-9]\d{9}(?!\d)")
_PHONE_SPLIT = re.compile(r"(?<!\d)(?:\+?91[\s\-]?|0)?[6-9]\d{4}[\s\-]\d{5}(?!\d)")

# Long ID-like runs (order ids, OTPs). Threshold 7+ keeps ordinary prices intact
# (₹1,20,000 has comma-broken runs; typical amounts are <=6 contiguous digits).
_LONG_ID = re.compile(r"(?<!\d)\d{7,}(?!\d)")


def scrub(text: str | None) -> str:
    if not text:
        return ""
    text = _URL.sub("[URL]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    text = _REDDIT_HANDLE.sub("[USER]", text)
    text = _PHONE_SPLIT.sub("[PHONE]", text)
    text = _PHONE_CONTIG.sub("[PHONE]", text)
    text = _LONG_ID.sub("[ID]", text)
    return text
