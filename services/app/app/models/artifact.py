"""LectureArtifact model."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class LectureArtifact(Base):
    """An uploaded lecture file (PDF, DOCX, PPTX)."""

    __tablename__ = "lecture_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=True
    )
    week: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ingested")
    pipeline_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pipeline_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="artifacts")
    course: Mapped["Course | None"] = relationship(back_populates="artifacts")
    extraction: Mapped["Extraction | None"] = relationship(back_populates="artifact", uselist=False)
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="artifact")
    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="source_artifact")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="source_artifact")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="artifact")

    __table_args__ = (
        UniqueConstraint("sha256", "user_id", name="uq_artifacts_sha256_user"),
        Index("ix_lecture_artifacts_sha256", "sha256"),
        Index("ix_lecture_artifacts_user_id", "user_id"),
        Index("ix_lecture_artifacts_course_id", "course_id"),
        Index("ix_lecture_artifacts_status", "status"),
    )
