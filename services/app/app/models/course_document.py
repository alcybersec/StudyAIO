"""CourseDocument model — uploaded course outlines, rubrics, etc."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class CourseDocument(Base):
    """A course document (outline, rubric, handbook) uploaded for CourseOps extraction."""

    __tablename__ = "course_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "outline", "rubric", "handbook", "other"
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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="course_documents")
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="source_document"
    )
    deadlines: Mapped[list["Deadline"]] = relationship(back_populates="source_document")

    __table_args__ = (
        Index("ix_course_documents_course", "course_id"),
        Index("ix_course_documents_sha256", "sha256"),
    )
