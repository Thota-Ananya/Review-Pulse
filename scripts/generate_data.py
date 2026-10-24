"""
Generate a realistic *synthetic* customer-review dataset for "QuickBite",
a fictional food-delivery company.

Three business problems are deliberately hidden in the data so the
insights engine has something real to discover:
  1. Delivery delays spike in Hyderabad in the last 4 weeks.
  2. An iOS app update (v5.2) causes checkout crashes in the last 3 weeks.
  3. Pricing complaints rise steadily after a platform-fee hike (week 16).

Usage:  python scripts/generate_data.py            -> data/sample_reviews.csv
        python scripts/generate_data.py --n 5000   -> bigger dataset
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

START = date(2026, 4, 20)  # Monday
WEEKS = 26

CITIES = {"Hyderabad": .25, "Bengaluru": .20, "Mumbai": .15, "Chennai": .12,
          "Delhi": .12, "Pune": .10, "Warangal": .06}
PLATFORMS = {"Android": .55, "iOS": .30, "Web": .15}

PHRASES = {
    "Delivery": {
        "neg": ["Delivery was delayed by over an hour and the rider never picked up my calls.",
                "Order arrived 50 minutes late, really frustrating.",
                "The rider took a very long route, my order reached late.",
                "Late delivery again. This is the third time this week.",
                "Rider marked the order delivered but it never arrived.",
                "Terrible delivery time, the ETA kept increasing."],
        "pos": ["Delivery was super quick, arrived before the ETA.",
                "The rider was polite and the order came right on time.",
                "Fast delivery even in heavy rain, great job.",
                "Delivered within 25 minutes, impressive."],
    },
    "Food Quality": {
        "neg": ["The food was cold and the biryani tasted stale.",
                "Portion size was tiny and the curry was too oily.",
                "Pizza was soggy and undercooked, very disappointed.",
                "Found the food bland and not fresh at all."],
        "pos": ["Food was hot, fresh and delicious.",
                "Loved the taste, the paneer tikka was amazing.",
                "Great quality food, exactly like dining at the restaurant.",
                "The biryani was flavourful and the portion was generous."],
    },
    "Packaging": {
        "neg": ["The packaging was poor and the gravy leaked all over the bag.",
                "Container was broken and the drink spilled.",
                "Packaging was flimsy, everything was messy."],
        "pos": ["Neat packaging, nothing spilled.",
                "Packaging was sealed and spill-proof, very hygienic."],
    },
    "Pricing": {
        "neg": ["Delivery fee and surge charges are way too high now.",
                "Items are overpriced compared to the restaurant menu.",
                "Hidden charges at checkout, the platform fee keeps increasing.",
                "Too expensive, the new fees are not worth it."],
        "pos": ["Good discounts and the coupon saved me a lot.",
                "Reasonable prices and great offers this week.",
                "Value for money with the free delivery offer."],
    },
    "App Experience": {
        "neg": ["The app keeps crashing at checkout after the latest update.",
                "App freezes when I try to pay, had to reinstall.",
                "Very buggy app, the cart keeps getting cleared.",
                "Login fails and the app is slow to load."],
        "pos": ["The app is smooth and easy to use.",
                "Love the new app design, ordering is very simple.",
                "Live tracking in the app works perfectly."],
    },
    "Customer Support": {
        "neg": ["Customer support is useless, the chat agent just closed my ticket.",
                "Waited 40 minutes for customer care and got no help.",
                "Support staff were rude and unhelpful."],
        "pos": ["Customer support resolved my issue in minutes.",
                "The support agent was very helpful and kind."],
    },
    "Refunds": {
        "neg": ["Still waiting for my refund for a cancelled order.",
                "Refund was rejected even though items were missing.",
                "They promised a refund but never credited it."],
        "pos": ["Got a quick refund for the missing item, no questions asked.",
                "Refund was processed instantly to my wallet."],
    },
}
GENERIC = {"pos": ["Great experience overall, will order again.", "Very happy with the service.",
                   "Excellent, highly recommend."],
           "neg": ["Not happy with the experience.", "Worst experience, never again.",
                   "Very disappointing overall."]}

BASE_TOPIC_WEIGHT = {"Delivery": .26, "Food Quality": .24, "Packaging": .08, "Pricing": .12,
                     "App Experience": .14, "Customer Support": .09, "Refunds": .07}
BASE_NEG_PROB = {"Delivery": .35, "Food Quality": .30, "Packaging": .35, "Pricing": .30,
                 "App Experience": .25, "Customer Support": .45, "Refunds": .50}


def pick(weights: dict, rng: random.Random):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def scenario(week: int, city: str, platform: str):
    """Return topic weights and negative probabilities for this context (the hidden story)."""
    tw, neg = dict(BASE_TOPIC_WEIGHT), dict(BASE_NEG_PROB)
    if city == "Hyderabad" and week >= WEEKS - 4:          # 1. delivery crisis
        tw["Delivery"] *= 2.0
        neg["Delivery"] = .80
    if platform == "iOS" and week >= WEEKS - 3:            # 2. bad iOS release
        tw["App Experience"] *= 2.6
        neg["App Experience"] = .85
    if week >= 16:                                         # 3. fee hike
        tw["Pricing"] *= 1.0 + (week - 15) * 0.08
        neg["Pricing"] = min(.70, .30 + (week - 15) * 0.04)
    return tw, neg


def make_review(rng: random.Random, week: int):
    city, platform = pick(CITIES, rng), pick(PLATFORMS, rng)
    tw, neg = scenario(week, city, platform)
    roll = rng.random()
    if roll < .08:  # generic review with no specific topic
        mood = "neg" if rng.random() < .35 else "pos"
        text, moods = rng.choice(GENERIC[mood]), [mood]
    else:
        n_topics = 1 if roll < .78 else 2
        topics = []
        while len(topics) < n_topics:
            t = pick(tw, rng)
            if t not in topics:
                topics.append(t)
        moods = ["neg" if rng.random() < neg[t] else "pos" for t in topics]
        text = " ".join(rng.choice(PHRASES[t][m]) for t, m in zip(topics, moods, strict=True))

    if all(m == "neg" for m in moods):
        rating = rng.choice([1, 1, 2, 2, 2])
    elif all(m == "pos" for m in moods):
        rating = rng.choice([4, 5, 5])
    else:
        rating = rng.choice([2, 3, 3, 4])
    if rng.random() < .06:  # real users often give stars that don't match their words
        rating = 4 if rating <= 2 else (2 if rating >= 4 else rating)

    day = START + timedelta(weeks=week, days=rng.randint(0, 6))
    return {"date": day.isoformat(), "city": city, "platform": platform,
            "rating": rating, "review_text": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2600, help="approximate number of reviews")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "sample_reviews.csv"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = []
    per_week = args.n / WEEKS
    for w in range(WEEKS):
        volume = int(per_week * (0.8 + 0.4 * w / WEEKS) * rng.uniform(.9, 1.1))  # business is growing
        rows += [make_review(rng, w) for _ in range(volume)]
    rows.sort(key=lambda r: r["date"])
    for i, r in enumerate(rows, 1):
        r["review_id"] = f"QB{i:05d}"

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["review_id", "date", "city", "platform", "rating", "review_text"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} reviews -> {args.out}")


if __name__ == "__main__":
    main()
