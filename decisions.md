# decisions.md — authoritative project state

**Brief:** NextLeap graduation project (re-attempt). Increase % of users who purchase at least
one item from their wishlist within 30 days of adding it.
**Deadline:** 5 Sep 2026, 15:59:00 IST. Hard. No late submissions.
**Hard constraint from brief:** NO monetary incentives in the solution.
**Blind eval:** no name, no personal identifiers, anywhere in deliverables or file metadata.

---

## Locked decisions

**Platform: Myntra (primary).** Chosen on community-discussion depth, NOT review volume.
Review volume was never the binding constraint last time — corpus blindness was.

**Comparators:** AJIO (all sources). Nykaa Fashion (APP STORES ONLY — "Nykaa" in community
text is overwhelmingly the beauty vertical; do not rely on keyword filtering to separate them).

**Verified app IDs:**

| | iOS | Play |
|---|---|---|
| Myntra | 907394059 | com.myntra.android *(unverified, high confidence)* |
| AJIO | 1113425372 | com.ril.ajio *(unverified, high confidence)* |
| Nykaa Fashion | 1439872423 | com.fsn.nds |

**Blocklist (enforced at import in config.py, prefix rule):** com.fsn.nykaa* , 1022363908,
com.fsn.nykaa.man. Nykaa Beauty and Nykaa Man share the `com.fsn.nykaa` prefix; Fashion
(`com.fsn.nds`) deliberately does not.

**Corpus weighting is INVERTED vs the previous project.** App/Play Store reviews are the
SECONDARY source. Wishlist-abandonment reasoning does not appear in app store review text —
that corpus is complaint-state and post-purchase. Community/discussion text is the spine.
diagnostics.py and all coverage reporting must reflect this.

---

## Sources

| Source | Status |
|---|---|
| Play Store | scraper exists, IDs wired |
| App Store | scraper exists, IDs wired |
| Reddit | NOT DONE — rewrite RSS transport → Apify. Query-targeted, not sub firehose. Benchmark 2 actors on same query, time-box 1hr. |
| YouTube | **BUILT — awaiting sample gate.** Two-stage: `resolve_videos()` (search.list, 100 units, persisted so Stage B never re-pays) then `fetch_comments()` (commentThreads, 1 unit, `part=snippet,replies` for free inline replies). 8 axis-neutral seed queries, 50 videos/query, 200 comments/video ≈ 1,524 units (15.2% of daily). Brand inherited from the VIDEO. Not ingested: no gate decision on file. |
| X/Twitter | NOT DONE — sample-only script, ~200 posts ≈ $1 at $0.005/read. Measure hit-rate, log to sample gate, then decide. Do NOT build full scraper. Do NOT record a drop decision without a measured number. |
| Forums | FOLDED INTO REDDIT. MouthShut/ConsumerComplaints are complaint registries = wrong corpus profile. FORUM_SEED_URLS stays empty. |

---

## Corpus instrument discipline

**Seed queries are axis-neutral. This is load-bearing, not stylistic.**
Querying by uncertainty axis manufactures the relative frequencies the corpus exists to
measure — search "myntra size issue" and sizing will duly appear as a top cause. The YouTube
seed set (8 queries) and Reddit query set (S1/S2/S4) are deliberation CONTEXTS only: haul,
honest-review, wishlist, non-purchase, retrospective. Fit, price, quality, decision-fatigue,
forgetting and anything unanticipated surface at their natural base rates. **If a gate shows
thin yield, expand UNIFORMLY** — more haul/review phrasings, more brands, more pages. Never by
adding an axis query. Axis terms were explicitly deleted from both sets; do not reintroduce them.

**Lexicon axis frequencies are NOT a finding.** `AXIS_TERMS` is hand-authored, so an axis with
more terms — or more generic ones — fires more often regardless of what users said. The flag
aims attention only. Cause frequency comes from cluster sizes over the embedding space, which
carries no hand-authored priors. Two axes (Decision fatigue, Forgetting) were missing entirely
until 2026-08-20.2 and reported 0% by construction; Price double-counted through both
`AXIS_TERMS["Price"]` and `POSTPONE_PHRASES`.

