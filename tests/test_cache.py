"""Store-aware cache reuse (§7.1) — guards the partial-cache footgun: a run that
requests a store not in the cache must fetch that store, not silently skip."""
from pipeline import cache
from pipeline.ingest.scrapers import raw_record


def _seed(tmp_cache, app, date, stores):
    recs = [raw_record(app, s, f"a sufficiently long review body number {i} here", 5, "2026-07-01")
            for i, s in enumerate(stores)]
    cache.save_raw(app, date, recs)


def test_raw_stores_reports_present_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.config, "CACHE_DIR", tmp_path)
    _seed(cache, "Myntra", "2026-07-22", ["play"])
    assert cache.raw_stores("Myntra", "2026-07-22") == {"play"}


def test_raw_stores_empty_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.config, "CACHE_DIR", tmp_path)
    assert cache.raw_stores("AJIO", "2026-07-22") == set()


def test_missing_store_is_detected(tmp_path, monkeypatch):
    # play cached, appstore requested -> appstore is the gap that must be fetched.
    monkeypatch.setattr(cache.config, "CACHE_DIR", tmp_path)
    _seed(cache, "Myntra", "2026-07-22", ["play"])
    present = cache.raw_stores("Myntra", "2026-07-22")
    requested = ["play", "appstore"]
    missing = [s for s in requested if s not in present]
    assert missing == ["appstore"]


def test_corrupt_raw_is_safe(tmp_path, monkeypatch):
    # A corrupt cache file must be a re-scrape signal, not a crash (edge-cases §1.7).
    monkeypatch.setattr(cache.config, "CACHE_DIR", tmp_path)
    d = cache.cache_dir("Myntra", "2026-07-22")
    (d / "reviews_raw.json").write_text("{ this is not valid json", encoding="utf-8")
    assert cache.load_raw_safe("Myntra", "2026-07-22") is None
    assert cache.raw_stores("Myntra", "2026-07-22") == set()
