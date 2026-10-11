"""Append-only product usage events (retention cohorts)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class UsageEvent(Base):
    """One thing a user did, for D7/D30 retention and funnel queries.

    Append-only: rows are inserted and never updated, so there is no
    `updated_at`. Distinct from `UsageRecord` (daily quota counters).

    `event` is a short name such as `summary_viewed`, `quiz_started`,
    `quiz_completed`, `flashcard_reviewed`, `chat_message_sent`,
    `upload_completed`, `study_plan_viewed`; the set is validated in the
    service layer.

    `properties` must stay small and must never hold content or PII: no
    lecture text, prompts, answers, file names, emails or free text. Ids,
    counts, durations and enum-like labels only.

    User-scoped via a non-nullable `user_id`, so it is removed on account
    deletion.
    """

    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    course_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_usage_events_event_occurred", "event", "occurred_at"),
        Index("ix_usage_events_user_occurred", "user_id", "occurred_at"),
    )
