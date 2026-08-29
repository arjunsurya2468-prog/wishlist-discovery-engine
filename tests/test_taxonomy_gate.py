"""STEP 7 — the taxonomy corpus-fingerprint gate.

These tests exist because the failure they guard against is invisible. A taxonomy
trained on the wrong corpus does not crash; it assigns every input to some nearest
centroid and produces confident, well-formed, meaningless output. If this gate ever
silently stops working, nothing downstream would notice.
"""
from __future__ import annotations

import json

import pytest

from pipeline import config
from pipeline.cluster import fingerprint as fp


def _records(n=50, store="reddit"):
    return [{"review_id": f"r{i}", "store": store} for i in range(n)]


def test_missing_fingerprint_is_refused():
    """An unfingerprinted taxonomy is what a carried-forward artifact looks like."""
    with pytest.raises(fp.TaxonomyFingerprintError, match="NO corpus fingerprint"):
        fp.verify(None)


def test_legacy_bare_list_schema_yields_no_fingerprint(tmp_path):
    """The previous build wrote centroid_labels.json as a bare list."""
    p = tmp_path / "centroid_labels.json"
    p.write_text(json.dumps([0, 1, 2, 3]))
    got, labels = fp.read_from_labels(p)
    assert got is None
    assert labels == [0, 1, 2, 3]
    with pytest.raises(fp.TaxonomyFingerprintError):
        fp.verify(got)


# A fingerprint from some OTHER corpus. The domain and app names here are deliberately
# generic placeholders: what the gate must catch is "this taxonomy is not ours", and
# that property has nothing to do with which specific domain it came from.
FOREIGN_DOMAIN = "some-other-domain"
FOREIGN_APPS = ["AppOne", "AppTwo", "AppThree"]


def test_wrong_domain_is_refused():
    """The exact scenario the fingerprint gate exists for: a taxonomy built elsewhere."""
    stale = {
        "domain": FOREIGN_DOMAIN,
        "apps": FOREIGN_APPS,
        "embedding_model": config.EMBEDDING_MODEL,
        "lexicon_version": "old",
        "n_records": 38000,
        "corpus_hash": "0" * 16,
    }
    with pytest.raises(fp.TaxonomyFingerprintError) as exc:
        fp.verify(stale)
    msg = str(exc.value)
    assert FOREIGN_DOMAIN in msg and fp.EXPECTED_DOMAIN in msg


def test_wrong_apps_is_refused():
    good = fp.compute(_records())
    good["apps"] = ["Myntra"]
    with pytest.raises(fp.TaxonomyFingerprintError, match="does not cover the apps"):
        fp.verify(good)


def test_wrong_embedding_model_is_refused():
    """Centroid distances are meaningless across embedding spaces."""
    good = fp.compute(_records())
    good["embedding_model"] = "some/other-embedding-model"
    with pytest.raises(fp.TaxonomyFingerprintError, match="not comparable"):
        fp.verify(good)


def test_lexicon_drift_warns_but_does_not_block():
    """Stale is not the same as wrong — a lexicon bump must not brick a deploy."""
    good = fp.compute(_records())
    good["lexicon_version"] = "1999-01-01.1"
    warnings = fp.verify(good)
    assert any("lexicon drift" in w for w in warnings)


def test_matching_fingerprint_passes_clean():
    assert fp.verify(fp.compute(_records())) == []


def test_fingerprint_is_order_independent():
    """Scrape order must not change the corpus hash."""
    recs = _records(30)
    assert fp.compute(recs)["corpus_hash"] == fp.compute(list(reversed(recs)))["corpus_hash"]


def test_fingerprint_changes_with_corpus():
    assert fp.compute(_records(30))["corpus_hash"] != fp.compute(_records(31))["corpus_hash"]


def test_write_read_round_trip(tmp_path):
    p = tmp_path / "centroid_labels.json"
    finger = fp.compute(_records())
    fp.write_labels(p, [0, 1, 2], finger)
    got, labels = fp.read_from_labels(p)
    assert got == finger
    assert labels == [0, 1, 2]
    assert fp.verify(got) == []


def test_nykaa_fashion_excluded_from_community_sources():
    """STEP 4 — the exclusion is structural, not a downstream keyword filter."""
    for source in ("reddit", "youtube", "twitter", "forum"):
        keys = [s.key for s in config.apps_for(source)]
        assert "Nykaa Fashion" not in keys, f"Nykaa Fashion leaked into {source}"
    for source in ("play", "appstore"):
        assert "Nykaa Fashion" in [s.key for s in config.apps_for(source)]


# ---- STEP 4 (hardened): sibling-listing blocklist ----------------------------------

def test_blocked_ids_are_rejected_at_config_level():
    """Nykaa ships three listings under one developer. Only Fashion is in scope.

    A wrong-but-valid package scrapes cleanly and fills the corpus with beauty reviews.
    Nothing downstream would flag it — the reviews are well-formed and about shopping,
    just about the wrong catalogue. So it is caught in config, at import.
    """
    for blocked, why in config.BLOCKED_STORE_IDS.items():
        assert "out of scope" in why

    bad = dict(config.APPS)
    bad["Nykaa Fashion"] = config.AppSpec(
        key="Nykaa Fashion", role="comparator",
        play_package="com.fsn.nykaa",          # Nykaa BEAUTY
        appstore_id="1439872423",
        sources=frozenset({"play", "appstore"}), community_terms=(),
    )
    with pytest.raises(config.BlockedStoreIdError, match="Nykaa Beauty|blocked prefix"):
        config._assert_no_blocked_ids(bad)


def test_blocked_ios_id_is_rejected():
    bad = dict(config.APPS)
    bad["Nykaa Fashion"] = config.AppSpec(
        key="Nykaa Fashion", role="comparator",
        play_package="com.fsn.nds",
        appstore_id="1022363908",              # Nykaa Beauty iOS
        sources=frozenset({"play", "appstore"}), community_terms=(),
    )
    with pytest.raises(config.BlockedStoreIdError, match="Nykaa Beauty"):
        config._assert_no_blocked_ids(bad)


def test_nykaa_man_package_is_rejected():
    bad = dict(config.APPS)
    bad["Nykaa Fashion"] = config.AppSpec(
        key="Nykaa Fashion", role="comparator",
        play_package="com.fsn.nykaa.man",      # Nykaa Man
        appstore_id="1439872423",
        sources=frozenset({"play", "appstore"}), community_terms=(),
    )
    with pytest.raises(config.BlockedStoreIdError):
        config._assert_no_blocked_ids(bad)


def test_live_config_passes_its_own_blocklist():
    """The shipped config must survive the check it imposes on everything else."""
    config._assert_no_blocked_ids()
    assert config.APPS["Nykaa Fashion"].play_package == "com.fsn.nds"
    assert config.verify_app_ids() == []