**Denominator caveat (F7).** `EXTERNAL_SOURCES` contains "youtube", "reddit", "instagram", so
external-source rates on a YouTube-sourced corpus are inflated relative to store reviews. Any
"where do users look outside the app" figure must state which corpus its denominator came from.

---

## Gates (all three are machinery, not intentions)

**Lexicon axis-coverage gate.** `pipeline/lexicon_audit.py --static` must pass for all five
required axes (price, fit, quality, decision-fatigue, forgetting) against the CURRENT
`LEXICON_VERSION`, with the result recorded to `data/lexicon_audit.json`. Scrapers call
`assert_axis_coverage()` and refuse to spend quota otherwise. Reason: an axis with no terms
reports 0%, and 0%-because-unmeasurable is indistinguishable from 0%-because-absent once the
number reaches a deck. A stale record (audited against an older lexicon version) counts as no
record.

**Sample gate.** No source gets full ingestion until 50–100 items are pulled and a human
records a wishlist-relevance hit-rate. `run.py` refuses ingest with no recorded decision.
This exists because a prior corpus turned out structurally blind to several of its brief
questions, discovered too late to change instrument.

**Taxonomy fingerprint gate.** Centroids must carry a corpus fingerprint; live_run.py refuses
to boot on mismatch. Centroids from any other corpus were NOT copied. Bypass is
local-dev only: `ALLOW_UNVERIFIED_TAXONOMY=i-know-this-is-wrong`.
Known fixed defect: `persist_taxonomy()` was writing the legacy bare-list schema its own gate
rejects. Writer and reader must stay in sync.

---

## Sale calendar context

Summer EORS 2026 ran ~29 May – 14 June. EORS is twice yearly (summer + December). No live
sale during the 20 Aug – 5 Sep research window. Items saved around EORS have been parked
~10 weeks, so the "waiting for a sale" cohort is maximally visible mid-cycle. This is a
considered research window, not a convenient one — worth a line in the deck.

---

## Repo

Fresh repo, copy-forward only. The prior project's repo is untouched and kept separately
as its own submitted-work record.
Never open this repo in two Antigravity windows simultaneously.

**Day-one .gitignore (already in place):** `data/*`, `!data/taxonomy/`, `extras/`, `interviews/`
Interview material (5–6 participants required by brief) never enters git history.

**Deliberately NOT in this repo:** the prior build's MVP and its supporting modules,
its product catalogues and figma directories, its bespoke analysis harness and docs,
and any centroids trained on a different corpus.

---

## Open / next

- [ ] **DECIDE: embedding + LLM models.** Unresolved on purpose. `config.py` defaults to
      `openai/text-embedding-3-large` + `anthropic/claude-sonnet-5` (paid); `.env.example`
      previously suggested `nvidia/llama-nemotron-embed-vl-1b-v2:free` +
      `nvidia/nemotron-3-ultra-550b-a55b:free`. This is a real cost decision across the whole
      corpus and gets made deliberately BEFORE the embed stage — not by editing whichever file
      is open. Both were left disagreeing rather than silently reconciled.
- [ ] Float survey (screener + survey in one; open text Q5 before checklist Q6)
- [x] Build YouTube scraper (highest yield, cheapest quota) — built, NOT run past the gate
- [ ] Rewrite Reddit → Apify
- [ ] X sample script (~$1), measure, log
- [ ] Sample gate all six sources → human decision per source
- [ ] Metric decomposition (wishlist → purchase)
- [ ] Recruit + run 5–6 interviews ← LONGEST LEAD ITEM, depends on other people's calendars
- [ ] MVP build + deploy (public testable link)
- [ ] 10-slide deck, font size 14 strictly, slide titles state the key message

---

## Standing note on where the last attempt lost

Scored 199.54/300 against a 208.57 cutoff. The gap was entirely **Creativity of Solution**
(52.88 vs 67.83 median). Every other competency was at or near median. The engine, the rigor,
and the pre-registered falsification work were strong and scored where the ceiling is low.
The solution artifact read as generic.

Implication for this project: engine work is Part 1 of 7 and is the part already known to be
done well. Guard the calendar for the solution and the research, not the pipeline.
