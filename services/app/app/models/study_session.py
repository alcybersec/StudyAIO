"""StudySession model."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class StudySession(Base):
    """Records a completed study session with aggregated stats."""

    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    exam_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("exams.id", ondelete="SET NULL"),
        nullable=True,
    )
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=False
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    cards_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="study_sessions")
    exam: Mapped["Exam | None"] = relationship(back_populates="study_sessions")
    course: Mapped["Course"] = relationship(back_populates="study_sessions")

    __table_args__ = (
        Index("ix_study_sessions_user_id", "user_id"),
        Index("ix_study_sessions_date", "session_date"),
        Index("ix_study_sessions_exam", "exam_id"),
    )
