"""Exam model."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Exam(Base):
    """An upcoming exam for a course, scoping study plans and progress tracking."""

    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[datetime] = mapped_column(nullable=False)
    weeks_scope: Mapped[list] = mapped_column(JSONB, nullable=False)
    target_mastery_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="exams")
    course: Mapped["Course"] = relationship(back_populates="exams")
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="exam")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="exam")

    __table_args__ = (
        Index("ix_exams_user_id", "user_id"),
        Index("ix_exams_course_status", "course_id", "status"),
        Index("ix_exams_exam_date", "exam_date"),
    )
