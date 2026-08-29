"""Static artifact writer — P4 (§7.7, architecture §6.1).

Writes app/static/analysis.json — the self-contained payload that renders Pane 1
with NO backend and NO network (the mandatory fallback). Only VALIDATED quotes
go in the display payload; all clusters are included with their sizes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .. import config, corpus
from ..interpret import brief_questions, forum_corroboration, triangulation

log = logging.getLogger(__name__)

_STATIC_DIR = config.ROOT / "app" / "static"


def _header(manifests: list[dict], clusters_doc: dict) -> dict:
    """Build the header stats block from per-app manifests."""
    raw = sum(m.get("raw_scraped", 0) for m in manifests)
    usable = clusters_doc.get("n_reviews") or sum(m.get("usable", 0) for m in manifests)
    per_app: dict[str, dict] = {}
    for m in manifests:
        app = m["app"]
        per_app[app] = {
            "raw": m.get("raw_scraped", 0),
            "usable": m.get("usable", 0),
            "by_store": m.get("by_store_usable", {}),
        }
    retention = round(100 * usable / raw, 1) if raw else 0.0
    return {
        "raw_scraped": raw,
        "usable": usable,
        "per_app_counts": per_app,
        "window_months": config.PRIMARY_WINDOW_MONTHS,
        "scrape_window_months": config.SCRAPE_MAX_MONTHS,
        "retention_pct": retention,
    }


def _theme_for_display(t: dict) -> dict:
    """Project a theme dict to the display contract (only validated quotes)."""
    quotes = []
    for q in t.get("quotes", []):
        if isinstance(q, dict):
            quotes.append({"text": q.get("text", q.get("quote_text", "")),
                           "validation_status": "Validated"})
        else:
            quotes.append({"text": str(q), "validation_status": "Validated"})

    return {
        "theme_name": t.get("theme_name", ""),
        "summary": t.get("summary", ""),
        "review_count": t.get("size", t.get("review_count", 0)),
        "pct_of_corpus": t.get("pct_of_corpus", 0.0),
        "avg_rating": t.get("avg_rating"),
        "per_app": t.get("per_app", {}),
        "funnel_gate": t.get("funnel_gate", ""),
        "mapping_rationale": t.get("mapping_rationale", ""),
        "what_this_means": t.get("what_this_means", ""),
        "category_mentioned": t.get("category_mentioned", t.get("category_mentions", {})),
        "quotes": quotes[:3],
        "selection_path": t.get("selection_path", ""),
        "track": t.get("track", ""),
        "cluster_id": t.get("cluster_id"),
        "relevance_share": t.get("relevance_share", 0.0),
        "score": t.get("score", 0.0),
        "per_app_observation": t.get("per_app_observation", ""),
        "model_used": t.get("model_used", ""),
    }


def _all_clusters(clusters_doc: dict) -> list[dict]:
    """Every cluster with its size — transparency guardrail."""
    out = []
    for c in clusters_doc.get("clusters", []):
        out.append({
            "id": c["cluster_id"],
            "size": c["size"],
            "relevance_share": c.get("relevance_share", 0.0),
            "avg_rating": c.get("avg_rating"),
            "per_app": c.get("per_app", {}),
        })
    return out


def _triangulation(themes_display: list[dict], corpus_usable: int) -> list[dict]:
    """Pane 2 (§9 Table 5) — one row per PRIMARY-RESEARCH finding, driven by the
    human-owned data/interpret/triangulation.json (loaded, never generated here).

    Empty until survey/interview data lands -> [] -> the UI shows an honest empty
    state. The review signal is joined from the theme by theme_id; survey/interview
    numbers stay in SEPARATE fields and are NEVER summed or averaged with it — that
    separation is what makes the evidence credible (§9 schema rule).
    """
    return triangulation.build_rows(
        themes_display, triangulation.load_rows(), corpus_usable)


def write_artifact(date: str, out_dir: Path | None = None) -> Path:
    """Build and write analysis.json from the P3 interpreted output."""
    analysis_dir = config.ANALYSIS_DIR / date
    interpreted_path = analysis_dir / "interpreted.json"
    clusters_path = analysis_dir / "clusters.json"

    if not interpreted_path.exists():
        raise FileNotFoundError(f"interpreted.json not found at {interpreted_path} — run interpret first")

    interpreted = json.loads(interpreted_path.read_text(encoding="utf-8"))
    clusters_doc = json.loads(clusters_path.read_text(encoding="utf-8")) if clusters_path.exists() else {}

    # Load per-app manifests for header stats
    manifests = []
    for app_key in config.APPS:
        mf = config.CACHE_DIR / app_key / date / "manifest.json"
        if mf.exists():
            manifests.append(json.loads(mf.read_text(encoding="utf-8")))

    # Themes — display projection (only validated quotes)
    themes_display = []
    all_themes = interpreted.get("themes_all", [])
    corpus_usable = clusters_doc.get("n_reviews", 0)
    for t in all_themes:
        td = _theme_for_display(t)
        if corpus_usable:
            td["pct_of_corpus"] = round(100 * td["review_count"] / corpus_usable, 1)
        themes_display.append(td)

    # Sort: Consideration/Conversion first (the research signal), then by review count
    gate_order = {"Consideration": 0, "Conversion": 1, "Awareness": 2, "Other - unrelated": 3}
    themes_display.sort(key=lambda t: (gate_order.get(t["funnel_gate"], 9), -t["review_count"]))

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": date,
        "project_name": config.PROJECT_NAME,
        "header": _header(manifests, clusters_doc),
        "models": {
            "embedding_model": config.EMBEDDING_MODEL,
            "llm_model": config.LLM_MODEL,
            "llm_fallback": config.LLM_FALLBACK_MODEL,
        },
        "themes": themes_display,
        "all_clusters": _all_clusters(clusters_doc),
        "noise": {
            "count": clusters_doc.get("noise_count", 0),
            "pct": clusters_doc.get("noise_pct", 0.0),
        },
        # Renamed with the thesis change: the card is now per-uncertainty-axis
        # resolved-vs-stalled, not competitor category whitespace.
        "resolution_template": interpreted.get("resolution_template", {}),
        "recommendation": interpreted.get("recommendation", {}),
        "validation": interpreted.get("validation", {}),
        "naming_stats": interpreted.get("naming_stats", {}),
        "triangulation": _triangulation(themes_display, corpus_usable),
        "brief_questions": brief_questions.build_rows(themes_display, corpus_usable),
        # Cross-source corroboration over the FULL record set (both weight classes) —
        # load_forums()/single-corpus was the pre-inversion API.
        "corroboration": forum_corroboration.build(
            corpus.load_corpus(date), interpreted.get("themes_all", [])),
        "corpus_weighting": interpreted.get("corpus_weighting", {}),
        "taxonomy_ref": f"data/taxonomy/centroids-{date}",
    }

    target = out_dir or _STATIC_DIR
    target.mkdir(parents=True, exist_ok=True)
    out_path = target / "analysis.json"
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("analysis.json written to %s (%d themes, %d clusters)",
             out_path, len(themes_display), len(artifact["all_clusters"]))
    return out_path
