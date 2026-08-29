"""Embedding bake-off — P2 methodology gate (§7.2).

Compares the primary (openai/text-embedding-3-large) against the challenger
(qwen/qwen3-embedding-8b) on a language-STRATIFIED sample that enriches Hinglish,
because the stated selection criterion is code-mixed Hinglish performance — NOT
MTEB rank. Clusters each embedding set with the identical UMAP->HDBSCAN config and
compares coherence. If results are indistinguishable, the primary ships and that
is recorded as a finding. Writes a methodology note the deck can cite.

Run:  python -m pipeline.embed.bakeoff
"""
from __future__ import annotations

import json
import logging
import random

import numpy as np
from sklearn.metrics import silhouette_score

from .. import config, corpus
from ..cluster import umap_hdbscan
from . import cache as embed_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("bakeoff")

SEED = 42
N_PER_LANG = 100


def stratified_sample(rows: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    hing = [r for r in rows if r["language"] == "hinglish"]
    eng = [r for r in rows if r["language"] == "en"]
    rng.shuffle(hing)
    rng.shuffle(eng)
    sample = hing[:N_PER_LANG] + eng[:N_PER_LANG]
    rng.shuffle(sample)
    return sample


def _metrics(labels: np.ndarray, reduced: np.ndarray, langs: list[str]) -> dict:
    labels = np.asarray(labels)
    n_clusters = len(set(labels.tolist()) - {-1})
    noise = float((labels == -1).mean())
    mask = labels != -1
    sil = None
    if n_clusters >= 2 and mask.sum() > n_clusters:
        try:
            sil = round(float(silhouette_score(reduced[mask], labels[mask])), 3)
        except ValueError:
            sil = None
    hmask = np.array([lang == "hinglish" for lang in langs])
    hing_cov = round(float((labels[hmask] != -1).mean()), 3) if hmask.any() else None
    return {"n_clusters": n_clusters, "noise": round(noise, 3),
            "silhouette": sil, "hinglish_coverage": hing_cov}


def _evaluate(texts: list[str], langs: list[str], model: str) -> dict:
    log.info("bake-off: embedding %d reviews with %s", len(texts), model)
    X = embed_cache.get_embeddings(texts, model=model)
    labels, reduced, _, _ = umap_hdbscan.cluster(X)
    m = _metrics(labels, reduced, langs)
    m["dims"] = int(X.shape[1])
    return m


def run() -> dict:
    rows = corpus.load_corpus()
    if not rows:
        raise SystemExit("no corpus — run `ingest` then `cluster` first")
    sample = stratified_sample(rows)
    texts = [r["text"] for r in sample]
    langs = [r["language"] for r in sample]
    n_hing = langs.count("hinglish")
    log.info("sample: %d reviews (%d hinglish, %d english)", len(sample), n_hing, langs.count("en"))

    primary = _evaluate(texts, langs, config.EMBEDDING_MODEL)
    challenger = _evaluate(texts, langs, config.EMBEDDING_CHALLENGER)

    # Decision: prefer challenger only if it beats primary on Hinglish coverage by a
    # meaningful margin without losing coherence; else ship primary (§7.2).
    pc, cc = primary["hinglish_coverage"] or 0, challenger["hinglish_coverage"] or 0
    ps, cs = primary["silhouette"] or 0, challenger["silhouette"] or 0
    if cc - pc > 0.05 and cs >= ps - 0.02:
        choice, reason = config.EMBEDDING_CHALLENGER, (
            f"challenger Hinglish coverage {cc} vs {pc} (+{round(cc-pc,3)}) without losing coherence")
    else:
        choice, reason = config.EMBEDDING_MODEL, (
            f"no decisive Hinglish-coverage gain (primary {pc} vs challenger {cc}); "
            f"primary ships — indistinguishable or better")

    result = {
        "sample_size": len(sample), "hinglish_in_sample": n_hing, "seed": SEED,
        "primary": {"model": config.EMBEDDING_MODEL, **primary},
        "challenger": {"model": config.EMBEDDING_CHALLENGER, **challenger},
        "choice": choice, "reason": reason,
    }

    date = corpus.latest_date()
    out = config.ANALYSIS_DIR / date
    out.mkdir(parents=True, exist_ok=True)
    (out / "embedding_bakeoff.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_note(out / "embedding_bakeoff.md", result)

    print("\n=== Embedding bake-off ===")
    print(f"  sample: {len(sample)} reviews ({n_hing} hinglish), seed={SEED}")
    for k in ("primary", "challenger"):
        r = result[k]
        print(f"  {k:<10} {r['model']:<32} dims={r['dims']:<5} clusters={r['n_clusters']:<3} "
              f"noise={r['noise']} silhouette={r['silhouette']} hinglish_cov={r['hinglish_coverage']}")
    print(f"  -> CHOICE: {choice}\n     {reason}")
    print(f"  note -> {out / 'embedding_bakeoff.md'}")
    return result


def _write_note(path, r: dict) -> None:
    p, c = r["primary"], r["challenger"]
    path.write_text(
        f"""# Embedding Bake-off — Methodology Note

**Gate (§7.2):** choose the embedding model on **code-mixed Hinglish performance**,
not MTEB rank. Language-stratified sample of {r['sample_size']} reviews
({r['hinglish_in_sample']} Hinglish), seed {r['seed']}, identical UMAP→HDBSCAN config.

**Decision metric = Hinglish coverage** — the fraction of Hinglish reviews assigned
to a real (non-noise) cluster. The headline comparison ({p['hinglish_coverage']} vs
{c['hinglish_coverage']}) is this metric, NOT silhouette. Silhouette (cluster-separation
coherence) is reported as a secondary guard so we don't trade Hinglish gains for
incoherent clusters.

| Metric | Primary — {p['model']} | Challenger — {c['model']} |
|---|---|---|
| Dimensions | {p['dims']} | {c['dims']} |
| Clusters found | {p['n_clusters']} | {c['n_clusters']} |
| Noise fraction | {p['noise']} | {c['noise']} |
| Silhouette (coherence) | {p['silhouette']} | {c['silhouette']} |
| **Hinglish coverage** | **{p['hinglish_coverage']}** | **{c['hinglish_coverage']}** |

*Hinglish coverage = fraction of Hinglish reviews assigned to a real (non-noise)
cluster — higher means the model represents code-mixed text meaningfully.*

**Decision: `{r['choice']}`** — {r['reason']}
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    run()
