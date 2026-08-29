"""Central configuration — the single source of truth for the pipeline.

Every secret is env-loaded here; every tunable knob is a named constant here.
No other module reads os.environ or hard-codes a threshold (implementation-plan P0).
Reference tags like (§6) point to docs/problemStatement.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---- Paths ----
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
EMBED_DIR = DATA_DIR / "embeddings"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
ANALYSIS_DIR = DATA_DIR / "analysis"
INTERPRET_DIR = DATA_DIR / "interpret"


# ---- Apps: primary + comparators, with PER-APP SOURCE VALIDITY (STEP 4) ----
# Source validity is declared per app, not filtered downstream by keyword.
#
# WHY Nykaa Fashion is store-only: in community text ("nykaa"), the token refers
# overwhelmingly to the BEAUTY vertical, not Nykaa Fashion. A keyword filter cannot
# separate them reliably — beauty discussion would enter a fashion wishlist corpus and
# poison every downstream cluster. The exclusion is therefore STRUCTURAL: Nykaa Fashion
# is never queried on reddit/youtube/twitter/forum at all.

SOURCES = ("play", "appstore", "reddit", "youtube", "twitter", "forum")
STORE_SOURCES = frozenset({"play", "appstore"})
COMMUNITY_SOURCES = frozenset({"reddit", "youtube", "twitter", "forum"})


@dataclass(frozen=True)
class AppSpec:
    key: str                        # canonical single-select value used everywhere
    role: str                       # "primary" | "comparator"
    play_package: str
    appstore_id: str                # "" == UNVERIFIED, see verify_app_ids()
    sources: frozenset              # the ONLY sources this app may be ingested from
    community_terms: tuple          # search terms for community sources; () when excluded

    def allows(self, source: str) -> bool:
        return source in self.sources


# ---- Sibling-listing blocklist (STEP 4, hardened) ----
# Nykaa ships THREE separate listings under one developer. Nykaa Fashion is the one in
# scope; Nykaa Beauty and Nykaa Man are not. Their package names are close enough that a
# typo pulls beauty reviews into a fashion corpus, and nothing downstream would flag it —
# the reviews are well-formed, in-language, and about shopping. They would simply be
# about the wrong products.
#
# This is enforced as a hard blocklist checked at import time, not as a comment, because
# a comment does not stop a fat-fingered edit six weeks from now.
BLOCKED_STORE_IDS: dict[str, str] = {
    # Nykaa Beauty
    "com.fsn.nykaa": "Nykaa Beauty (Android) — beauty vertical, out of scope",
    "1022363908": "Nykaa Beauty (iOS) — beauty vertical, out of scope",
    # Nykaa Man
    "com.fsn.nykaa.man": "Nykaa Man (Android) — separate listing, out of scope",
}

# Any Android package under this prefix is a Nykaa vertical that is NOT Nykaa Fashion.
# Nykaa Fashion is com.fsn.nds, which deliberately does not share the prefix.
BLOCKED_PACKAGE_PREFIXES: tuple = ("com.fsn.nykaa",)


APPS: dict[str, AppSpec] = {
    "Myntra": AppSpec(
        key="Myntra", role="primary",
        play_package="com.myntra.android",   # not independently confirmed
        appstore_id="907394059",             # verified
        sources=frozenset({"play", "appstore", "reddit", "youtube", "twitter", "forum"}),
        community_terms=("myntra",),
    ),
    "AJIO": AppSpec(
        key="AJIO", role="comparator",
        play_package="com.ril.ajio",         # not independently confirmed
        appstore_id="1113425372",            # verified
        sources=frozenset({"play", "appstore", "reddit", "youtube", "twitter", "forum"}),
        community_terms=("ajio",),
    ),
    "Nykaa Fashion": AppSpec(
        key="Nykaa Fashion", role="comparator",
        play_package="com.fsn.nds",          # verified — NOT com.fsn.nykaa (that is Beauty)
        appstore_id="1439872423",            # verified
        # APP STORES ONLY — structural exclusion, see note above.
        sources=frozenset({"play", "appstore"}),
        community_terms=(),
    ),
}


class BlockedStoreIdError(ValueError):
    """Raised when an AppSpec points at an out-of-scope sibling listing."""


def _assert_no_blocked_ids(apps: dict = None) -> None:
    """Fail at import if any app points at a blocked sibling listing.

    Import-time rather than scrape-time on purpose: the whole failure mode is that a
    wrong-but-valid package scrapes cleanly and silently contaminates the corpus. The
    only safe place to catch it is before anything runs.
    """
    for key, spec in (apps or APPS).items():
        for field, value in (("play_package", spec.play_package),
                             ("appstore_id", spec.appstore_id)):
            if value in BLOCKED_STORE_IDS:
                raise BlockedStoreIdError(
                    f"{key}.{field} = {value!r} is BLOCKED: {BLOCKED_STORE_IDS[value]}.\n"
                    f"  This listing is a different product from the one in scope. Scraping it "
                    f"returns well-formed reviews about the wrong catalogue, and no downstream "
                    f"check would notice."
                )
        for prefix in BLOCKED_PACKAGE_PREFIXES:
            if spec.play_package.startswith(prefix):
                raise BlockedStoreIdError(
                    f"{key}.play_package = {spec.play_package!r} starts with blocked prefix "
                    f"{prefix!r} — that namespace is Nykaa Beauty / Nykaa Man, not Nykaa "
                    f"Fashion. Nykaa Fashion is 'com.fsn.nds'."
                )


def apps_for(source: str) -> list[AppSpec]:
    """The apps a given source may ingest. The single gate every scraper must call.

    A scraper that iterates config.APPS directly bypasses the Nykaa exclusion —
    always route through here.
    """
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}; choose from {SOURCES}")
    return [spec for spec in APPS.values() if spec.allows(source)]


def verify_app_ids() -> list[str]:
    """Return app keys whose store IDs are still unset.

    All iOS ids are human-verified. The Myntra and AJIO Android packages are the
    conventional ones but were not independently confirmed — the STEP 8 sample pull
    confirms them, since a wrong package returns an empty scrape rather than an error.
    """
    return [k for k, sp in APPS.items() if not sp.appstore_id or not sp.play_package]


# Enforced on import. Nothing in this package can run with a blocked listing wired in.
_assert_no_blocked_ids()


COUNTRY = "in"  # §6: country='in' for both stores

# ---- Ingestion knobs (§6, §7.1) ----
WORD_FLOOR = 8                    # drop reviews under this many words after scrub
SCRAPE_TARGET_PER_APP = 15_000    # Play Store per-app ceiling target (§6)
SCRAPE_MAX_MONTHS = 24            # stop paginating past this review age (§6)
PRIMARY_WINDOW_MONTHS = 12        # headline-stats window; applied downstream, NOT at ingest
PLAY_BATCH = 200                  # google-play-scraper page size (its practical max)
APPSTORE_RSS_MAX_PAGES = 10       # iTunes RSS hard ceiling (~50 reviews/page)
SCRAPE_PAGE_PAUSE_SEC = 0.4       # politeness delay between paginated requests
ML_FLOOR = 20                     # abort clustering below this many usable reviews (§7.2)

# ---- Embedding / clustering — declared now (P0), consumed in P2 ----
# Embeddings are PROVIDER-PREFIXED like the LLM. "gemini/" routes to Google's
# generativelanguage API; anything else goes to OpenRouter's OpenAI-compatible endpoint.
#
# Groq hosts NO embedding models (verified: 404), so Groq was never an option here.
# Gemini is the free path that does not cost quality: gemini-embedding-001 returns
# 3072-dim vectors — identical dimensionality to openai/text-embedding-3-large — on a
# free tier, versus OpenRouter's free embed model at 2048 dims behind a 50-req/day cap.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-large")
EMBEDDING_CHALLENGER = "qwen/qwen3-embedding-8b"
# 100 is Gemini's hard ceiling: batchEmbedContents rejects >100 with HTTP 400
# ("at most 100 requests can be in one batch"). It is also exactly the free-tier
# per-minute quota, since each item in a batch counts as one embed request.
EMBED_BATCH_SIZE = 100            # inputs per /embeddings call
UMAP_PARAMS = {"n_neighbors": 15, "n_components": 5, "random_state": 42}
# min_cluster_size is CARRIED FORWARD UNTUNED from the previous corpus. It must be
# re-swept against the fashion corpus before it means anything — the sweep is part of
# the first full clustering run, not an inherited constant.
HDBSCAN_PARAMS = {"min_cluster_size": 10, "min_samples": 3}
NOISE_RETRY_THRESHOLD = 0.90      # noise fraction above which we retry once (edge-cases §3)
GIANT_CLUSTER_THRESHOLD = 0.80    # one cluster > this share of clustered -> flag re-split (§3)

# ---- LLM naming & summarization — declared now (P0), consumed in P3 ----
# LLM routing is PROVIDER-PREFIXED. A model id starting with "groq/" is sent to Groq's
# OpenAI-compatible endpoint; everything else goes to OpenRouter. Groq is used here
# because OpenRouter's free tier caps at 50 requests/day, which is below what a single
# naming run needs — Groq's free tier is 1,000 RPM / 250k TPM.
LLM_MODEL = os.getenv("LLM_MODEL", "groq/qwen/qwen3.8-27b")
# NOT qwen3.6-27b: it returns HTTP 400 ("Failed to validate JSON") under json_object
# mode, so it cannot serve as a degraded path for a strict-JSON call. gpt-oss-120b was
# verified live against the real naming prompt.
LLM_FALLBACK_MODEL = "groq/openai/gpt-oss-120b"   # degraded path (§7.4)
MAX_TOKENS_PER_RUN = 200_000
LLM_MIN_SPACING_SEC = 2.0

# ---- Live run — declared now (P0), consumed in P5 ----
LIVE_RUN_MAX_PER_SESSION = 3
LIVE_RUN_COOLDOWN_SEC = 60
LIVE_RUN_FETCH = 100
LIVE_RUN_TIMEOUT_SEC = 30         # hard ceiling on a single live run (endpoint bounds total time)
LIVE_RUN_EMBED_TIMEOUT_SEC = 20   # per-request embed timeout on the live path (fail fast)
LIVE_RUN_IP_MAX_PER_WINDOW = 10   # per-IP cap (independent of the cookie session)
LIVE_RUN_IP_WINDOW_SEC = 3600     # rolling window for the per-IP cap

# ---- Exploration engine (Link B) ----
# Per-IP cap on /api/suggest, which is an unauthenticated endpoint that can reach a paid model.
# Higher than the live-run cap because clicking presets is the intended demo behaviour and most
# clicks are served from cache; it exists to bound a hammering client, not to ration an evaluator.
# Shares LIVE_RUN_IP_WINDOW_SEC but NOT the live-run bucket — see ratelimit.check_ip.
SUGGEST_IP_MAX_PER_WINDOW = 300

# ---- Community / discussion corpus (STEP 5 + STEP 6) ----
# CORPUS WEIGHTING INVERTS vs the previous build. Community/discussion text is now the
# SPINE of the corpus, not a depth supplement. Wishlist-abandonment reasoning ("saved it,
# never bought it, here's why") does not appear in app store reviews — those are dominated
# by delivery, returns, refunds and app bugs. See corpus.py PRIMARY_SOURCES.
FORUM_DIR = CACHE_DIR / "_forums"
FORUM_TEXT_MAX_CHARS = 6000

# ---- Reddit (STEP 5: PENDING REWRITE against Apify — query-targeted, not sub dumps) ----
# The RSS/JSON transport carried forward from the previous build is a FALLBACK and is
# not considered the delivery path for this brief. Do not treat reddit.py as complete.
REDDIT_TRANSPORT = os.getenv("REDDIT_TRANSPORT", "apify")   # apify | rss (fallback)
APIFY_API_KEY = os.getenv("APIFY_API_KEY")
APIFY_REDDIT_ACTOR = os.getenv("APIFY_REDDIT_ACTOR", "trudax/reddit-scraper-lite")
REDDIT_USER_AGENT = "WishlistDiscoveryResearch/1.0 (public read)"
REDDIT_RATE_SEC = 2.0
REDDIT_RSS_RATE_SEC = 6.0
REDDIT_RSS_BACKOFF_SEC = 30
REDDIT_WINDOW = "year"
REDDIT_RESULTS_PER_QUERY = 100
REDDIT_MAX_QUERIES = 40
REDDIT_MAX_COMMENT_THREADS = 30
REDDIT_TOP_COMMENTS = 20

# Query-targeted search terms — the wishlist/abandonment behaviour, NOT brand firehose.
# Brand terms come from AppSpec.community_terms and are combined with these.
# AXIS TERMS DELETED — same principle as YOUTUBE_VIDEO_QUERIES above. The previous
# list carried "size doubt", "sizing confusion", "will it fit", "true to size",
# "fabric quality", "quality check", "worth buying" (axis-seeded) and "waiting for
# sale" / "waiting for price drop" (price-seeded). Every one of them pre-supposes the
# root cause and would have produced its own confirmation.
#
# What remains is behaviour-shaped only: the SAVE, the NON-PURCHASE, and the
# retrospective. Why it did not convert is left entirely to the text.
REDDIT_QUERY_TERMS = [
    # S1 — wishlist core: the save happened, the purchase did not
    "wishlist", "saved items", "never bought",
    # S2 — postpone: purchase deferred, cause unspecified BY DESIGN
    "been in my cart", "keep postponing", "didnt buy",
    # S4 — retrospective: haul/review talk where deliberation is narrated
    "haul review", "what i actually kept",
]
# Communities where fashion purchase-hesitation talk actually lives.
# CARRIED FORWARD AS A PROPOSAL ONLY — validate hit-rate via STEP 8 before full scrape.
#
# Trimmed from 8. Dropped: FemaleFashionAdvice and malefashionadvice (US-centric —
# Myntra/AJIO barely appear), and IndianStreetBets (a stocks sub, where "Myntra" is
# EQUITY talk, not shopping — right keyword, wrong corpus profile, the same reasoning
# that folded MouthShut/ConsumerComplaints out of scope).
#
# These 5 are a RANKING signal, not a query multiplier: queries run site-wide and the
# benchmark reports which subs actually yielded, so the list expands from measured
# data rather than from guesses about which sub names exist.
REDDIT_SUBS_PROPOSED = [
    "IndianFashionAddicts", "IndianFashion", "india", "TwoXIndia", "DesiFashion",
]

# Exclusion list: subs that match keywords but carry the wrong corpus profile.
# Built empirically from STEP 8 gate benchmarks (RSS task-170 + Apify task-250).
# Same reasoning as the IndianStreetBets drop: right keyword, wrong talk.
#
# Category 1 — SELF-PROMO / APP-LAUNCH subs. Users advertising their own
# price-tracker/wishlist tools. Matches "wishlist" but it's marketing copy,
# not genuine purchase deliberation.
# Category 2 — DEAL-AGGREGATOR / REFERRAL subs. Coupon/cashback/referral spam.
# Mentions brands but never surfaces hesitation, only discount mechanics.
REDDIT_SUBS_EXCLUDED = {# Cat 1: self-promo / app-launch (inflated RSS 53.4% by 42%)
    "SaasDevelopers", "ProductHunters", "RoastMyApp", "alphaandbetausers",
    "droidappshowcase", "AndroidClosedTesting", "TestersCommunity",
    "swipeyield", "prettyusefulwebsites", "chrome_extensions",
    "fucksavana_",
    # Cat 2: deal-aggregator / referral spam
    "topdealsfinder", "LooteraShopper", "10MinDeals", "dealsforindia",
    "IndianGlamDeals", "IndianBeautyDeals", "CashbackWarriors",
    "OnlineBuyIndia", "IndiaReferral", "Lootdealsforindia",
    "IndiaMegaDeals", "HotDealsIndia", "IndiaDealsExchange",
    # Cat 3: unrelated verticals that pollute brand queries (beauty, finance, watches)
    "IndianSkincareAddicts", "DesiFragranceAddicts", "IndianMakeupAddicts", "KultCult",
    "CreditCardsIndia", "IndiaInvestments", "PersonalFinanceIndia", "CreditCardIndia",
    "hmtwatches", "WatchesIndia", "watches",

    "IndiaLegoDeals", "GoldIndia", "GoldSilverIndia", "silverindia", "SneakersIndia", "SneakerheadsIndia", "watchesindia", "IndianBeautyTalks", "indianbeautyhauls", "indianbeautyyappers", "IndianBeautyDeals", "indianhaircareaddict", "headphonesindia", "personalfinanceindia", "CreditCardsIndia_", "pFinTools", "LooteraShopper", "topdealsfinder", "dealsforindia", "IndiaGlamDeals", "10MinDeals", "Raw_n_real_finance", "GoldSilverDealsIndia", "LegalAdviceIndia", "indianstartups", "SideProject", "StockMarketIndia", "surveyexchangeindia", "AskIndianWomen", "ticktocktreasures", "IsThisAScamIndia", "india", "indianrunners", "indiasocial", "ask_Bondha", "internationalshopper", "HindiMemes", "delhi", "Raipur", "getyourdeals", "twoxindiamums", "bestcouponsindia", "SavingAround", "wherecanibuythis", "Gifts", "NoStupidQuestions", "Frugal_Ind", "EcommerceIndia", "betatests", "offerindia", "InPoints", "khatarnakdeals", "india_cycling", "IndiaLaw", "PerfumeIndia", "scamindia", "ConsumerAdvice", "findfashion", "microsaas", "trekkingIndia", "BuyItForLifeIndia", "shopify", "ecommerce", "ShopifyeCommerce", "bondha_diaries", "indianfitness", "iemlndia", "IndianEntrepreneur", "SurveyExchangeIndia", "TeluguJournals", "MicrosoftRewardsIndia", "delhimarketplace", "hyderabad", "ThirtiesIndia", "PartneredYoutube", "IndianCyberHub", "AskIndia", "cardreviewsindia", "stockphotography", "IndiaBusiness", "StartUpIndia", "SurveyExchange", "BangaloreSocial", "office", "ShoppingSecretDeal", "tech_flames", "shopnery", "AndroidHelp", "kolkata", "IndianClassified", "vouchershunt", "SonyHeadphones", "Scams", "tamilyapping"}

# ---- YouTube (STEP 5) ----
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# SEED SET: DELIBERATION CONTEXTS ONLY. ZERO AXIS TERMS.
#
# Earlier drafts of this list carried size/quality queries and EORS/sale queries.
# Both were removed, and the reason is the design principle for this whole corpus:
# querying by axis MANUFACTURES the relative frequencies the corpus exists to
# MEASURE. Search for "myntra size issue" and you will find size issues; the
# resulting 30%-of-corpus-is-sizing figure is a property of the query, not of how
# users behave. Choosing a problem from numbers produced that way is choosing it
# from your own priors with extra steps.
#
# Haul and honest-review comment sections are places where people narrate purchase
# deliberation to each other unprompted. Fit, price, quality, decision-fatigue,
# forgetting, and whatever nobody has thought of yet all surface there at their
# NATURAL BASE RATES. That is the measurement.
#
# IF THE GATE SHOWS THE CORPUS IS THIN: expand UNIFORMLY — more haul/review query
# phrasings, more brands, more pages. NEVER by adding an axis query. Adding one
# axis query to fix thin yield silently converts this corpus from a measurement
# into a confirmation.
YOUTUBE_VIDEO_QUERIES = [
    "myntra haul",
    "myntra try on haul",
    "myntra haul honest review",
    "myntra review what i actually bought",
    "what i actually bought from my myntra wishlist",
    "ajio haul",
    "ajio try on haul",
    "ajio haul honest review",
]

# search.list bills a flat 100 units per call regardless of how many of its (max 50)
# results you keep. Truncating to 25 therefore discards results already paid for.
# Keeping 50 costs only Stage B: ~2 units/video, so +25 videos/query ≈ +400 units
# total, and roughly doubles corpus size for ~4% of the daily budget.
YOUTUBE_MAX_VIDEOS_PER_QUERY = 50
YOUTUBE_COMMENTS_PER_VIDEO = 200      # 100/page -> 2 commentThreads.list calls
YOUTUBE_SEARCH_PAGES = 1              # pagination on SEARCH is the expensive dimension

# Hard ceiling on search.list calls per run. 100 units each, so 40 calls = 4,000 of
# the 10,000/day budget. Quota resets midnight Pacific, so a runaway loop does not
# cost money — it costs a CALENDAR DAY, which on this deadline is worse.
YOUTUBE_MAX_SEARCH_CALLS = 40

# ---- X/Twitter (STEP 5: FEASIBILITY ASSESSMENT ONLY — not built, see report) ----
TWITTER_ENABLED = False

# Aggregator fallback (Firecrawl) — hard-capped. Targets are NOT yet chosen for fashion.
FORUM_FIRECRAWL_CAP = 150
FORUM_SEED_URLS: list[str] = []       # STEP 5: fashion targets to be proposed, not assumed
FORUM_AGG_QUERIES: list[str] = []     # STEP 5: pending

# ---- Secrets: env only. Never hard-code, never log, never write to an artifact. ----
# OpenRouter is the SINGLE provider — embeddings (§7.2) and the LLM (§7.4) both
# route through it (OpenAI-compatible schema). No separate direct-OpenAI key.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Provider endpoints for the prefixed-routing scheme above.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_EMBED_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_PREFIX = "gemini/"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_PREFIX = "groq/"


def resolve_llm(model_id: str) -> tuple[str, str, str]:
    """Map a prefixed model id -> (url, api_key, provider_model_id).

    Keeps provider selection in ONE place. Without this the naming client would have
    to know which vendor each model string belongs to, and a mis-set model would fail
    as a confusing 401 from the wrong provider rather than a clear routing error.
    """
    if model_id.startswith(GROQ_PREFIX):
        return GROQ_URL, GROQ_API_KEY, model_id[len(GROQ_PREFIX):]
    return OPENROUTER_URL, OPENROUTER_API_KEY, model_id
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GOOGLE_SHEETS_CREDS_FILE = os.getenv("GOOGLE_SHEETS_CREDS_FILE")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Blind-eval: neutral name on the public artifact — no personal/cohort identifier.
# One naming stem everywhere (repo/service/site): "wishlist-discovery".
PROJECT_NAME = "Wishlist Discovery Engine"


def today_str() -> str:
    """Cache-partition date; the pull date, not the review date."""
    return date.today().isoformat()
