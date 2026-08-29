from pipeline.ingest import pii


def test_email_scrubbed():
    assert pii.scrub("mail me at foo.bar@example.co.in please") == "mail me at [EMAIL] please"


def test_indian_phone_contiguous():
    assert "[PHONE]" in pii.scrub("call 9876543210 now")
    assert "[PHONE]" in pii.scrub("reach +91 9876543210")


def test_indian_phone_split():
    assert "[PHONE]" in pii.scrub("number is 98765 43210")


def test_long_id_scrubbed():
    assert "[ID]" in pii.scrub("order 1234567890123 was late")


def test_url_scrubbed():
    assert pii.scrub("see https://foo.com/x?y=1 now") == "see [URL] now"
    assert "[URL]" in pii.scrub("visit www.example-shop.com today")


def test_money_preserved():
    # Prices are theme signal, not PII — must survive.
    out = pii.scrub("basket was ₹1200 and I paid Rs 500 extra")
    assert "1200" in out and "500" in out
    assert "[PHONE]" not in out and "[ID]" not in out


def test_empty_and_none():
    assert pii.scrub("") == ""
    assert pii.scrub(None) == ""
