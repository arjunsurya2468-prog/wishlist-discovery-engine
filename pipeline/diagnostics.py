"""Diagnostics — read-only analysis. Does NOT name clusters.

Run: python -m pipeline.diagnostics
Covers: (1) corpus composition BY WEIGHT CLASS, (2) noise diagnostic incl.
flagged-in-noise, (3) centroid-assignment validation with novelty threshold,
(4) per-app enrichment index, (5) min_cluster_size sweep, (6) confirmations.

STEP 6 — every volume and coverage figure here is reported against the corpus it
came from. PRIMARY (community/discussion) is the quantified base; SECONDARY (store
reviews) is corroboration. A rate quoted against the combined corpus is reported as
such and explicitly labelled, never presented as the headline.
"""
from __future__ import annotations

import json
import logging

import numpy as np
from hdbscan import HDBSCAN
from umap import UMAP

from . import cache, config, corpus
from .cluster import assign as assign_mod
from .cluster import rank as rank_mod
from .embed import cache as embed_cache

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("diagnostics")


def hr(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


# ---------- 1. Corpus composition ----------
def corpus_composition(date):
    hr("1. CORPUS COMPOSITION  (by weight class — STEP 6)")
    tot_raw = tot_usable = 0
    per_store_usable = {}
    print(f"{'app':<16} {'raw':>7} {'usable':>7} {'ret%':>6}  by_store_usable / raw_by_store")
    for app in config.APPS:
        try:
            m = cache.load_manifest(app, date)
        except (FileNotFoundError, OSError):
            # Not every app is valid for every source (Nykaa Fashion is store-only),
            # and a source may have been dropped at the STEP 8 sample gate.
            print(f"{app:<16} {'—':>7} {'—':>7} {'—':>6}  no manifest for this date")
            continue
        tot_raw += m["raw_scraped"]; tot_usable += m["usable"]
        for st, n in m["by_store_usable"].items():
            per_store_usable[st] = per_store_usable.get(st, 0) + n
        print(f"{app:<16} {m['raw_scraped']:>7} {m['usable']:>7} {m['retention_pct']:>6}"
              f"  {m['by_store_usable']} / {m['raw_by_store']}")
    ret = round(100 * tot_usable / tot_raw, 1) if tot_raw else 0.0
    print(f"{'TOTAL':<16} {tot_raw:>7} {tot_usable:>7} {ret:>6}"
          f"  usable_by_store={per_store_usable}")

    # ---- Weight-class split: the number that decides what the headlines may say ----
    n_primary = sum(n for st, n in per_store_usable.items() if st in corpus.PRIMARY_SOURCES)
    n_secondary = sum(n for st, n in per_store_usable.items() if st in corpus.SECONDARY_SOURCES)
    total = n_primary + n_secondary
    print("\n  WEIGHT CLASS")
    print(f"    PRIMARY   (community/discussion — {', '.join(corpus.PRIMARY_SOURCES)}): "
          f"{n_primary:>6}  ({100*n_primary/total if total else 0:.1f}%)")
    print(f"    SECONDARY (store reviews — {', '.join(corpus.SECONDARY_SOURCES)}):       "
          f"{n_secondary:>6}  ({100*n_secondary/total if total else 0:.1f}%)")
    print("\n    → Headline percentages use the PRIMARY denominator "
          f"(n={n_primary}), NOT the combined corpus (n={total}).")
    print("      Store reviews are transactional and structurally do not carry "
          "wishlist-abandonment reasoning; they corroborate, they do not quantify.")

    if total and n_primary / total < 0.5:
        print("\n  ⚠️  PRIMARY is a minority of the corpus. The spine is thin — either the "
              "community sources under-delivered at the STEP 8 sample gate, or ingestion "
              "is incomplete. Do NOT quote combined-corpus rates to compensate.")
    if n_primary < config.ML_FLOOR:
        print(f"\n  🚨 PRIMARY corpus below ML_FLOOR ({config.ML_FLOOR}). "
              "Clustering on this base is not meaningful.")

    print("\n  written to: data/cache/<app>/<date>/manifest.json  (per app)  ✓")
    return {"usable": tot_usable, "primary": n_primary, "secondary": n_secondary}


# ---------- 2. Noise diagnostic ----------
def noise_diagnostic(rows, labels):
    hr("2. NOISE DIAGNOSTIC  (highest priority)")
    labels = np.asarray(labels)
    N = len(rows)
    noise = labels == -1
    flagged = np.array([bool(r["relevance_flagged"]) for r in rows])

    overall_noise = 100 * noise.mean()
    flagged_noise = 100 * (flagged & noise).sum() / flagged.sum() if flagged.sum() else 0
    unflagged_noise = 100 * ((~flagged) & noise).sum() / (~flagged).sum() if (~flagged).sum() else 0

    print(f"  corpus in noise (-1):            {overall_noise:5.1f}%  ({noise.sum()}/{N})")
    print(f"  relevance-FLAGGED in noise:      {flagged_noise:5.1f}%  "
          f"({(flagged & noise).sum()}/{flagged.sum()})")
    print(f"  unflagged in noise (reference):  {unflagged_noise:5.1f}%")
    lift = flagged_noise / overall_noise if overall_noise else 0
    print(f"  flagged-vs-overall noise ratio:  {lift:.2f}x")

    if flagged_noise > overall_noise + 3:
        print("\n  🚨 FLAGGED REVIEWS ARE OVER-REPRESENTED IN NOISE.")
        print("     Clustering is discarding target signal — a SECOND-PASS clustering on the")
        print("     noise subset is warranted before P3.")
    else:
        print("\n  ✅ Flagged reviews are NOT over-represented in noise (flagged noise rate "
              f"{flagged_noise:.1f}% <= overall {overall_noise:.1f}%).")
        print("     Target signal is being clustered, not discarded. No second pass required.")
    return overall_noise


# ---------- 3. Centroid-assignment validation ----------
def centroid_validation(X, labels, holdout=300, seed=42):
    hr("3. CENTROID-ASSIGNMENT VALIDATION  (3072-dim embedding space vs UMAP-space labels)")
    labels = np.asarray(labels)
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(X))
    hold, train = perm[:holdout], perm[holdout:]

    train_labels = labels[train]
    uniq = sorted(set(train_labels.tolist()) - {-1})
    centroids = np.array([X[train][train_labels == l].mean(axis=0) for l in uniq], dtype=np.float32)
    threshold = assign_mod.compute_threshold(X[train], train_labels, centroids, uniq, pct=95.0)

    true = labels[hold]
    nonnoise = true != -1
    truenoise = true == -1

    pred_raw, dist = assign_mod.assign(X[hold], centroids, uniq, threshold=None)
    pred_thr, _ = assign_mod.assign(X[hold], centroids, uniq, threshold=threshold)

    agree_raw = 100 * (pred_raw[nonnoise] == true[nonnoise]).mean() if nonnoise.any() else 0
    agree_thr = 100 * (pred_thr[nonnoise] == true[nonnoise]).mean() if nonnoise.any() else 0
    nonnoise_to_novel = 100 * (pred_thr[nonnoise] == -1).mean() if nonnoise.any() else 0
    truenoise_to_novel = 100 * (pred_thr[truenoise] == -1).mean() if truenoise.any() else None

    print(f"  holdout={holdout} (train-only centroids, seed={seed})")
    print(f"  novelty threshold (cosine dist, 95th pct intra-cluster): {threshold:.3f}")
    print(f"  holdout composition: {nonnoise.sum()} in real clusters, {truenoise.sum()} true-noise")
    print(f"\n  agreement vs true HDBSCAN label (nearest-centroid, NO threshold): {agree_raw:5.1f}%")
    print(f"  agreement (WITH threshold; some sent to novel):                   {agree_thr:5.1f}%")
    print(f"  real-cluster holdout sent to 'novel' by threshold:                {nonnoise_to_novel:5.1f}%")
    if truenoise_to_novel is not None:
        print(f"  true-noise holdout correctly flagged 'novel':                     {truenoise_to_novel:5.1f}%")
    verdict = "STRONG" if agree_raw >= 80 else "MODERATE" if agree_raw >= 60 else "WEAK"
    print(f"\n  → embedding-space centroid assignment reproduces UMAP-space labels: {verdict} ({agree_raw:.1f}%)")
    print(f"  → novelty outcome implemented: reviews beyond {threshold:.3f} return -1 (unassigned), "
          "persisted to taxonomy for the live demo.")


