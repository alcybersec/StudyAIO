"""TargetedGeneration model: one on-demand quiz/flashcard generation request."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class TargetedGeneration(Base):
    """A weak-spot targeted generation request and its outcome counts (ADR 0007)."""

    __tablename__ = "targeted_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ``quiz`` | ``flashcards``.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    #: ``queued`` | ``running`` | ``completed`` | ``failed``.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    dropped_duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    dropped_uncited_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    #: Topic labels only.
    topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    #: Short machine code; never provider text.
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_targeted_generations_user_created", "user_id", "created_at"),
        Index(
            "uq_targeted_generations_in_flight",
            "user_id",
            "course_id",
            "week",
            "kind",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
