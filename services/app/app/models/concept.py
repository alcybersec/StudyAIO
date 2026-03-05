"""Concept model — a knowledge graph node extracted from course content."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class Concept(Base):
    """A concept (knowledge graph node) extracted from course materials."""

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    source_artifact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_weeks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    embedding: Mapped[list | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    outgoing_relations = relationship(
        "ConceptRelation",
        foreign_keys="ConceptRelation.source_concept_id",
        back_populates="source_concept",
        cascade="all, delete-orphan",
    )
    incoming_relations = relationship(
        "ConceptRelation",
        foreign_keys="ConceptRelation.target_concept_id",
        back_populates="target_concept",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "name", name="uq_concept_user_course_name"),
    )
