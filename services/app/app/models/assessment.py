"""Assessment model — course assessments extracted from course documents."""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Assessment(Base):
    """An assessment item (assignment, exam, quiz, project) extracted from a course document."""

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("course_documents.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "exam", "assignment", "quiz", "project", "lab", "presentation", "other"
    weight_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weeks_relevant: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="assessments")
    source_document: Mapped["CourseDocument | None"] = relationship(back_populates="assessments")
    deadlines: Mapped[list["Deadline"]] = relationship(back_populates="assessment")

    __table_args__ = (Index("ix_assessments_course", "course_id"),)
