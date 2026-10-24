"""ORM models. One review can mention many topics -> one-to-many table (normalised design)."""
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    review_date: Mapped[date] = mapped_column(Date, index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)  # Monday of that week, for trends
    city: Mapped[str] = mapped_column(String(64), index=True, default="Unknown")
    platform: Mapped[str] = mapped_column(String(32), index=True, default="Unknown")
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    sentiment_score: Mapped[float] = mapped_column(Float)
    sentiment_label: Mapped[str] = mapped_column(String(16), index=True)
    mismatch: Mapped[bool] = mapped_column(Boolean, default=False)  # stars disagree with words
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    topics: Mapped[list["ReviewTopic"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin")


class ReviewTopic(Base):
    __tablename__ = "review_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(32), index=True)

    review: Mapped[Review] = relationship(back_populates="topics")
