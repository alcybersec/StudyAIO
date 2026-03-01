"""Course model."""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Course(Base):
    """A university course (e.g., CSIT302)."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    term: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    artifacts: Mapped[list["LectureArtifact"]] = relationship(back_populates="course")
    summaries: Mapped[list["Summary"]] = relationship(back_populates="course")
    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="course")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="course")
