from app.nlp import analyze_sentiment, clean_text, detect_topics, is_mismatch


def test_clean_text_removes_urls_and_spaces():
    assert clean_text("Great   food  https://x.com/a ") == "Great food"


def test_sentiment_uses_domain_words():
    assert analyze_sentiment("The pizza was soggy and delivery was late.")[1] == "negative"
    assert analyze_sentiment("Food was hot, fresh and delicious.")[1] == "positive"


def test_topics_multi_label():
    topics = detect_topics("The app keeps crashing and my refund never came.")
    assert "App Experience" in topics and "Refunds" in topics


def test_delivery_fee_is_pricing_not_delivery():
    topics = detect_topics("Delivery fee and surge charges are way too high now.")
    assert topics == ["Pricing"]


def test_unknown_topic_is_other():
    assert detect_topics("Very happy with the service.") == ["Other"]


def test_mismatch():
    assert is_mismatch(5, "negative") and is_mismatch(1, "positive")
    assert not is_mismatch(5, "positive") and not is_mismatch(3, "negative")
