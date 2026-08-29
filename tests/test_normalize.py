from pipeline.ingest import normalize
from pipeline.ingest.scrapers import raw_record


def _raw(text, rating=5, store="play", date="2026-07-01"):
    return raw_record("Myntra", store, text, rating, date)


def test_word_floor_drops_short():
    reviews, stats = normalize.normalize_corpus("Myntra", [_raw("good app")])
    assert stats["usable"] == 0 and stats["floor_dropped"] == 1


def test_hinglish_kept_and_tagged():
    # Distinctive romanized-Hindi review must be kept and tagged hinglish.
    text = "bas sale ke liye theek hai baaki sab bahut mehenga hai yaar"
    reviews, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    assert len(reviews) == 1
    assert reviews[0].language == "hinglish"


def test_english_tagged_en():
    text = "delivery was fast and the packaging quality was genuinely excellent overall"
    reviews, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    assert reviews[0].language == "en"


def test_emoji_stripped_but_review_kept():
    text = "the delivery person was very polite and quick every single time 😊👍🔥🎉"
    reviews, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    assert len(reviews) == 1
    assert "😊" not in reviews[0].text and "👍" not in reviews[0].text


def test_pii_scrubbed_before_store():
    text = "great service but they leaked my number 9876543210 to a third party seller"
    reviews, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    assert "[PHONE]" in reviews[0].text and "9876543210" not in reviews[0].text


def test_relevance_flag_and_category():
    text = ("saved this dress on myntra months ago but i am still not sure about the "
            "size so i keep checking amazon reviews before buying")
    reviews, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    r = reviews[0]
    assert r.relevance_flagged is True
    assert "Size" in r.category_mentioned


def test_review_id_stable():
    text = "consistent identifier check for a sufficiently long review body here now"
    r1, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    r2, _ = normalize.normalize_corpus("Myntra", [_raw(text)])
    assert r1[0].review_id == r2[0].review_id


def test_source_app_and_store_present():
    text = "the app first-class source app and store fields must always be populated ok"
    reviews, _ = normalize.normalize_corpus("AJIO", [raw_record("AJIO", "appstore", text, 4, "2026-06-01")])
    assert reviews[0].app == "AJIO" and reviews[0].store == "appstore"
