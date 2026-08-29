from pipeline.ingest.dedupe import dedupe


def _rec(text, rating=5, date="2026-07-01"):
    return {"text": text, "rating": rating, "posted_date": date, "store": "play"}


def test_identical_triple_collapses():
    recs = [_rec("great app"), _rec("great app"), _rec("great app")]
    out, dropped = dedupe(recs)
    assert len(out) == 1 and dropped == 2


def test_whitespace_and_case_variants_collapse():
    recs = [_rec("Great App"), _rec("great   app"), _rec("  GREAT APP ")]
    out, dropped = dedupe(recs)
    assert len(out) == 1 and dropped == 2


def test_different_rating_kept_separate():
    recs = [_rec("nice", rating=5), _rec("nice", rating=1)]
    out, dropped = dedupe(recs)
    assert len(out) == 2 and dropped == 0


def test_first_occurrence_wins():
    recs = [_rec("Keep This Casing"), _rec("keep this casing")]
    out, _ = dedupe(recs)
    assert out[0]["text"] == "Keep This Casing"
