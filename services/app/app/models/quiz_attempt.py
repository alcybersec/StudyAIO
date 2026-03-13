"""QuizAttempt model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class QuizAttempt(Base):
    """Records a single answer to a quiz question."""

    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    quiz_question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    exam_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("exams.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    quiz_question: Mapped["QuizQuestion"] = relationship(back_populates="attempts")
    exam: Mapped["Exam | None"] = relationship(back_populates="quiz_attempts")

    __table_args__ = (
        Index("ix_quiz_attempts_question", "quiz_question_id"),
        Index("ix_quiz_attempts_exam", "exam_id"),
        Index("ix_quiz_attempts_created", "created_at"),
    )
