"""Canonical data models shared by pipeline and app (architecture §4).

Plain stdlib dataclasses, deliberately NOT Pydantic: this avoids a compiled
dependency (pydantic-core) on a bleeding-edge interpreter, and the validation we
actually need (word floor, PII scrub, dedupe) is domain logic we own, not schema
coercion. The Airtable schema (§9) and analysis.json are projections of these.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

APP_VALUES = ("Myntra", "AJIO", "Nykaa Fashion")
STORE_VALUES = ("play", "appstore", "reddit", "youtube", "twitter", "forum")
LANGUAGE_VALUES = ("en", "hinglish", "other")

# The wishlist -> purchase funnel. Each gate is a distinct place the conversion can
# die, and a theme is mapped to the gate whose FAILURE it describes.
#   Save    - why the item entered the wishlist at all (intent vs bookmarking)
#   Return  - whether the user ever comes back to the saved item
#   Resolve - the uncertainty that must clear before buying (fit, price, quality, social)
#   Convert - what finally triggers, or blocks, the purchase itself
FUNNEL_GATES = ("Save", "Return", "Resolve", "Convert", "Other - unrelated")

# Why a save happens — the brief separates genuine purchase intent from bookmarking,
# and that distinction drives segment analysis, so it is a first-class field.
SAVE_INTENTS = ("Purchase intent", "Bookmark / inspiration", "Price watch",
                "Comparison shortlist", "Unclear")


@dataclass
class Review:
    """One usable review after normalization (§7.1).

    `app` is the first-class source_app: comparative analysis breaks without it.
    """
    review_id: str
    app: str                        # Myntra / AJIO / Nykaa Fashion
    store: str                      # play / appstore / reddit / youtube / forum
    text: str                       # PII-scrubbed text ONLY
    rating: int | None              # 1-5; None for forum posts
    posted_date: str | None         # ISO YYYY-MM-DD (review date, not pull date)
    language: str                   # en / hinglish / other
    word_count: int
    relevance_flagged: bool         # lexicon hit (§7.3) — attention allocation only
    category_mentioned: list[str] = field(default_factory=list)
    source_url: str | None = None   # forum rows only
    cluster_id: int | None = None   # set in P2; -1 = noise
    # Forum provenance / tagging (docs/forum-ingestion-plan.md) — store="forum" rows only.
    source_type: str | None = None  # reddit / youtube / aggregator / web
    source_detail: str | None = None  # subreddit or aggregator page slug
    multi_brand: bool = False       # comparison thread emitted once per brand it discusses
    thread_id: str | None = None    # shared id across a multi-brand thread's records (no double-count)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Review":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


@dataclass
class Theme:
    """One cluster surviving to summarization (§9 Table 2). Populated in P2/P3.

    funnel_gate, mapping_rationale, what_this_means are HUMAN-owned (§7.6) and
    stay empty until the interpretive layer — never written by an LLM call.
    """
    theme_id: str
    theme_name: str = ""
    summary: str = ""
    review_count: int = 0
    pct_of_corpus: float = 0.0
    avg_rating: float | None = None            # reported, NEVER used to rank (§7.3)
    per_app: dict = field(default_factory=dict)   # {app_key: count}
    funnel_gate: str | None = None             # human-set, post-clustering
    mapping_rationale: str = ""                # human-written; mandatory when mapped
    what_this_means: str = ""                  # human 1-2 line brief (§8.3)
    category_mentioned: list[str] = field(default_factory=list)
    quote_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Quote:
    """One candidate quote incl. rejects — rejects are the validation evidence (§7.5)."""
    quote_id: str
    quote_text: str
    theme_id: str
    source_review_id: str | None = None        # set only on a validation pass
    validation_status: str = "Rejected - no source match"
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunLog:
    """Provenance, one row per pipeline run (§9 Table 4)."""
    run_id: str
    run_datetime: str
    raw_scraped: int = 0
    usable_after_normalization: int = 0
    per_app_counts: str = ""
    embedding_model: str = ""
    llm_model: str = ""
    clusters_found: int = 0
    themes_summarized: int = 0
    noise_pct: float = 0.0
    quotes_validated: int = 0
    quotes_rejected: int = 0
    spotcheck_agreement_pct: float | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
