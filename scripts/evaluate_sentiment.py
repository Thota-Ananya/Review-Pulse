"""
How good is the sentiment model? We have no hand-labelled data, so we use star ratings as a
weak label (4-5 stars = positive, 1-2 = negative, 3 stars excluded) and measure agreement.
Disagreements are not all model errors: some customers' stars contradict their words.

Usage: python scripts/evaluate_sentiment.py [path/to/reviews.csv]
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app.nlp import analyze_sentiment  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "sample_reviews.csv"
df = pd.read_csv(path)
df = df[df["rating"] != 3]
df["truth"] = df["rating"].map(lambda r: "positive" if r >= 4 else "negative")
df["pred"] = df["review_text"].map(lambda t: analyze_sentiment(str(t))[1])

pairs = Counter(zip(df["truth"], df["pred"], strict=True))
print(f"Reviews evaluated (excluding 3-star): {len(df)}")
print(f"Agreement with star rating: {(df['truth'] == df['pred']).mean():.1%}\n")
print("Confusion matrix (rows = stars, cols = model)")
print(f"{'':>10}{'positive':>10}{'neutral':>10}{'negative':>10}")
for t in ("positive", "negative"):
    print(f"{t:>10}" + "".join(f"{pairs[(t, p)]:>10}" for p in ("positive", "neutral", "negative")))
for label in ("positive", "negative"):
    tp = pairs[(label, label)]
    predicted = sum(pairs[(t, label)] for t in ("positive", "negative"))
    actual = sum(pairs[(label, p)] for p in ("positive", "neutral", "negative"))
    print(f"\n{label}: precision {tp / predicted:.1%}, recall {tp / actual:.1%}")
