"""Relevance lexicon — a transparent, versioned attention-allocation flag.

This flag NEVER filters or reorders text at ingestion and NEVER influences
clustering. It only (a) tags a record as wishlist/uncertainty/comparison-relevant
so the summarization budget can later be aimed, and (b) records which uncertainty
axis the record touches. The lexicon is illustrative and tunable — bump
LEXICON_VERSION on any change so runs stay auditable.

Fashion build. The taxonomy below is the set of UNCERTAINTY AXES the brief asks
about (fit, size, quality, price, returns, styling, occasion, social validation),
NOT a product-category taxonomy. That is the deliberate change from the previous
build: for this brief the question is "what stops the purchase", not "which
category does the user mention".

AXIS FREQUENCIES FROM THIS LEXICON ARE NOT A FINDING.
=====================================================
This list is HAND-AUTHORED, illustrative, and non-exhaustive. Reading "Price fired
on 34% of records" as evidence that price is the dominant blocker would be reading
the authorship of this file, not the corpus: an axis with more terms, or with more
GENERIC terms, fires more often regardless of what users actually said. Price in
particular double-counts, because sale/price-drop language appears in BOTH
AXIS_TERMS["Price"] and POSTPONE_PHRASES.

The flag is for AIMING ATTENTION (which records a human or a summarizer should
read first) and nothing else. The real uncertainty taxonomy comes from unsupervised
clustering over the embedding space, which has no hand-authored priors. Any headline
about relative cause frequency must come from cluster sizes, never from here.
"""
from __future__ import annotations

import re

LEXICON_VERSION = "2026-08-20.2"  # + Decision fatigue / Forgetting axes; postpone vetoes

# Uncertainty axes -> the axis_mentioned taxonomy used downstream.
# These map directly onto the brief's stated questions (fit, size, styling, price,
# reviews, occasion, social validation).
AXIS_TERMS: dict[str, list[str]] = {
    "Fit": [
        "fit", "fits", "fitting", "didn't fit", "doesnt fit", "does not fit",
        "too tight", "too loose", "too small", "too big", "oversized",
        "true to size", "runs small", "runs large", "body type", "measurements",
    ],
    "Size": [
        "size", "sizing", "size chart", "size guide", "which size", "what size",
        "size up", "size down", "m or l", "s or m", "l or xl", "wrong size",
    ],
    "Quality": [
        "quality", "fabric", "material", "cloth", "stitching", "cheap material",
        "see through", "sheer", "thin fabric", "durability", "wash", "shrink",
        "colour fade", "color fade", "faded",
    ],
    "Price": [
        "price", "priced", "expensive", "costly", "overpriced", "budget",
        "price drop", "wait for sale", "waiting for sale", "sale", "eors",
        "end of reason sale", "big fashion festival", "discount", "coupon",
        "deal", "worth the price", "worth it",
    ],
    "Returns": [
        "return", "returns", "return policy", "exchange", "exchange policy",
        "refund", "non returnable", "non-returnable", "return window",
        "easy returns", "return charges", "pickup",
    ],
    "Styling": [
        "styling", "style", "how to style", "what to wear with", "pair it",
        "pairing", "goes with", "outfit", "look", "wardrobe",
    ],
    "Occasion": [
        "occasion", "wedding", "party", "office wear", "formal", "casual",
        "festive", "diwali", "date night", "interview", "everyday wear",
    ],
    "Social validation": [
        "opinion", "what do you think", "should i buy", "thoughts on",
        "does it look good", "suits me", "friends said", "asked my", "second opinion",
        "reviews said", "review photos", "customer photos", "real photos",
    ],
    "Model reference": [
        "model", "on the model", "looks different on", "model photo",
        "height and size", "model is wearing", "photoshopped", "looks nothing like",
    ],
    "Colour accuracy": [
        "colour", "color", "colour difference", "color difference", "shade",
        "different in person", "not the same colour", "not the same color",
        "lighting", "screen colour", "screen color",
    ],
    # The two axes below were MISSING until 2026-08-20.2, and their absence was not
    # neutral. Decision-fatigue and forgetting language lived only in POSTPONE_PHRASES
    # and WISHLIST_TERMS, which carry no axis — so a record saying "I just cant decide"
    # resolved to (postpone=True, axes=[]) and reported as NO axis at all, while a
    # record saying "waiting for the sale" resolved to (postpone=True, axes=["Price"])
    # and was counted twice. Any axis tally was therefore structurally guaranteed to
    # under-report these two and over-report Price, independent of the corpus.
    #
    # 8 of the 17 POSTPONE_PHRASES are decision-fatigue phrasings; 3 are price-implying.
    # The instrument was blind to its own largest category.
    "Decision fatigue": [
        "can't decide", "cant decide", "cannot decide", "torn between",
        "confused between", "on the fence", "second thoughts", "overthinking",
        "too many options", "too many choices", "analysis paralysis",
        "keep changing my mind", "changed my mind", "still deciding",
    ],
    "Forgetting": [
        "forgot about it", "forgot i saved", "forgot i had", "been sitting there",
        "been sitting in my", "lost track", "never looked at it again",
        "out of sight", "completely forgot", "didn't even remember",
        "didnt even remember", "only just noticed",
    ],
}

