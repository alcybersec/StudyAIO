"""CourseDocument model — uploaded course outlines, rubrics, etc."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class CourseDocument(Base):
    """A course document (outline, rubric, handbook) uploaded for CourseOps extraction."""

    __tablename__ = "course_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    # Set when the document is attached to a specific assessment (brief, rubric,
    # guideline, …) rather than being a course-level outline to extract from.
    assessment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "outline", "rubric", "handbook", "brief", "guideline", "other"
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "pdf", "docx"
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # "pending", "processing", "processed", "failed"
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="course_documents")
    course: Mapped["Course"] = relationship(back_populates="course_documents")
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="source_document", foreign_keys="Assessment.source_document_id"
    )
    deadlines: Mapped[list["Deadline"]] = relationship(back_populates="source_document")
    assessment: Mapped["Assessment | None"] = relationship(
        foreign_keys=[assessment_id], viewonly=True
    )

    __table_args__ = (
        Index("ix_course_documents_user_id", "user_id"),
        Index("ix_course_documents_course", "course_id"),
        Index("ix_course_documents_sha256", "sha256"),
    )
