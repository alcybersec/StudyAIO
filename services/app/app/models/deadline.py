"""Deadline model — due dates extracted from course documents."""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Deadline(Base):
    """A deadline extracted from a course document (superset of exams)."""

    __tablename__ = "deadlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    assessment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("course_documents.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "exam", "assignment", "quiz", "project", "lab", "presentation", "other"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="deadlines")
    assessment: Mapped["Assessment | None"] = relationship(back_populates="deadlines")
    source_document: Mapped["CourseDocument | None"] = relationship(back_populates="deadlines")

    __table_args__ = (
        Index("ix_deadlines_course", "course_id"),
        Index("ix_deadlines_due_date", "due_date"),
    )
