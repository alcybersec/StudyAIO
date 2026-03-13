"""Flashcard model."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Flashcard(Base):
    """A study flashcard generated from lecture content."""

    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    source_artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lecture_artifacts.id"), nullable=False
    )
    source_page_ref: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="flashcards")
    source_artifact: Mapped["LectureArtifact"] = relationship(back_populates="flashcards")
    review: Mapped["FlashcardReview | None"] = relationship(
        back_populates="flashcard", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_flashcards_course_week", "course_id", "week"),)
