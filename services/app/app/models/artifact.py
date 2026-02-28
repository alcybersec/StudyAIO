"""LectureArtifact model."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class LectureArtifact(Base):
    """An uploaded lecture file (PDF, DOCX, PPTX)."""

    __tablename__ = "lecture_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    course_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=True
    )
    week: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ingested")
    pipeline_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    pipeline_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    course: Mapped["Course | None"] = relationship(back_populates="artifacts")
    extraction: Mapped["Extraction | None"] = relationship(
        back_populates="artifact", uselist=False
    )
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="artifact")
    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="source_artifact")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="source_artifact"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="artifact")

    __table_args__ = (
        Index("ix_lecture_artifacts_sha256", "sha256", unique=True),
        Index("ix_lecture_artifacts_course_id", "course_id"),
        Index("ix_lecture_artifacts_status", "status"),
    )
