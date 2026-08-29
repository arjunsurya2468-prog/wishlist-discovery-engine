# Wishlist Discovery Engine

AI discovery engine for the wishlist → purchase conversion brief (Myntra / AJIO /
Nykaa Fashion). Ingests public conversation at scale, clusters it without hypothesis
priming, and maps the resulting themes onto the wishlist funnel.

This repo is a **copy-forward** of the generic machinery from a previous discovery
engine built for a different brief. Nothing brief-specific was carried over. The
previous repo is untouched and remains the record of that submitted work.

## Status — read this before trusting any output

| Area | State |
|---|---|
| Embedding / clustering / ranking / publish | ✅ carried forward, domain-neutral |
| Deploy layer (Docker, Render, `/healthz`, rate limits) | ✅ carried forward |
| Lexicon, funnel map, prompts, interpret cards | ✅ rewritten for this brief |
| `config.APPS` + per-source validity | ✅ rewritten (STEP 4) |
| Corpus weighting (community = primary) | ✅ inverted (STEP 6) |
| Taxonomy corpus-fingerprint boot gate | ✅ built + tested (STEP 7) |
| Sample gate harness | ✅ built (STEP 8) |
| **Reddit ingestion** | ❌ **NOT REBUILT** — RSS fallback only, awaiting Apify rewrite |
| **YouTube ingestion** | ❌ **DOES NOT EXIST** |
| **X/Twitter ingestion** | ❌ **NOT BUILT, NOT SAMPLED** — see below |
| **Forum targets** | ❌ fashion targets not chosen |
| **Taxonomy artifact** | ❌ none — must be trained on the fashion corpus |
| **MVP** | ❌ not started |
| Orchestrator (`pipeline/run.py`) | ✅ written fresh (not ported) |
| Sample-gate ledger enforcement | ✅ `ingest` refuses unapproved sources |

**The engine cannot currently ingest its primary corpus.** Store-review ingestion works;
community ingestion does not.

## Corpus weighting

Community/discussion text is the **primary** corpus and the denominator for every
headline statistic. App/Play Store reviews are **secondary** corroboration.

Store reviews are written at moments of transactional friction, by people who already
transacted. Someone with twelve saved kurtas and no purchase has no reason to write one.
The reasoning this brief asks about lives in community text. See `pipeline/corpus.py`.

## Nykaa Fashion is store-only

`config.apps_for(source)` excludes Nykaa Fashion from every community source. In
community text "nykaa" overwhelmingly refers to the beauty vertical; a keyword filter
cannot separate the two reliably. The exclusion is structural, not a downstream filter.
Enforced by `tests/test_taxonomy_gate.py::test_nykaa_fashion_excluded_from_community_sources`.

## The taxonomy boot gate

`app/backend/main.py` refuses to start unless the shipped taxonomy carries a corpus
fingerprint matching this deployment. A taxonomy trained on a different corpus does not
error at assignment time — it returns a nearest centroid for every input and fills the
dashboard with confident, meaningless themes. There is no downstream check that catches
this, so it is caught at boot. See `pipeline/cluster/fingerprint.py`.

```bash
curl localhost:8000/healthz    # reports domain, apps, corpus_hash of the live taxonomy
```

## X/Twitter is undecided, not dropped

The cost case is fine — X moved to pay-per-use in Feb 2026 at $0.005/read, no monthly
minimum. The open question is signal quality, and it has **not been measured**: X search
is behind auth (HTTP 402) and general web search does not index post bodies, so no
hit-rate sample was obtainable. The prior reasoning (wishlist deliberation is long-form,
tweets are short) remains an assertion.

A real sample costs about **$1** (200 post reads). Until one is run, `sources.py` records
this source as NOT SAMPLED and no drop decision is on file. Do not put a sampled-and-
excluded claim in the deck without the number behind it.

## Before any full scrape

```bash
python -m scripts.sample_gate --source play --app Myntra -n 75
```

Reports the wishlist-relevance hit-rate on a small sample. Full scrape or drop is a
human decision, per source. Never run full ingestion on an unsampled source.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add OPENROUTER_API_KEY, APIFY_API_KEY, YOUTUBE_API_KEY
python -m pytest tests/ -q
```

Store IDs in `config.APPS` are **unverified placeholders**. `config.verify_app_ids()`
lists them. A wrong id returns an empty scrape that looks like "no reviews" — verify
before reading anything into a zero result.

## Privacy

`extras/` and `interviews/` are gitignored from the first commit. Primary-research
material (5–6 participant interviews) never enters git history.