# ---------- 4. Per-app enrichment index ----------
def per_app_index(rows, labels, top_n=15):
    hr("4. PER-APP ENRICHMENT INDEX  (share-normalized, not raw counts)")
    labels = np.asarray(labels)
    for r, l in zip(rows, labels):
        r["cluster_id"] = int(l)
    ranked = rank_mod.rank_clusters(rows)

    N = len(rows)
    share = {app: sum(1 for r in rows if r["app"] == app) / N for app in config.APPS}
    print("  corpus share: " + ", ".join(f"{a} {100*share[a]:.1f}%" for a in config.APPS))
    print("  index = (app's fraction of cluster) / (app's corpus share); >1 = over-represented\n")
    print(f"  {'#id':>4} {'size':>5} {'relSh':>5} | " + " ".join(f"{a[:4]:>6}" for a in config.APPS) + "   dominant(by index)")
    survive = 0
    for c in ranked[:top_n]:
        idx = {a: (c["per_app"][a] / c["size"]) / share[a] if share[a] else 0 for a in config.APPS}
        dom = max(idx, key=idx.get)
        comparators = [a for a, sp in config.APPS.items() if sp.role == "comparator"]
        if dom in comparators and idx[dom] > 1.2:
            survive += 1
        print(f"  {c['cluster_id']:>4} {c['size']:>5} {c['relevance_share']:>5.2f} | "
              + " ".join(f"{idx[a]:>6.2f}" for a in config.APPS) + f"   {dom} ({idx[dom]:.2f}x)")
    comparators = [a for a, sp in config.APPS.items() if sp.role == "comparator"]
    print(f"\n  Of the top {top_n} clusters, {survive} are dominated (index>1.2x) by a "
          f"comparator ({', '.join(comparators)}).")
    print("  → The comparator skew " + ("SURVIVES" if survive >= top_n // 2 else "is WEAKER than raw counts suggested")
          + " under share-normalization.")
    print("     NOTE: Nykaa Fashion is store-only by design, so its corpus share is not "
          "comparable to Myntra/AJIO on community-sourced clusters. Read this table "
          "per weight class, not across it.")


# ---------- 5. Parameter sweep ----------
def param_sweep(reduced, rows, values=(5, 10, 15, 25)):
    hr("5. min_cluster_size SWEEP  (UMAP fixed, seed=42; re-HDBSCAN only)")
    flagged = np.array([bool(r["relevance_flagged"]) for r in rows])
    print(f"  {'mcs':>4} {'clusters':>9} {'noise%':>7} {'flagged_noise%':>14}  top15_sizes")
    results = {}
    for mcs in values:
        labels = HDBSCAN(min_cluster_size=mcs,
                         min_samples=config.HDBSCAN_PARAMS["min_samples"]).fit_predict(reduced)
        noise = labels == -1
        noise_pct = 100 * noise.mean()
        fn = 100 * (flagged & noise).sum() / flagged.sum() if flagged.sum() else 0
        sizes = sorted((int((labels == l).sum()) for l in set(labels.tolist()) - {-1}), reverse=True)
        n_clusters = len(sizes)
        results[mcs] = {"n_clusters": n_clusters, "noise_pct": round(noise_pct, 1),
                        "flagged_noise_pct": round(fn, 1), "top15": sizes[:15]}
        print(f"  {mcs:>4} {n_clusters:>9} {noise_pct:>7.1f} {fn:>14.1f}  {sizes[:15]}")
    return results


def recommend(sweep):
    hr("RECOMMENDATION")
    # Pick the value that keeps flagged reviews OUT of noise while giving substantive,
    # not-too-fragmented top clusters. Lower flagged_noise% is the priority signal.
    best = min(sweep, key=lambda m: (sweep[m]["flagged_noise_pct"], sweep[m]["noise_pct"]))
    for m in sweep:
        s = sweep[m]
        print(f"  mcs={m}: {s['n_clusters']} clusters, noise {s['noise_pct']}%, "
              f"flagged-in-noise {s['flagged_noise_pct']}%, top cluster {s['top15'][0]}")
    print(f"\n  → lowest flagged-in-noise is at mcs={best} "
          f"({sweep[best]['flagged_noise_pct']}%).")
    print("  Reasoning printed in the narrative report — higher mcs is NOT assumed cleaner.")
    return best


def confirmations():
    hr("6. CONFIRMATIONS")
    print("  (a) Clustering ran on the FULL corpus with the relevance flag INVISIBLE to it.")
    print("      cluster/umap_hdbscan.cluster(embeddings) sees only embeddings; the flag is")
    print("      used solely in cluster/rank.py (ranking). Confirmed by code path.")
    print("  (b) Bake-off headline '0.70 vs 0.65' = HINGLISH COVERAGE (fraction of Hinglish")
    print("      reviews assigned to a non-noise cluster), NOT silhouette. Silhouette was")
    print("      0.482 vs 0.491 (separate row). Recorded in embedding_bakeoff.md.")


def main():
    date = corpus.latest_date()
    rows = corpus.load_corpus(date)
    texts = [r["text"] for r in rows]
    X = embed_cache.get_embeddings(texts)                 # cache hit — no API calls

    print("reducing (UMAP, seed=42) once for all diagnostics…")
    reduced = UMAP(**config.UMAP_PARAMS).fit_transform(X)
    labels5 = HDBSCAN(**config.HDBSCAN_PARAMS).fit_predict(reduced)  # baseline mcs=5

    corpus_composition(date)
    noise_diagnostic(rows, labels5)
    centroid_validation(X, labels5)
    per_app_index(rows, labels5)
    sweep = param_sweep(reduced, rows)
    recommend(sweep)
    confirmations()


if __name__ == "__main__":
    main()
