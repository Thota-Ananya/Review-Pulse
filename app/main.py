"""ReviewPulse API + dashboard. Run:  uvicorn app.main:app --reload"""
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import analytics, insights
from .database import Base, SessionLocal, engine, get_db
from .ingest import IngestError, ingest_csv
from .models import Review, ReviewTopic
from .nlp import TOPICS

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
SAMPLE_CSV = ROOT / "data" / "sample_reviews.csv"
MAX_UPLOAD_MB = 10


def seed_if_empty() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count(Review.id))) == 0 and SAMPLE_CSV.exists():
            ingest_csv(db, SAMPLE_CSV)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("SEED_ON_START", "true").lower() == "true":
        seed_if_empty()
    yield


app = FastAPI(title="ReviewPulse", version="1.0.0", lifespan=lifespan,
              description="Customer feedback analytics: sentiment, topics, trends and insights.")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "reviews": db.scalar(select(func.count(Review.id)))}


@app.get("/api/filters")
def filters(db: Session = Depends(get_db)):
    return {**analytics.distinct_values(db), "topics": TOPICS}


@app.get("/api/dashboard")
def dashboard(city: str | None = None, platform: str | None = None, db: Session = Depends(get_db)):
    """Everything the dashboard needs in one round-trip."""
    return {
        "kpis": analytics.kpis(db, city, platform),
        "trend": analytics.weekly_trend(db, city, platform),
        "topics": analytics.topic_breakdown(db, city, platform),
        "cities": analytics.segment_breakdown(db, "city", city, platform),
        "platforms": analytics.segment_breakdown(db, "platform", city, platform),
    }


@app.get("/api/insights")
def get_insights(db: Session = Depends(get_db)):
    return {"insights": insights.generate_insights(db)}


@app.get("/api/summary")
def get_summary(db: Session = Depends(get_db)):
    return insights.llm_summary(insights.generate_insights(db))


def _review_query(topic, sentiment, city, platform, q, mismatch):
    stmt = select(Review)
    if topic:
        stmt = stmt.where(Review.id.in_(select(ReviewTopic.review_id).where(ReviewTopic.topic == topic)))
    if sentiment:
        stmt = stmt.where(Review.sentiment_label == sentiment)
    if city:
        stmt = stmt.where(Review.city == city)
    if platform:
        stmt = stmt.where(Review.platform == platform)
    if q:
        stmt = stmt.where(or_(Review.text.ilike(f"%{q}%"), Review.source_id.ilike(f"%{q}%")))
    if mismatch:
        stmt = stmt.where(Review.mismatch.is_(True))
    return stmt


def _serialise(r: Review) -> dict:
    return {"id": r.id, "source_id": r.source_id, "date": str(r.review_date), "city": r.city,
            "platform": r.platform, "rating": r.rating, "text": r.text,
            "sentiment": r.sentiment_label, "score": r.sentiment_score,
            "mismatch": r.mismatch, "topics": [t.topic for t in r.topics]}


@app.get("/api/reviews")
def list_reviews(topic: str | None = None, sentiment: str | None = Query(None, pattern="^(positive|negative|neutral)$"),
                 city: str | None = None, platform: str | None = None, q: str | None = Query(None, max_length=100),
                 mismatch: bool = False, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db)):
    stmt = _review_query(topic, sentiment, city, platform, q, mismatch)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Review.review_date.desc(), Review.id.desc())
                      .offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [_serialise(r) for r in rows]}


@app.get("/api/export.csv")
def export_csv(topic: str | None = None, sentiment: str | None = None, city: str | None = None,
               platform: str | None = None, q: str | None = None, mismatch: bool = False,
               db: Session = Depends(get_db)):
    stmt = _review_query(topic, sentiment, city, platform, q, mismatch).order_by(Review.review_date)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["review_id", "date", "city", "platform", "rating", "sentiment", "sentiment_score",
                "topics", "stars_text_mismatch", "review_text"])
    for r in db.scalars(stmt):
        w.writerow([r.source_id, r.review_date, r.city, r.platform, r.rating, r.sentiment_label,
                    r.sentiment_score, "; ".join(t.topic for t in r.topics), r.mismatch, r.text])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=reviewpulse_export.csv"})


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), replace: bool = False, db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB).")
    if replace:
        db.query(ReviewTopic).delete()
        db.query(Review).delete()
        db.commit()
    try:
        return ingest_csv(db, io.BytesIO(data))
    except IngestError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/reset-demo")
def reset_demo(db: Session = Depends(get_db)):
    """Wipe the database and reload the bundled sample dataset."""
    db.query(ReviewTopic).delete()
    db.query(Review).delete()
    db.commit()
    return ingest_csv(db, SAMPLE_CSV)
