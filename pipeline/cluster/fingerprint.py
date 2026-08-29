"""Corpus fingerprint for the locked taxonomy — the STEP 7 deploy gate.

THE FAILURE THIS PREVENTS

The clustering taxonomy (centroids + labels + novelty threshold) is a binary artifact.
Nothing about a `.npy` of centroids says which corpus produced it. A taxonomy trained on
one domain will happily accept embeddings from a completely different domain and assign
every one of them to *some* nearest centroid. There is no error, no exception, no empty
result — just confident, well-formed, entirely meaningless cluster assignments served
to whoever is looking at the deployed engine.

That is the worst class of bug available here: it does not look like a bug. It looks
like output.

So the taxonomy carries a fingerprint of the corpus it was built from, and the runtime
refuses to boot if that fingerprint is absent or does not describe the corpus this
deployment expects. Loud failure on startup, never a silent wrong answer in production.

WHAT IS CHECKED

  domain           must equal EXPECTED_DOMAIN — the decisive check. A taxonomy from a
                   previous project fails here even if everything else somehow lines up.
  apps             must match config.APPS. Retargeting the engine without retraining
                   the taxonomy is caught.
  lexicon_version  a lexicon change alters relevance flagging and therefore which
                   records were summarized; a stale taxonomy is reported as stale.
  embedding_model  centroids live in one embedding space. A different model makes the
                   cosine distances meaningless.

A missing fingerprint is treated as a FAILURE, not as "legacy, allow it". An unlabelled
taxonomy is exactly what a carried-forward artifact looks like.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import config
from ..ingest import lexicon

# The domain this deployment is built for. Changing this is a deliberate act that
# should accompany retraining the taxonomy from scratch.
EXPECTED_DOMAIN = "fashion-wishlist"

FINGERPRINT_KEY = "corpus_fingerprint"


class TaxonomyFingerprintError(RuntimeError):
    """Raised when the loaded taxonomy does not provably come from the expected corpus."""


def compute(records: list[dict], *, embedding_model: str | None = None) -> dict:
    """Build the fingerprint to embed in centroid_labels.json at taxonomy-build time.

    `corpus_hash` is order-independent (record ids are sorted) so a re-run over the
    same corpus produces the same hash regardless of scrape ordering.
    """
    ids = sorted(str(r.get("review_id", "")) for r in records)
    corpus_hash = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]
    return {
        "domain": EXPECTED_DOMAIN,
        "apps": sorted(config.APPS),
        "sources": sorted({r.get("store", "") for r in records if r.get("store")}),
        "lexicon_version": lexicon.LEXICON_VERSION,
        "embedding_model": embedding_model or config.EMBEDDING_MODEL,
        "n_records": len(records),
        "corpus_hash": corpus_hash,
    }


def verify(fp: dict | None, *, strict: bool = True) -> list[str]:
    """Verify a fingerprint against this deployment's expectations.

    Returns a list of warning strings for non-fatal drift. Raises
    TaxonomyFingerprintError for anything that makes the taxonomy WRONG rather than
    merely stale. With strict=False, drift that would raise is returned as warnings
    instead — for offline inspection only, never for the serving path.
    """
    if not fp:
        raise TaxonomyFingerprintError(
            "Taxonomy has NO corpus fingerprint. Refusing to boot.\n"
            "  An unfingerprinted taxonomy cannot be shown to come from this project's "
            "corpus, and a taxonomy from another corpus produces confident nonsense "
            "rather than an error.\n"
            "  Fix: rebuild the taxonomy from the current corpus so that "
            f"centroid_labels.json carries a {FINGERPRINT_KEY!r} block."
        )

    problems: list[str] = []
    warnings: list[str] = []

    domain = fp.get("domain")
    if domain != EXPECTED_DOMAIN:
        problems.append(
            f"domain is {domain!r}, expected {EXPECTED_DOMAIN!r} — this taxonomy was "
            f"trained on a different corpus entirely."
        )

    apps = fp.get("apps") or []
    if sorted(apps) != sorted(config.APPS):
        problems.append(
            f"apps are {sorted(apps)}, this deployment serves {sorted(config.APPS)} — "
            f"the taxonomy does not cover the apps being assigned to it."
        )

    model = fp.get("embedding_model")
    if model and model != config.EMBEDDING_MODEL:
        problems.append(
            f"embedding_model is {model!r} but this deployment embeds with "
            f"{config.EMBEDDING_MODEL!r} — centroid distances are not comparable "
            f"across embedding spaces."
        )

    lex = fp.get("lexicon_version")
    if lex and lex != lexicon.LEXICON_VERSION:
        warnings.append(
            f"lexicon drift: taxonomy built at lexicon {lex}, current is "
            f"{lexicon.LEXICON_VERSION}. Assignments remain valid; relevance flagging "
            f"may have shifted since. Consider a rebuild."
        )

    if problems:
        if strict:
            raise TaxonomyFingerprintError(
                "Taxonomy does not match this deployment's corpus. Refusing to boot.\n"
                + "".join(f"  - {p}\n" for p in problems)
                + "  Fix: rebuild the taxonomy from the current corpus, or deploy the "
                  "taxonomy that matches this configuration. Do NOT bypass this check — "
                  "a mismatched taxonomy returns plausible-looking wrong answers."
            )
        warnings.extend(problems)

    return warnings


def read_from_labels(labels_path: Path | str) -> tuple[dict | None, list]:
    """Read (fingerprint, labels) from centroid_labels.json.

    Supports both the fingerprinted schema and the bare-list schema. A bare list
    returns fingerprint=None, which verify() treats as a hard failure — that is the
    intended outcome for an artifact carried forward from another project.
    """
    raw = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw.get(FINGERPRINT_KEY), raw.get("labels", [])
    return None, raw


def write_labels(labels_path: Path | str, labels: list, fingerprint: dict) -> None:
    """Persist centroid labels WITH their fingerprint. The only supported writer."""
    Path(labels_path).write_text(
        json.dumps({FINGERPRINT_KEY: fingerprint, "labels": list(labels)}, indent=2),
        encoding="utf-8",
    )
