"""Dedupe BEFORE normalization (§7.1).

QC reviews carry heavy copy-paste spam, so we collapse by a hash of
(text, rating, posted_date). The text is whitespace-collapsed and lowercased
for the key so trivial variants of the same pasted review still collide.
The review that survives keeps its original casing/text.
"""
from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")


def _norm_text(text: str | None) -> str:
    return _WS.sub(" ", (text or "").strip()).lower()


def dedupe_key(text: str | None, rating, posted_date) -> str:
    basis = f"{_norm_text(text)}|{rating}|{posted_date}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """Return (deduped_records, n_dropped). First occurrence wins."""
    seen: set[str] = set()
    out: list[dict] = []
    dropped = 0
    for rec in records:
        key = dedupe_key(rec.get("text"), rec.get("rating"), rec.get("posted_date"))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(rec)
    return out, dropped
