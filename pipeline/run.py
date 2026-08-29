"""Pipeline orchestrator CLI.

Written fresh for this brief. The previous build's orchestrator was not ported: a third
of it encoded the old source set, the old store-aware cache-merge rules and a forum
provider that no longer exists, and those assumptions are cheaper to re-derive than to
find.

    python -m pipeline.run ingest    --source play --app Myntra
    python -m pipeline.run ingest    --source all --dry-run
    python -m pipeline.run embed
    python -m pipeline.run cluster
    python -m pipeline.run summarize
    python -m pipeline.run interpret
    python -m pipeline.run publish
    python -m pipeline.run all --dry-run

TWO GATES ARE ENFORCED HERE, NOT ASSUMED:

  1. Sample gate (STEP 8). `ingest` refuses a source with no recorded human decision.
     See pipeline/sources.py.
  2. Source validity (STEP 4). Every scrape routes through config.apps_for(source), so
     Nykaa Fashion cannot reach a community source even if named explicitly.

The cache is authoritative: without --refresh, an app+source already cached for the
date is reused rather than re-scraped.
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import cache, config, corpus, sources
from .ingest import normalize

log = logging.getLogger("run")


# ---- ingest ------------------------------------------------------------------------

# Sources whose unit of work is a QUERY, not an app.
#
# A store scrape is per-app by nature: one package id, one review feed. A community
# scrape is not. One YouTube search for "myntra haul" returns a video whose comments
# may discuss Myntra, AJIO or both, and the brand is a PROPERTY OF THE TEXT rather
# than an input to the pull.
#
# Running these through the per-app loop would be wrong twice over: the full seed
# query set would execute once per app (2x quota — 2,248 units instead of 1,124 on
# YouTube), and each execution emits records for every brand it found, so both app
# partitions would receive both brands' records. Every cross-brand record would be
# double-counted and the corpus totals would silently inflate.
CROSS_APP_SOURCES = frozenset({"reddit", "youtube", "twitter", "forum"})


def _scrape(source: str, spec) -> list[dict]:
    """Dispatch one (source, app) scrape. Per-app sources only."""
    if source == "play":
        from .ingest.scrapers import play_store
        return play_store.scrape(spec, target=config.SCRAPE_TARGET_PER_APP)
    if source == "appstore":
        from .ingest.scrapers import app_store
        return app_store.scrape(spec, max_pages=config.APPSTORE_RSS_MAX_PAGES)
    raise NotImplementedError(
        f"source {source!r} has no scraper for this brief yet — {sources.SOURCES[source].note}"
    )


def _scrape_cross_app(source: str) -> list[dict]:
    """Dispatch ONE scrape covering every in-scope app. Records carry their own app."""
    if source == "youtube":
        from .ingest.scrapers import youtube
        return youtube.scrape()
    if source == "reddit":
        from .ingest.scrapers import reddit
        return reddit.scrape()
    raise NotImplementedError(
        f"source {source!r} has no scraper for this brief yet — {sources.SOURCES[source].note}"
    )


def _persist(source: str, app_key: str, raw: list[dict], date: str) -> None:
    """Merge one source's records into an app partition and re-normalize it."""
    existing = cache.load_raw_safe(app_key, date) or []
    merged = [r for r in existing if r.get("store") != source] + raw
    cache.save_raw(app_key, date, merged)

    reviews, stats = normalize.normalize_corpus(app_key, merged)
    cache.save_normalized(app_key, date, [r.to_dict() for r in reviews])
    cache.save_manifest(app_key, date, {
        "app": app_key, "date": date,
        "raw_scraped": len(merged), "usable": len(reviews),
        "retention_pct": round(100 * len(reviews) / len(merged), 1) if merged else 0.0,
        "raw_by_store": stats.get("raw_by_store", {}),
        "by_store_usable": stats.get("by_store_usable", {}),
    })
    log.info("[%s:%s] %d raw -> %d usable", source, app_key, len(merged), len(reviews))


