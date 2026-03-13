"""Extraction model."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Extraction(Base):
    """Extracted content from a lecture artifact (text + images per page)."""

    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lecture_artifacts.id"), unique=True, nullable=False
    )
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    artifact: Mapped["LectureArtifact"] = relationship(back_populates="extraction")