# Wishlist behaviour terms — the core signal for THIS brief. A record hitting any
# of these is describing the save/return/convert behaviour the engine exists to explain.
WISHLIST_TERMS = [
    "wishlist", "wish list", "wishlisted", "saved item", "saved items", "saved it",
    "save for later", "saved for later", "bookmark", "bookmarked", "shortlist",
    "shortlisted", "added to cart", "in my cart", "cart for months", "abandoned cart",
    "never bought", "never ordered", "still haven't bought", "still havent bought",
    "keep postponing", "been sitting in my", "forgot about it", "waiting to buy",
]

# Postponement / hesitation phrasing — why the purchase does not happen now.
POSTPONE_PHRASES = [
    "waiting for", "will buy later", "buy it later", "maybe later", "next month",
    "after salary", "when it goes on sale", "if the price drops", "not sure if",
    "confused between", "can't decide", "cant decide", "torn between",
    "thinking about it", "on the fence", "second thoughts", "hesitant",
]

# Objects that make a postponement phrase CONTENT postponement rather than PURCHASE
# postponement. "waiting for" is the highest-frequency postpone phrase, and in a
# YouTube comment section it fires overwhelmingly on "waiting for part 2" / "waiting
# for your next haul" — noise that lands in the gate's headline hit-rate.
#
# THIS VETO IS AXIS-NEUTRAL BY CONSTRUCTION, and that is the whole point. The obvious
# alternative — narrowing "waiting for" to (sale|price drop|discount|restock) — would
# make postpone-detection PRICE-SHAPED: waiting-for-salary, waiting-to-decide and
# waiting-for-an-occasion would stop being detected at all, and price would then
# dominate the findings as a pure artifact of this file. Removing non-purchase
# postponement of every kind is safe; keeping only one kind is not.
#
# "a review" / "the review" are deliberately NOT vetoed: "waiting for a review before
# I buy" is genuine uncertainty-resolution and squarely on-thesis.
POSTPONE_META_OBJECTS = [
    "part 2", "part two", "part 3", "part three", "the video", "next video",
    "the next video", "your next", "episode", "the upload", "your reply",
    "a reply", "the link", "the giveaway", "results",
]
POSTPONE_VETO_WINDOW = 30   # chars after the match to inspect for a meta object

# Cross-platform reference — where users go to resolve uncertainty OUTSIDE the app.
# The brief explicitly asks what information users seek outside Myntra/AJIO.
#
# DENOMINATOR CAVEAT (record now, applies at interpretation): this list contains
# "youtube", "reddit" and "instagram". On a YouTube-sourced corpus every "saw this on
# youtube" fires it, so external-source rates computed over YouTube records are
# inflated relative to store-review records. Any cross-source comparison of "where do
# users look outside the app" must state which corpus its denominator came from.
EXTERNAL_SOURCES = [
    "amazon", "flipkart", "meesho", "tata cliq", "tatacliq", "shein", "zara",
    "h&m", "hm", "uniqlo", "instagram", "youtube", "reddit", "pinterest",
    "google", "review video", "haul video", "try on", "tryon", "store",
    "offline store", "mall", "showroom", "friend", "sister", "mom",
]


