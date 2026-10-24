"""
Text analytics: cleaning, sentiment and topic tagging.

- Sentiment uses VADER (a rule-based model built for short social text), extended with a
  small food-delivery lexicon so domain words like "late", "soggy" or "crashing" count.
- Topics use transparent keyword rules, so every tag can be explained to a business user.
"""
import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()
_analyzer.lexicon.update({
    # negative domain words (VADER scale is roughly -4..+4)
    "late": -1.5, "delayed": -1.6, "delay": -1.4, "cold": -1.2, "stale": -1.8, "soggy": -1.8,
    "undercooked": -1.8, "bland": -1.4, "oily": -1.0, "tiny": -0.8, "leaked": -1.8,
    "spilled": -1.5, "flimsy": -1.5, "messy": -1.3, "overpriced": -2.0, "expensive": -1.0,
    "hidden": -0.8, "crashing": -2.0, "crash": -2.0, "crashes": -2.0, "freezes": -1.5,
    "buggy": -2.0, "fails": -1.6, "slow": -1.2, "waiting": -0.6, "unhelpful": -1.8,
    # positive domain words
    "fresh": 1.5, "quick": 1.2, "fast": 1.3, "smooth": 1.5, "instantly": 1.0,
    "hygienic": 1.5, "flavourful": 1.8, "impressive": 2.0, "resolved": 1.2,
})

POS_THRESHOLD, NEG_THRESHOLD = 0.05, -0.05

# Order matters only for display. Patterns are regexes matched on cleaned lowercase text.
TOPIC_RULES: dict[str, list[str]] = {
    # "delivery fee" is a pricing complaint and "free delivery" is a pricing offer, so exclude them
    "Delivery": [r"(?<!free )deliver(y|ed)(?! fee| charges?)", r"rider", r"\beta\b", r"\blate\b",
                 r"delay(ed)?", r"on time", r"arrived", r"long route"],
    "Food Quality": [r"\bfood\b", r"tast(e|ed)", r"stale", r"\bcold\b", r"fresh", r"bland",
                     r"oily", r"soggy", r"undercooked", r"delicious", r"portion", r"biryani",
                     r"pizza", r"curry", r"paneer", r"flavou?rful"],
    "Packaging": [r"packag(ing|e)", r"leak(ed)?", r"spill", r"container", r"sealed"],
    "Pricing": [r"price[sd]?", r"overpriced", r"expensive", r"\bfees?\b", r"charges?",
                r"surge", r"discounts?", r"coupon", r"offers?", r"value for money"],
    "App Experience": [r"\bapp\b", r"crash", r"freez", r"\bbug", r"login", r"update",
                       r"tracking", r"reinstall"],
    "Customer Support": [r"support", r"customer care", r"\bagent\b", r"ticket", r"helpline"],
    "Refunds": [r"refund", r"credited", r"money back"],
}
_COMPILED = {t: [re.compile(p) for p in pats] for t, pats in TOPIC_RULES.items()}
TOPICS = list(TOPIC_RULES) + ["Other"]


def clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def analyze_sentiment(text: str) -> tuple[float, str]:
    score = _analyzer.polarity_scores(text)["compound"]
    if score >= POS_THRESHOLD:
        label = "positive"
    elif score <= NEG_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"
    return round(score, 4), label


def detect_topics(text: str) -> list[str]:
    low = text.lower()
    found = [t for t, pats in _COMPILED.items() if any(p.search(low) for p in pats)]
    return found or ["Other"]


def is_mismatch(rating: int, label: str) -> bool:
    """Happy stars but unhappy words (or the reverse): a signal star ratings alone miss."""
    return (rating >= 4 and label == "negative") or (rating <= 2 and label == "positive")
