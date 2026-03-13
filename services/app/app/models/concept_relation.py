"""ConceptRelation model — an edge in the knowledge graph."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class ConceptRelation(Base):
    """A directed relationship between two concepts."""

    __tablename__ = "concept_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    source_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    source_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lecture_artifacts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    source_concept = relationship(
        "Concept",
        foreign_keys=[source_concept_id],
        back_populates="outgoing_relations",
    )
    target_concept = relationship(
        "Concept",
        foreign_keys=[target_concept_id],
        back_populates="incoming_relations",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_concept_id",
            "target_concept_id",
            "relation_type",
            name="uq_concept_relation",
        ),
    )