def cmd_ingest(source_keys: list[str], app_keys: list[str] | None,
               refresh: bool, dry_run: bool, date: str | None = None) -> int:
    date = date or config.today_str()
    planned, blocked = [], []

    for source in source_keys:
        spec_list = config.apps_for(source)          # STEP 4 gate
        if app_keys:
            spec_list = [s for s in spec_list if s.key in app_keys]
        if not spec_list:
            log.warning("[%s] no in-scope apps for this source — skipping", source)
            continue

        meta = sources.SOURCES[source]
        if not meta.implemented:
            blocked.append((source, f"no scraper built for this brief — {meta.note}"))
            continue
        try:
            sources.assert_approved(source)          # STEP 8 gate
        except sources.SampleGateError as e:
            blocked.append((source, str(e)))
            continue
        for spec in spec_list:
            planned.append((source, spec))

    print(f"\nINGEST PLAN  ({date})")
    for source, spec in planned:
        cached = cache.has_raw(spec.key, date) and source in cache.raw_stores(spec.key, date)
        action = "reuse cache" if (cached and not refresh) else "scrape"
        print(f"  {source:<10} {spec.key:<15} -> {action}")
    for source, why in blocked:
        print(f"  {source:<10} {'—':<15} -> BLOCKED")
        for line in why.strip().splitlines():
            print(f"      {line}")
    if not planned:
        print("\n  Nothing to ingest. Every requested source is blocked or out of scope.")
        return 1 if blocked else 0
    if dry_run:
        print("\n  --dry-run: no work done.")
        return 0

    # Group by source: a cross-app source must scrape ONCE for all its apps.
    by_source: dict[str, list] = {}
    for source, spec in planned:
        by_source.setdefault(source, []).append(spec)

    for source, spec_list in by_source.items():
        if source in CROSS_APP_SOURCES:
            stale = [s for s in spec_list
                     if refresh or source not in cache.raw_stores(s.key, date)]
            if not stale:
                log.info("[%s] cache hit for every in-scope app — skipping scrape", source)
                continue

            records = _scrape_cross_app(source)          # one pull, every brand
            by_app: dict[str, list[dict]] = {s.key: [] for s in spec_list}
            out_of_scope = 0
            for rec in records:
                if rec.get("app") in by_app:
                    by_app[rec["app"]].append(rec)
                else:
                    out_of_scope += 1
            if out_of_scope:
                log.warning("[%s] discarded %d records for apps not in scope for this "
                            "source (see config.apps_for)", source, out_of_scope)
            for spec in spec_list:
                _persist(source, spec.key, by_app[spec.key], date)
            continue

        for spec in spec_list:
            if source in cache.raw_stores(spec.key, date) and not refresh:
                log.info("[%s:%s] cache hit — skipping scrape", source, spec.key)
                continue
            _persist(source, spec.key, _scrape(source, spec), date)
    return 0


# ---- embed / cluster ---------------------------------------------------------------

def cmd_embed(date: str | None = None) -> int:
    import numpy as np

    from .embed import cache as embed_cache

    date = date or corpus.latest_date()
    rows = corpus.load_corpus(date)
    if not rows:
        print("no corpus — run ingest first"); return 1
    print(f"embedding {len(rows)} records ({config.EMBEDDING_MODEL})")
    vecs = embed_cache.get_embeddings([r["text"] for r in rows])
    print(f"  -> {np.asarray(vecs).shape}")
    return 0


