"""ETL: validate a CSV/DataFrame of reviews -> enrich with NLP -> load into SQL."""
from datetime import timedelta

import pandas as pd
from sqlalchemy.orm import Session

from .models import Review, ReviewTopic
from .nlp import analyze_sentiment, clean_text, detect_topics, is_mismatch

REQUIRED = {"review_text", "rating", "date"}
ALIASES = {"text": "review_text", "review": "review_text", "comment": "review_text",
           "stars": "rating", "score": "rating", "review_date": "date", "created_at": "date"}


class IngestError(ValueError):
    pass


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
    df = df.rename(columns={k: v for k, v in ALIASES.items() if k in df.columns and v not in df.columns})
    missing = REQUIRED - set(df.columns)
    if missing:
        raise IngestError(f"CSV is missing required column(s): {', '.join(sorted(missing))}. "
                          f"Required: review_text, rating, date. Optional: city, platform, review_id.")
    return df


def ingest_dataframe(db: Session, df: pd.DataFrame, batch_size: int = 500) -> dict:
    df = normalise_columns(df)
    total = len(df)

    # --- Transform & validate (vectorised with pandas) ---
    df["review_text"] = df["review_text"].fillna("").astype(str).map(clean_text)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for col in ("city", "platform"):
        df[col] = (df[col].fillna("Unknown").astype(str).str.strip().str.title()
                   if col in df.columns else "Unknown")
    df["platform"] = df["platform"].replace({"Ios": "iOS"})

    valid = (df["review_text"].str.len() > 0) & df["rating"].between(1, 5) & df["date"].notna()
    skipped = int((~valid).sum())
    df = df[valid]

    # --- Load ---
    inserted = 0
    for start in range(0, len(df), batch_size):
        chunk = df.iloc[start:start + batch_size]
        for row in chunk.itertuples(index=False):
            rating = int(round(row.rating))
            score, label = analyze_sentiment(row.review_text)
            review = Review(
                source_id=str(getattr(row, "review_id", "") or "") or None,
                review_date=row.date,
                week_start=row.date - timedelta(days=row.date.weekday()),
                city=row.city, platform=row.platform, rating=rating, text=row.review_text,
                sentiment_score=score, sentiment_label=label, mismatch=is_mismatch(rating, label),
            )
            review.topics = [ReviewTopic(topic=t) for t in detect_topics(row.review_text)]
            db.add(review)
            inserted += 1
        db.commit()

    return {"rows_received": total, "inserted": inserted, "skipped_invalid": skipped}


def ingest_csv(db: Session, file_or_path) -> dict:
    try:
        df = pd.read_csv(file_or_path)
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the user
        raise IngestError(f"Could not read CSV: {exc}") from exc
    return ingest_dataframe(db, df)
