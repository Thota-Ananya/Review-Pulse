"""
Analytics layer. Hand-written, parameterised SQL (portable across SQLite / PostgreSQL / MySQL)
so the business logic is visible and reviewable, and safe from SQL injection.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def as_date(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _where(city: str | None, platform: str | None, alias: str = "r") -> tuple[str, dict]:
    clauses, params = ["1=1"], {}
    if city:
        clauses.append(f"{alias}.city = :city")
        params["city"] = city
    if platform:
        clauses.append(f"{alias}.platform = :platform")
        params["platform"] = platform
    return " AND ".join(clauses), params


def _rows(db: Session, sql: str, params: dict) -> list[dict]:
    return [dict(r._mapping) for r in db.execute(text(sql), params)]


def kpis(db: Session, city=None, platform=None) -> dict:
    where, p = _where(city, platform)
    row = _rows(db, f"""
        SELECT COUNT(*)                                                       AS total_reviews,
               AVG(r.rating)                                                  AS avg_rating,
               AVG(CASE WHEN r.rating >= 4 THEN 1.0 ELSE 0 END)               AS csat,
               AVG(CASE WHEN r.sentiment_label = 'positive' THEN 1.0 ELSE 0 END) AS pct_positive,
               AVG(CASE WHEN r.sentiment_label = 'negative' THEN 1.0 ELSE 0 END) AS pct_negative,
               SUM(CASE WHEN r.mismatch THEN 1 ELSE 0 END)                    AS mismatches
        FROM reviews r WHERE {where}""", p)[0]
    r = lambda v, n=3: round(float(v), n) if v is not None else None  # noqa: E731
    return {"total_reviews": row["total_reviews"] or 0, "avg_rating": r(row["avg_rating"], 2),
            "csat": r(row["csat"]), "pct_positive": r(row["pct_positive"]),
            "pct_negative": r(row["pct_negative"]), "mismatches": int(row["mismatches"] or 0)}


def weekly_trend(db: Session, city=None, platform=None) -> list[dict]:
    where, p = _where(city, platform)
    rows = _rows(db, f"""
        SELECT r.week_start, COUNT(*) AS reviews, AVG(r.rating) AS avg_rating,
               AVG(CASE WHEN r.sentiment_label = 'negative' THEN 1.0 ELSE 0 END) AS pct_negative
        FROM reviews r WHERE {where}
        GROUP BY r.week_start ORDER BY r.week_start""", p)
    return [{"week": str(as_date(x["week_start"])), "reviews": x["reviews"],
             "avg_rating": round(float(x["avg_rating"]), 2),
             "pct_negative": round(float(x["pct_negative"]), 3)} for x in rows]


def topic_breakdown(db: Session, city=None, platform=None) -> list[dict]:
    where, p = _where(city, platform)
    rows = _rows(db, f"""
        SELECT t.topic, COUNT(*) AS mentions,
               SUM(CASE WHEN r.sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative,
               SUM(CASE WHEN r.sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive,
               AVG(r.rating) AS avg_rating
        FROM review_topics t JOIN reviews r ON r.id = t.review_id
        WHERE {where}
        GROUP BY t.topic ORDER BY negative DESC""", p)
    return [{**x, "avg_rating": round(float(x["avg_rating"]), 2),
             "pct_negative": round(x["negative"] / x["mentions"], 3)} for x in rows]


def segment_breakdown(db: Session, column: str, city=None, platform=None) -> list[dict]:
    if column not in {"city", "platform"}:  # whitelist: column names can't be bound parameters
        raise ValueError("invalid segment")
    where, p = _where(city, platform)
    rows = _rows(db, f"""
        SELECT r.{column} AS segment, COUNT(*) AS reviews, AVG(r.rating) AS avg_rating,
               AVG(CASE WHEN r.sentiment_label = 'negative' THEN 1.0 ELSE 0 END) AS pct_negative,
               AVG(CASE WHEN r.rating >= 4 THEN 1.0 ELSE 0 END) AS csat
        FROM reviews r WHERE {where}
        GROUP BY r.{column} ORDER BY reviews DESC""", p)
    return [{"segment": x["segment"], "reviews": x["reviews"],
             "avg_rating": round(float(x["avg_rating"]), 2),
             "pct_negative": round(float(x["pct_negative"]), 3),
             "csat": round(float(x["csat"]), 3)} for x in rows]


def distinct_values(db: Session) -> dict:
    cities = [r[0] for r in db.execute(text("SELECT DISTINCT city FROM reviews ORDER BY city"))]
    platforms = [r[0] for r in db.execute(text("SELECT DISTINCT platform FROM reviews ORDER BY platform"))]
    rng = db.execute(text("SELECT MIN(review_date), MAX(review_date) FROM reviews")).one()
    return {"cities": cities, "platforms": platforms,
            "date_from": str(as_date(rng[0])) if rng[0] else None,
            "date_to": str(as_date(rng[1])) if rng[1] else None}