def cmd_cluster(date: str | None = None) -> int:
    import json

    import numpy as np

    from .cluster import rank as rank_mod
    from .cluster import umap_hdbscan
    from .embed import cache as embed_cache

    date = date or corpus.latest_date()
    rows = corpus.load_corpus(date)
    if len(rows) < config.ML_FLOOR:
        print(f"corpus below ML_FLOOR ({config.ML_FLOOR}) — refusing to cluster"); return 1

    weights = corpus.weight_summary(rows)
    print(f"corpus: {weights['total']} records — "
          f"PRIMARY {weights['primary_n']} ({weights['primary_pct']}%), "
          f"SECONDARY {weights['secondary_n']} ({weights['secondary_pct']}%)")
    if weights["primary_n"] < config.ML_FLOOR:
        print(f"  ⚠️  PRIMARY corpus below ML_FLOOR — the spine is too thin to cluster on.")

    X = np.asarray(embed_cache.get_embeddings([r["text"] for r in rows]), dtype=np.float32)
    labels, reduced, _reducer, clusterer = umap_hdbscan.cluster(X)
    noise = umap_hdbscan.noise_fraction(labels)
    print(f"  clusters={len(set(labels.tolist()) - {-1})}  noise={100*noise:.1f}%")

    for row, lab in zip(rows, labels.tolist()):
        row["cluster_id"] = int(lab)

    # STEP 7: the taxonomy is written WITH its corpus fingerprint. `records` is required.
    umap_hdbscan.persist_taxonomy(X, reduced, labels, clusterer=clusterer, records=rows)
    print(f"  taxonomy persisted with corpus fingerprint -> {config.TAXONOMY_DIR}")

    ranked = rank_mod.rank_clusters(rows)
    total_clustered = sum(c["size"] for c in ranked)
    giant = rank_mod.giant_cluster_id(ranked, total_clustered)
    if giant is not None:
        log.warning("cluster %d holds >%.0f%% of clustered volume — candidate for re-split",
                    giant, 100 * config.GIANT_CLUSTER_THRESHOLD)

    # Persist. Without this the clustering is in-memory only and `summarize` has
    # nothing to read — the phase would silently have to redo the whole thing.
    out = config.ANALYSIS_DIR / date
    out.mkdir(parents=True, exist_ok=True)
    noise_n = int((np.asarray(labels) == -1).sum())
    summary = {
        "date": date,
        "embedding_model": config.EMBEDDING_MODEL,
        "umap_params": config.UMAP_PARAMS,
        "hdbscan_params": config.HDBSCAN_PARAMS,
        "n_reviews": len(rows),
        "n_clusters": len(ranked),
        "noise_count": noise_n,
        "noise_pct": round(100 * noise_n / len(rows), 1) if rows else 0.0,
        "giant_cluster_id": giant,
        "corpus_weighting": weights,
        "clusters": ranked,
    }
    (out / "clusters.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "clustered.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== Clustering summary ({date}) ===")
    print(f"  records={len(rows)}  clusters={len(ranked)}  noise={summary['noise_pct']}%")
    print("  top clusters by score (size x relevance-share, rating-agnostic):")
    for c in ranked[:10]:
        print(f"    #{c['cluster_id']:<3} size={c['size']:>4}  rel_share={c['relevance_share']:.2f}  "
              f"score={c['score']:>7.1f}  per_app={c['per_app']}")
    print(f"  analysis -> {out}  |  taxonomy -> {config.TAXONOMY_DIR}")
    return 0


# ---- summarize -----------------------------------------------------------------

def _cluster_meta(cid, member_idx, rows) -> dict:
    per_app = {a: 0 for a in config.APPS}
    per_source: dict[str, int] = {}
    ratings, flagged = [], 0
    for i in member_idx:
        r = rows[i]
        if r["app"] in per_app:
            per_app[r["app"]] += 1
        per_source[r.get("store", "?")] = per_source.get(r.get("store", "?"), 0) + 1
        if r.get("rating") is not None:
            ratings.append(r["rating"])
        if r.get("relevance_flagged"):
            flagged += 1
    n = len(member_idx)
    return {"cluster_id": int(cid), "size": n, "per_app": per_app, "per_source": per_source,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "relevance_share": round(flagged / n, 3) if n else 0.0}


def _name_one(meta, member_idx, X, texts, budget=None):
    """Name+summarize one cluster, validate quotes, re-prompt once if all rejected."""
    from .summarize import llm, prompts, select, validate_quotes

    samples = select.pick_samples(member_idx, X, texts)
    cluster_texts = [texts[i] for i in member_idx]
    msgs = prompts.build_messages(samples, meta["size"], meta["avg_rating"],
                                  meta["per_app"], meta.get("per_source"))

    theme = validate_quotes.validate_theme(llm.name_cluster(msgs, budget=budget), cluster_texts)
    if theme["n_quotes_validated"] == 0 and theme["n_quotes_rejected"] > 0:   # re-prompt once
        retry = validate_quotes.validate_theme(llm.name_cluster(msgs, budget=budget), cluster_texts)
        theme = retry if retry["n_quotes_validated"] > 0 else {**theme, "_omitted": True}
    return theme


def _to_record(meta, theme, extra=None):
    rec = {**meta,
           "theme_name": theme.get("theme_name", ""), "summary": theme.get("summary", ""),
           "quotes": theme.get("quotes", []),
           "per_app_observation": theme.get("per_app_observation", ""),
           "n_quotes_validated": theme.get("n_quotes_validated", 0),
           "n_quotes_rejected": theme.get("n_quotes_rejected", 0),
           # Carry rejected-quote TEXT, not just the count, so the artifact can itemize
           # real rejects as evidence the validator actually fires.
           "quotes_rejected": theme.get("quotes_rejected", []),
           "model_used": theme.get("_model_used", ""),
           "omitted": theme.get("_omitted", False)}
    if extra:
        rec.update(extra)
    return rec


def _name_set(label, cluster_metas, members, X, texts, budget=None):
    import time

    from .summarize import llm

    if budget is None:
        budget = llm.TokenBudget()
    themes, val, rej, omitted = [], 0, 0, 0
    for n, (meta, extra) in enumerate(cluster_metas, 1):
        theme = _name_one(meta, members[meta["cluster_id"]], X, texts, budget=budget)
        rec = _to_record(meta, theme, extra)
        val += rec["n_quotes_validated"]; rej += rec["n_quotes_rejected"]
        omitted += int(rec["omitted"])
        themes.append(rec)
        print(f"  [{label} {n}/{len(cluster_metas)}] #{meta['cluster_id']} "
              f"'{rec['theme_name']}' ({rec['n_quotes_validated']}✓/{rec['n_quotes_rejected']}✗)"
              + (" OMITTED" if rec["omitted"] else ""))
        time.sleep(config.LLM_MIN_SPACING_SEC)
    return themes, {"quotes_validated": val, "quotes_rejected": rej, "themes_omitted": omitted}


def cmd_summarize(date: str | None = None) -> int:
    """Name+summarize two tracks: (A) full-corpus union-selection, (B) flagged subset
    re-clustered finer. Validates every quote. Stops BEFORE interpretive mapping."""
    import json

    import numpy as np
    from hdbscan import HDBSCAN
    from umap import UMAP

    from .cluster import rank as rank_mod
    from .embed import cache as embed_cache
    from .summarize import llm, select

    date = date or corpus.latest_date()
    out_dir = config.ANALYSIS_DIR / date
    clustered_path = out_dir / "clustered.json"
    if not clustered_path.exists():
        print("  no clustered.json — run `cluster` first."); return 1

    rows = json.loads(clustered_path.read_text(encoding="utf-8"))
    texts = [r["text"] for r in rows]
    X = np.asarray(embed_cache.get_embeddings(texts), dtype=np.float32)

    members: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        members.setdefault(r["cluster_id"], []).append(i)

    out_dir.mkdir(parents=True, exist_ok=True)
    budget = llm.TokenBudget()

    # ---- Track A: full-corpus union selection ----
    ranked = rank_mod.rank_clusters(rows)
    selected = select.union_select(ranked)
    print(f"Track A: naming {len(selected)} union-selected clusters")
    metasA = []
    for c in selected:
        meta = _cluster_meta(c["cluster_id"], members[c["cluster_id"]], rows)
        meta["score"] = c.get("score")
        metasA.append((meta, {"selection_path": c["selection_path"]}))
    themesA, statsA = _name_set("A", metasA, members, X, texts, budget=budget)
    (out_dir / "themes_full.json").write_text(json.dumps(
        {"track": "full-corpus union-selection",
         "mcs": config.HDBSCAN_PARAMS["min_cluster_size"],
         "stats": statsA, "themes": themesA}, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- Track B: flagged-subset re-clustering (finer mcs; every record relevant) ----
    flagged_idx = [i for i, r in enumerate(rows) if r.get("relevance_flagged")]
    print(f"Track B: re-clustering {len(flagged_idx)} flagged records (mcs=5)")
    themesB, statsB = [], {"quotes_validated": 0, "quotes_rejected": 0, "themes_omitted": 0}
    fb_noise, sub_members = 0.0, {}
    if len(flagged_idx) >= config.ML_FLOOR:
        Xf = X[flagged_idx]
        reduced_f = UMAP(**config.UMAP_PARAMS).fit_transform(Xf)
        labels_f = HDBSCAN(min_cluster_size=5, min_samples=3).fit_predict(reduced_f)
        for pos, lab in enumerate(labels_f):
            if lab != -1:
                sub_members.setdefault(int(lab), []).append(flagged_idx[pos])
        top_sub = sorted(sub_members, key=lambda c: len(sub_members[c]), reverse=True)[:12]
        fb_noise = 100 * float((labels_f == -1).mean())
        metasB = [(_cluster_meta(cid, sub_members[cid], rows), {"selection_path": "flagged-subset"})
                  for cid in top_sub]
        membersB = {m[0]["cluster_id"]: sub_members[m[0]["cluster_id"]] for m in metasB}
        themesB, statsB = _name_set("B", metasB, membersB, X, texts, budget=budget)
    else:
        print(f"  skipped — only {len(flagged_idx)} flagged records (< ML_FLOOR)")

    (out_dir / "themes_flagged.json").write_text(json.dumps(
        {"track": "flagged-subset (mcs=5)", "flagged_reviews": len(flagged_idx),
         "subclusters_found": len(sub_members), "noise_pct": round(fb_noise, 1),
         "stats": statsB, "themes": themesB}, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== naming complete ===")
    print(f"  token budget used (est.): {budget.used}/{budget.max_tokens}")
    print(f"  Track A: {len(themesA)} themes | quotes {statsA['quotes_validated']}✓/"
          f"{statsA['quotes_rejected']}✗ | omitted {statsA['themes_omitted']}")
    print(f"  Track B: {len(themesB)} themes | quotes {statsB['quotes_validated']}✓/"
          f"{statsB['quotes_rejected']}✗ | omitted {statsB['themes_omitted']}")
    print(f"  -> {out_dir}/themes_full.json , themes_flagged.json")
    return 0


def _load_theme_tracks(date: str):
    import json
    out_dir = config.ANALYSIS_DIR / date
    full_doc = json.loads((out_dir / "themes_full.json").read_text(encoding="utf-8"))
    flagged_doc = json.loads((out_dir / "themes_flagged.json").read_text(encoding="utf-8"))
    return (full_doc["themes"], flagged_doc["themes"],
            full_doc.get("stats", {}), flagged_doc.get("stats", {}))


def cmd_spotcheck_init(date: str | None = None) -> int:
    """Write a stratified spot-check template for the researcher to judge."""
    import json

    from .interpret import funnel_map, spotcheck

    date = date or corpus.latest_date()
    clustered_path = config.ANALYSIS_DIR / date / "clustered.json"
    if not clustered_path.exists():
        print("  no clustered.json — run `cluster` first."); return 1

    full_themes, _, _, _ = _load_theme_tracks(date)
    rows = json.loads(clustered_path.read_text(encoding="utf-8"))
    try:
        mapping = funnel_map.load_mapping()
        funnel_map.apply_mapping(full_themes, mapping, "full")
    except FileNotFoundError:
        pass          # sampling does not require the mapping

    samples = spotcheck.sample_reviews(rows, full_themes)
    path = spotcheck.write_template(samples)
    print(f"  spot-check template: {len(samples)} samples -> {path}")
    print("  Fill agrees_with_theme (true/false) + notes, then run `interpret`.")
    return 0


# ---- interpret -------------------------------------------------------------------

def _external_refs_by_axis(rows: list[dict]) -> dict[str, int]:
    """Records that name an OUTSIDE source while touching an axis.

    Feeds recommend()'s R5 externalisation multiplier: uncertainty a user leaves the
    platform to resolve is the strongest evidence the product surface has a hole.
    """
    from .ingest import lexicon

    counts: dict[str, int] = {}
    for r in rows:
        d = lexicon.flag_detailed(r.get("text", ""))
        if not d["external"]:
            continue
        for axis in d["axes"]:
            counts[axis] = counts.get(axis, 0) + 1
    return counts


def cmd_interpret(date: str | None = None) -> int:
    """Apply the human funnel mapping, then build the recommendation + validation cards."""
    import json
    from collections import Counter

    from .interpret import (forum_corroboration, funnel_map, positive_template,
                            recommend, spotcheck)

    date = date or corpus.latest_date()
    out_dir = config.ANALYSIS_DIR / date
    clustered_path = out_dir / "clustered.json"
    if not clustered_path.exists():
        print("  no clustered.json — run `cluster` + `summarize` first."); return 1
    for needed in ("themes_full.json", "themes_flagged.json"):
        if not (out_dir / needed).exists():
            print(f"  missing {needed} — run `summarize` first."); return 1

    full_themes, flagged_themes, stats_a, stats_b = _load_theme_tracks(date)
    try:
        mapping = funnel_map.load_mapping()
    except FileNotFoundError as e:
        print(f"  ABORT: {e}")
        print("  Run `scaffold-mapping` to emit a fill-in file keyed by the real themes.")
        return 1
    full_themes, unmapped_a = funnel_map.apply_mapping(full_themes, mapping, "full")
    flagged_themes, unmapped_b = funnel_map.apply_mapping(flagged_themes, mapping, "flagged")
    unmapped = unmapped_a + unmapped_b
    if unmapped:
        print(f"  ABORT: {len(unmapped)} theme(s) lack a funnel mapping: {unmapped[:5]}")
        return 1

    rows = json.loads(clustered_path.read_text(encoding="utf-8"))
    clusters_path = out_dir / "clusters.json"
    clusters_doc = json.loads(clusters_path.read_text(encoding="utf-8")) if clusters_path.exists() else {}

    all_themes = [dict(t, track="full") for t in full_themes if not t.get("omitted")]
    all_themes += [dict(t, track="flagged") for t in flagged_themes if not t.get("omitted")]

    try:
        spot = spotcheck.load_spotcheck()
    except FileNotFoundError:
        log.warning("spotcheck.json not found — proceeding without spot-check agreement. "
                    "Run `spotcheck-init`, fill judgments, then re-run `interpret`.")
        spot = {"samples": []}
    validation = spotcheck.compute_agreement(spot)
    validation["quotes_validated"] = stats_a.get("quotes_validated", 0) + stats_b.get("quotes_validated", 0)
    validation["quotes_rejected"] = stats_a.get("quotes_rejected", 0) + stats_b.get("quotes_rejected", 0)

    # Deliberate negative test: a fabricated quote MUST be rejected by the same
    # substring validator every displayed quote passes. This proves the kill-switch
    # fires, rather than leaning on the incidental natural reject rate.
    from .summarize import validate_quotes as _vq
    _fabricated = ("I wishlisted a kurta and the app teleported it into my wardrobe "
                   "before I finished tapping checkout.")
    validation["negative_test"] = {
        "fabricated_quote": _fabricated,
        "rejected": not _vq.is_valid(_fabricated, [r["text"] for r in rows]),
    }

    # Resolution template drives the recommendation (R3), so compute it first.
    resolution_template = positive_template.extract(rows)
    recommendation = recommend.recommend(
        all_themes,
        resolution_template=resolution_template,
        corpus_usable=clusters_doc.get("n_reviews"),
        external_refs=_external_refs_by_axis(rows),
    )
    corroboration = forum_corroboration.build(rows, all_themes)

    payload = {
        "date": date,
        "run_id": date,
        "themes_full": full_themes,
        "themes_flagged": flagged_themes,
        "themes_all": all_themes,
        "naming_stats": {"track_a": stats_a, "track_b": stats_b},
        "recommendation": recommendation,
        "resolution_template": resolution_template,
        "corroboration": corroboration,
        "corpus_weighting": corpus.weight_summary(rows),
        "validation": validation,
        "spotcheck": spot,
    }
    out_path = out_dir / "interpreted.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    gates = Counter(t.get("funnel_gate", "?") for t in all_themes)
    print("\n=== interpretive layer complete ===")
    print(f"  themes mapped: {len(all_themes)}  gates={dict(gates)}")
    print(f"  spot-check agreement: {validation.get('spotcheck_agreement_pct')}% "
          f"({validation.get('agreements')}/{validation.get('judged')} judged)")
    print(f"  quotes: {validation['quotes_validated']} validated / "
          f"{validation['quotes_rejected']} rejected")
    print(f"  negative test (fabricated quote rejected): {validation['negative_test']['rejected']}")
    print(f"  recommendation: {recommendation.get('axis') or '(none)'} "
          f"(confidence={recommendation.get('confidence')}, gate={recommendation.get('funnel_gate')})")
    print(f"  largest unresolved gaps: {resolution_template.get('largest_gaps', [])[:3]}")
    print(f"  -> {out_path}")
    return 0


def cmd_scaffold_mapping(date: str | None = None) -> int:
    """Emit a funnel_mapping.json scaffold keyed by the REAL theme ids.

    Code never decides a gate — that mapping is the human interpretive step and the
    whole audit trail depends on it staying human-owned. This only removes the
    transcription work: it writes every theme key with its name, size and quotes, and
    leaves funnel_gate/mapping_rationale blank for a person to fill.
    """
    import json

    date = date or corpus.latest_date()
    out_dir = config.ANALYSIS_DIR / date
    for needed in ("themes_full.json", "themes_flagged.json"):
        if not (out_dir / needed).exists():
            print(f"  missing {needed} — run `summarize` first."); return 1
    full_themes, flagged_themes, _, _ = _load_theme_tracks(date)

    from .models import FUNNEL_GATES
    mappings: dict[str, dict] = {}
    for track, themes in (("full", full_themes), ("flagged", flagged_themes)):
        for t in themes:
            if t.get("omitted"):
                continue
            mappings[f"{track}:{t['cluster_id']}"] = {
                "_theme_name": t.get("theme_name", ""),
                "_summary": t.get("summary", ""),
                "_size": t.get("size", 0),
                "_quotes": [q.get("quote_text", q) if isinstance(q, dict) else q
                            for q in (t.get("quotes") or [])][:2],
                "funnel_gate": "",
                "mapping_rationale": "",
                "what_this_means": "",
            }
    path = config.INTERPRET_DIR / "funnel_mapping.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"_instructions": f"Fill funnel_gate (one of {list(FUNNEL_GATES)}) and a one-line "
                          f"mapping_rationale for every entry. Fields prefixed _ are context "
                          f"only and are ignored by the loader. Map a theme to the gate whose "
                          f"FAILURE it describes.",
         "mappings": mappings}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  scaffold written: {len(mappings)} themes -> {path}")
    print("  Fill funnel_gate + mapping_rationale for each, then run `interpret`.")
    return 0


# ---- publish ---------------------------------------------------------------------

def cmd_publish(date: str | None = None) -> int:
    """Write analysis.json — the static artifact the deployed engine serves."""
    from .publish import artifact

    date = date or corpus.latest_date()
    if not date:
        print("  no data found — run the pipeline first."); return 1
    try:
        out_path = artifact.write_artifact(date)
    except FileNotFoundError as e:
        print(f"  {e}"); return 1
    print(f"  artifact -> {out_path}")
    return 0


def cmd_all(source_keys, app_keys, refresh, dry_run) -> int:
    rc = cmd_ingest(source_keys, app_keys, refresh, dry_run)
    if rc or dry_run:
        return rc
    for fn in (cmd_embed, cmd_cluster, cmd_summarize, cmd_interpret, cmd_publish):
        rc = fn()
        if rc:
            return rc
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["ingest", "embed", "cluster", "summarize",
                                      "spotcheck-init", "scaffold-mapping",
                                      "interpret", "publish", "all", "status"])
    ap.add_argument("--source", default="all",
                    help=f"one of {sorted(sources.SOURCES)} or 'all'")
    ap.add_argument("--app", default=None, help="limit to one app key")
    ap.add_argument("--refresh", action="store_true", help="ignore cache, re-scrape")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(message)s")

    if args.phase == "status":
        print("\nSOURCES")
        for k, s in sources.SOURCES.items():
            d = sources.decision(k)
            gate = ("approved" if d and d["approved"] else "dropped" if d else "not sampled")
            print(f"  {k:<10} {'built' if s.implemented else 'NOT BUILT':<10} "
                  f"{s.weight:<10} gate={gate}")
            if not s.implemented:
                print(f"      {s.note}")
        print(f"\nAPPS  (unverified ids: {config.verify_app_ids() or 'none'})")
        for k, sp in config.APPS.items():
            print(f"  {k:<15} {sp.role:<11} sources={sorted(sp.sources)}")
        return 0

    source_keys = sorted(sources.SOURCES) if args.source == "all" else [args.source]
    for s in source_keys:
        if s not in sources.SOURCES:
            ap.error(f"unknown source {s!r}; choose from {sorted(sources.SOURCES)} or 'all'")
    app_keys = [args.app] if args.app else None

    if args.phase == "ingest":
        return cmd_ingest(source_keys, app_keys, args.refresh, args.dry_run)
    if args.phase == "embed":
        return cmd_embed()
    if args.phase == "cluster":
        return cmd_cluster()
    if args.phase == "summarize":
        return cmd_summarize()
    if args.phase == "spotcheck-init":
        return cmd_spotcheck_init()
    if args.phase == "scaffold-mapping":
        return cmd_scaffold_mapping()
    if args.phase == "interpret":
        return cmd_interpret()
    if args.phase == "publish":
        return cmd_publish()
    return cmd_all(source_keys, app_keys, args.refresh, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
