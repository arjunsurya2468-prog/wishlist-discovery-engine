"""Brief-question mapping — "what the corpus must help answer".

Maps the engine's output back to the TEN discovery questions in the assignment brief,
including an explicit "reviews structurally cannot answer this" verdict where
that is the honest result. Mirrors funnel_map.py and triangulation.py: code
LOADS the human file, it never generates it.

The integrity property: prose, statuses and caveats are human-owned, but every
COUNT and every theme QUOTE is joined from the published themes by `theme_id` at
build time. A human never re-types a number, so an answer can never drift from
the Themes tab, and a typo'd theme_id raises instead of silently dropping
evidence from a row.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .. import config

log = logging.getLogger(__name__)

_DEFAULT_PATH = config.INTERPRET_DIR / "brief_questions.json"
_SPOTCHECK_PATH = config.INTERPRET_DIR / "spotcheck.json"

# The only statuses a row may carry. "Not answerable from review data" is a
# first-class outcome (§12), not a failure state.
STATUSES = {
    "Answered",
    "Partial",
    "Suggestive - under-powered",
    "Not answerable from review data",
}

_NOT_ANSWERABLE = "Not answerable from review data"

# The TEN discovery questions the brief names, verbatim in intent. The human-authored
# file must cover exactly these ids — no more, no fewer. Enforced in load_questions()
# so a question cannot be quietly dropped because the corpus turned out not to answer it
# ("Not answerable from review data" is the honest way to close a row, not omission).
BRIEF_QUESTIONS: dict[str, str] = {
    "Q1":  "Why do users add fashion products to their wishlist?",
    "Q2":  "What prevents wishlisted products from eventually being purchased?",
    "Q3":  "What uncertainties remain after users have identified a product they like?",
    "Q4":  "What causes users to postpone a purchase?",
    "Q5":  "How do users compare multiple shortlisted products?",
    "Q6":  "What information do users seek outside the app before purchasing?",
    "Q7":  "What role do fit, size, styling, price, reviews, occasion and social "
           "validation play?",
    "Q8":  "When do users use the wishlist as genuine purchase intent versus simply "
           "as a bookmarking mechanism?",
    "Q9":  "How do these behaviours differ across user segments?",
    "Q10": "What unmet needs emerge consistently across user conversations?",
}


def _theme_id(t: dict) -> str:
    """Published-theme address. Same convention as triangulation._theme_id."""
    return f"{t.get('track', 'full')}:{t.get('cluster_id', '')}"


def load_questions(path: Path | str | None = None) -> dict:
    """Return the human-authored brief-question document.

    Raises ValueError on a malformed row (missing question/answer/id, or a
    status outside the enum) so a bad hand-edit fails loud near the deadline
    rather than rendering a half-empty tab.
    """
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"brief questions not found at {p} — create it before publishing"
        )
    raw = json.loads(p.read_text(encoding="utf-8"))
    questions = raw.get("questions", [])
    if not questions:
        raise ValueError(f"{p.name}: no questions defined")

    seen: set[str] = set()
    for i, q in enumerate(questions):
        qid = (q.get("id") or "").strip()
        if not qid:
            raise ValueError(f"{p.name} row {i}: missing id")
        if qid in seen:
            raise ValueError(f"{p.name} row {i}: duplicate id {qid!r}")
        seen.add(qid)
        if not (q.get("question") or "").strip():
            raise ValueError(f"{p.name} row {i} ({qid}): missing question text")
        if not (q.get("answer") or "").strip():
            raise ValueError(
                f"{p.name} row {i} ({qid}): missing answer — a row with no answer "
                f"is incomplete; use status {_NOT_ANSWERABLE!r} and say why"
            )
        status = (q.get("status") or "").strip()
        if status not in STATUSES:
            raise ValueError(
                f"{p.name} row {i} ({qid}): invalid status {status!r}; "
                f"choose from {sorted(STATUSES)}"
            )

    # Coverage: exactly the brief's ten questions, no silent drops or additions.
    expected = set(BRIEF_QUESTIONS)
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    if missing:
        raise ValueError(
            f"{p.name}: missing brief questions {missing} — every one of the ten must "
            f"appear. If the corpus cannot answer one, keep the row and use status "
            f"{_NOT_ANSWERABLE!r} with a reason."
        )
    if extra:
        raise ValueError(f"{p.name}: unknown question ids {extra}; valid ids are {sorted(expected)}")
    return raw


def _load_spotcheck_texts(path: Path | str | None = None) -> dict[str, str]:
    """Return {review_id: text} from the spot-check sample, or {} if absent."""
    p = Path(path) if path else _SPOTCHECK_PATH
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {
        s["review_id"]: s.get("text", "")
        for s in raw.get("samples", [])
        if s.get("review_id")
    }


def _resolve(theme_ids: list[str], index: dict[str, dict],
             qid: str, field: str) -> list[dict]:
    """Join theme_ids -> display evidence. Unknown id raises, naming valid ids."""
    out: list[dict] = []
    for tid in theme_ids:
        theme = index.get(tid)
        if theme is None:
            raise ValueError(
                f"brief_questions.json ({qid}.{field}): unknown theme_id {tid!r} — "
                f"not one of the published themes. Valid ids: {sorted(index)}"
            )
        # Only validated quotes reach the payload — same contract as the themes table.
        quotes = [
            q for q in theme.get("quotes", [])
            if not isinstance(q, dict) or q.get("validation_status") == "Validated"
        ][:3]
        out.append({
            "theme_id": tid,
            "theme_name": theme.get("theme_name", ""),
            "review_count": theme.get("review_count", 0),
            "pct_of_corpus": theme.get("pct_of_corpus", 0.0),
            "funnel_gate": theme.get("funnel_gate", ""),
            "per_app": theme.get("per_app", {}),
            "quotes": quotes,
        })
    return out


def build_rows(themes: list[dict], corpus_usable: int = 0,
               path: Path | str | None = None) -> dict:
    """Join the human brief-question file to the published themes.

    `evidence_n` is SUMMED from the joined themes, never read from the human
    file — that join is what guarantees the answers cannot drift from the
    Themes tab. Corpus quotes are cross-checked verbatim against the spot-check
    sample by review_id; a mismatch raises rather than displaying text whose
    provenance can't be proven.
    """
    doc = load_questions(path)
    index = {_theme_id(t): t for t in themes}
    spotcheck = _load_spotcheck_texts()

    rows: list[dict] = []
    for q in doc["questions"]:
        qid = q["id"]
        evidence = _resolve(q.get("evidence_theme_ids", []), index, qid, "evidence_theme_ids")
        context = _resolve(q.get("context_theme_ids", []), index, qid, "context_theme_ids")

        # Verbatim-corpus quotes: prove provenance instead of trusting the file.
        corpus_quotes = []
        for cq in q.get("corpus_quotes", []):
            rid = cq.get("review_id", "")
            text = cq.get("text", "")
            source_text = spotcheck.get(rid)
            if source_text is None:
                raise ValueError(
                    f"brief_questions.json ({qid}): corpus_quote review_id {rid!r} "
                    f"is not in the spot-check sample — provenance unverifiable"
                )
            if text.strip() != source_text.strip():
                raise ValueError(
                    f"brief_questions.json ({qid}): corpus_quote text for {rid!r} does "
                    f"not match the source review verbatim.\n  file:   {text!r}\n"
                    f"  source: {source_text!r}"
                )
            corpus_quotes.append({**cq, "validation_status": "Validated - verbatim corpus text"})

        evidence_n = sum(e["review_count"] for e in evidence)
        rows.append({
            "id": qid,
            "question": q["question"],
            "status": q["status"],
            "answerable": q["status"] != _NOT_ANSWERABLE,
            "answer": q["answer"],
            "evidence": evidence,
            "context": context,
            "evidence_n": evidence_n,
            "evidence_pct": (round(100 * evidence_n / corpus_usable, 1)
                             if corpus_usable and evidence_n else 0.0),
            "theme_count": len(evidence),
            "corpus_quotes": corpus_quotes,
            "cross_refs": q.get("cross_refs", []),
            "caveat": (q.get("caveat") or "").strip(),
            "defers_to": (q.get("defers_to") or "").strip(),
        })

    answerable = sum(1 for r in rows if r["answerable"])
    return {
        "version": doc.get("version", ""),
        "questions": rows,
        "summary": {
            "total": len(rows),
            "answerable": answerable,
            "not_answerable": len(rows) - answerable,
        },
        "source_disclosure": doc.get("source_disclosure", {}),
        "gate_distribution": _gate_distribution(doc, themes),
    }


def _gate_distribution(doc: dict, themes: list[dict]) -> dict:
    """Human prose + live per-gate theme counts, so the headline can't go stale.

    Which gate the themes pile up in IS the finding for this brief: it says whether
    wishlist conversion is dying at Save, Return, Resolve or Convert.
    """
    from ..models import FUNNEL_GATES

    finding = dict(doc.get("gate_distribution", {}))
    counts = {g: sum(1 for t in themes if t.get("funnel_gate") == g) for g in FUNNEL_GATES}
    finding["per_gate_theme_count"] = counts
    finding["per_gate_review_count"] = {
        g: sum(t.get("review_count", 0) for t in themes if t.get("funnel_gate") == g)
        for g in FUNNEL_GATES
    }
    finding["total_theme_count"] = len(themes)
    finding["dominant_gate"] = max(counts, key=counts.get) if any(counts.values()) else None
    return finding