def _compile(term: str) -> re.Pattern:
    # Word-boundary match so "fit" doesn't fire inside "outfit"; phrases match literally.
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)


_AXIS_RE = {axis: [_compile(t) for t in terms] for axis, terms in AXIS_TERMS.items()}
_WISHLIST_RE = [_compile(t) for t in WISHLIST_TERMS]
_POSTPONE_RE = [re.compile(re.escape(p), re.IGNORECASE) for p in POSTPONE_PHRASES]
_META_RE = [re.compile(re.escape(m), re.IGNORECASE) for m in POSTPONE_META_OBJECTS]
_EXTERNAL_RE = [_compile(t) for t in EXTERNAL_SOURCES]


def _postpone_hits(text: str) -> tuple[int, int]:
    """(kept, vetoed) postpone matches after content-postponement vetoes.

    LIMITATION — the veto is TRAILING-WINDOW ONLY. It inspects the
    POSTPONE_VETO_WINDOW characters *after* the matched phrase, so reversed or
    distant constructions are not caught: "part 2 is what I'm waiting for",
    "your next haul — waiting for it!". Those still count as postpone hits.

    Consequence for reporting: the vetoed count is a FLOOR on content-postponement
    noise, never a total. Do not present it as "the noise has been removed" — present
    it as "at least this much was removed". If a gate shows residual noise, the next
    step is requiring co-occurrence with a purchase object, not widening this list.
    """
    kept = vetoed = 0
    for pat in _POSTPONE_RE:
        for m in pat.finditer(text):
            window = text[m.end():m.end() + POSTPONE_VETO_WINDOW]
            if any(mp.search(window) for mp in _META_RE):
                vetoed += 1
            else:
                kept += 1
    return kept, vetoed

# Brand self-mention exclusion: a record's OWN brand never flags it (self-mention is
# generic). Built from config at call time so it tracks config.APPS automatically.
def _self_terms(app: str | None) -> set[str]:
    if not app:
        return set()
    from .. import config
    spec = config.APPS.get(app)
    return set(spec.community_terms) if spec else set()


def flag_detailed(text: str) -> dict:
    """Return which trigger types fired: axes, wishlist, postponement, external refs."""
    axes = [a for a, pats in _AXIS_RE.items() if any(p.search(text) for p in pats)]
    wishlist = any(p.search(text) for p in _WISHLIST_RE)
    kept, vetoed = _postpone_hits(text)
    external = [EXTERNAL_SOURCES[i] for i, p in enumerate(_EXTERNAL_RE) if p.search(text)]
    return {"axes": axes, "wishlist": wishlist,
            "postpone": kept > 0, "postpone_vetoed": vetoed,
            "external": external}


def flag(text: str, app: str | None = None) -> tuple[bool, list[str]]:
    """Return (relevance_flagged, axes_mentioned).

    Flagged if the text hits an uncertainty axis, wishlist behaviour language, a
    postponement phrase, or an external-source reference other than the record's own
    brand. A record's own brand name never flags it — self-mention is generic.
    """
    d = flag_detailed(text)
    self_terms = _self_terms(app)
    cross_external = [e for e in d["external"] if e.lower() not in self_terms]
    flagged = bool(d["axes"]) or d["wishlist"] or d["postpone"] or bool(cross_external)
    return flagged, d["axes"]


# Back-compat alias: downstream modules carried forward from the previous build refer
# to CATEGORY_TERMS. The concept is now uncertainty axes; the name is kept so the
# rename lands in one place rather than being scattered through the pipeline.
CATEGORY_TERMS = AXIS_TERMS
