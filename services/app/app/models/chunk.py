"""Chunk model with pgvector embedding."""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Chunk(Base):
    """A text chunk from a lecture artifact, with optional embedding."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lecture_artifacts.id"), nullable=False
    )
    stable_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_ref: Mapped[int] = mapped_column(Integer, nullable=False)
    slide_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    artifact: Mapped["LectureArtifact"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_stable_id", "stable_id", unique=True),
        Index("ix_chunks_artifact_id", "artifact_id"),
    )
