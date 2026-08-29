"""Source registry + the STEP 8 sample gate ledger.

ONE place that knows, per ingestion source: whether a scraper exists for this brief,
how to call it, and whether a human has approved it for full ingestion.

WHY THE LEDGER EXISTS

The expensive failure on this project is not a scraper that breaks — it is a scraper
that works and returns thousands of records of the wrong kind of talk. That cost only
becomes visible after embedding and clustering, by which point the money and the days
are spent. So full ingestion is gated on a recorded human decision, made after reading
a small sample. The gate is machinery, not discipline: `run.py ingest` refuses a source
with no approval on file.

The ledger lives in data/ (gitignored) because it is a record of THIS run's decisions,
not a property of the code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

from . import config

LEDGER_PATH = config.DATA_DIR / "sample_gate.json"


@dataclass(frozen=True)
class Source:
    key: str
    implemented: bool          # is there a scraper for THIS brief?
    weight: str                # "primary" | "secondary"
    note: str = ""


SOURCES: dict[str, Source] = {
    "play": Source("play", True, "secondary",
                   "Play Store reviews — transactional; corroboration only."),
    "appstore": Source("appstore", True, "secondary",
                       "App Store reviews — transactional; corroboration only."),
    "reddit": Source("reddit", True, "primary",
                     "PENDING Apify rewrite. Current transport is the previous build's "
                     "RSS fallback with the wrong query shape."),
    "youtube": Source("youtube", True, "primary",
                      "Two-stage: resolve video ids (search.list, 100 units) then "
                      "commentThreads (1 unit). Brand inherited from the VIDEO, not the "
                      "comment — comment-level brand matching would discard most of the "
                      "corpus. Seed queries are deliberation contexts with zero axis terms."),
    "forum": Source("forum", False, "primary",
                    "Folded into Reddit — the previous aggregator targets were complaint "
                    "registries, the wrong corpus profile for purchase deliberation."),
    "twitter": Source("twitter", False, "primary",
                      "NOT BUILT, NOT SAMPLED. X search is behind auth (HTTP 402) and "
                      "post bodies are not meaningfully indexed by general web search, so "
                      "no hit-rate has been measured. Do NOT record a drop decision as "
                      "'sampled' until one actually is — pay-per-use reads are $0.005 "
                      "each, so a 200-post sample costs ~$1."),
}


def implemented() -> list[str]:
    return [k for k, s in SOURCES.items() if s.implemented]


def pending() -> list[str]:
    return [k for k, s in SOURCES.items() if not s.implemented]


# ---- Sample-gate ledger -----------------------------------------------------------

def _load() -> dict:
    if not LEDGER_PATH.exists():
        return {"decisions": {}}
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"decisions": {}}


def record_decision(source: str, *, approved: bool, hit_rate: float,
                    sample_n: int, note: str = "") -> dict:
    """Record a human's full-scrape / drop decision for a source."""
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    doc = _load()
    doc.setdefault("decisions", {})[source] = {
        "approved": bool(approved),
        "hit_rate_pct": round(float(hit_rate), 1),
        "sample_n": int(sample_n),
        "decided_on": _date.today().isoformat(),
        "note": note,
    }
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc["decisions"][source]


def record_observation(source: str, *, hit_rate: float, strict_rate: float,
                       sample_n: int, scope: str, note: str = "") -> dict:
    """Log a gate MEASUREMENT without deciding anything.

    record_decision() forces an approved=True/False binary. A gate result that has been
    measured but not yet ruled on has nowhere else to live, and leaving it only in a
    terminal scrollback is how a number gets remembered at the wrong scope later —
    "YouTube was 0%" when what was actually measured was "three generic haul queries
    across nine videos of one venue type returned 0%".

    `scope` is mandatory and is the point of this function: it records WHAT was
    measured, so the observation cannot be over-generalised after the fact.

    Observations never satisfy assert_approved(). Ingest stays blocked.
    """
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    doc = _load()
    obs = {
        "hit_rate_pct": round(float(hit_rate), 1),
        "strict_pct": round(float(strict_rate), 1),
        "sample_n": int(sample_n),
        "scope": scope,
        "observed_on": _date.today().isoformat(),
        "note": note,
    }
    doc.setdefault("observations", {}).setdefault(source, []).append(obs)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return obs


def observations(source: str) -> list[dict]:
    return _load().get("observations", {}).get(source, [])


def decision(source: str) -> dict | None:
    return _load().get("decisions", {}).get(source)


class SampleGateError(RuntimeError):
    """Raised when full ingestion is attempted on an unapproved source."""


def assert_approved(source: str) -> dict:
    """Refuse full ingestion on a source no human has signed off after sampling."""
    d = decision(source)
    if d is None:
        raise SampleGateError(
            f"source {source!r} has no sample-gate decision on file. Refusing full ingestion.\n"
            f"  Run:  python -m scripts.sample_gate --source {source} -n 75\n"
            f"  Then record the call with --approve / --drop.\n"
            f"  A source that returns volume of the wrong kind of talk costs money and days "
            f"before anyone notices; a 75-record sample answers it in a minute."
        )
    if not d["approved"]:
        raise SampleGateError(
            f"source {source!r} was DROPPED at the sample gate on {d['decided_on']} "
            f"(hit-rate {d['hit_rate_pct']}% on n={d['sample_n']}). Refusing full ingestion.\n"
            f"  note: {d.get('note') or '(none)'}"
        )
    return d
