"""Quote validation — the hallucination kill-switch — P3 (§7.5).

Every model quote must be a verbatim substring of a real review before it can
appear anywhere. Normalize whitespace/punctuation, case-insensitive substring
match against the cluster's reviews (full corpus as fallback), accept ellipsis-
truncated prefixes. Failures are dropped and counted; a fabricated quote is
structurally impossible to display.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s or "").strip().lower()


def is_valid(quote: str, texts: list[str], _normed: list[str] | None = None) -> bool:
    q = _norm(quote)
    if not q:
        return False
    q_core = q.split("...")[0].split("…")[0].strip(" .,!\"'")  # ellipsis-truncated prefix
    normed = _normed if _normed is not None else [_norm(t) for t in texts]
    for nt in normed:
        if q in nt or (len(q_core) >= 8 and q_core in nt):
            return True
    return False


def validate_theme(theme: dict, cluster_texts: list[str], corpus_texts: list[str] | None = None) -> dict:
    """Partition theme['quotes'] into validated/rejected. Mutates and returns theme."""
    cluster_normed = [_norm(t) for t in cluster_texts]
    corpus_normed = [_norm(t) for t in corpus_texts] if corpus_texts else None

    kept, rejected = [], []
    for q in theme.get("quotes", []):
        ok = is_valid(q, cluster_texts, cluster_normed)
        if not ok and corpus_normed is not None:
            ok = is_valid(q, corpus_texts, corpus_normed)
        (kept if ok else rejected).append(q)

    theme["quotes"] = kept
    theme["quotes_rejected"] = rejected
    theme["n_quotes_validated"] = len(kept)
    theme["n_quotes_rejected"] = len(rejected)
    return theme
