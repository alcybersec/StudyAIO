"""Per-item thumbs up/down on AI output."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id

#: What can be rated. Validated in the service layer; stored as plain strings
#: so adding a target is not a migration.
AI_FEEDBACK_TARGET_TYPES = ("summary", "answer", "flashcard", "quiz_question", "chat_message")

#: Fixed reasons offered with a thumbs-down.
AI_FEEDBACK_REASONS = ("inaccurate", "not_in_my_lectures", "unclear", "wrong_format", "other")


class AIFeedback(Base):
    """One user's latest rating of one piece of AI output.

    Unique on `(user_id, target_type, target_id)`: voting again replaces the
    earlier vote (upsert), so the table holds the current opinion, not a log.
    `target_id` is polymorphic across `target_type`, so it carries no FK.
    `rating` is +1 or -1 (range enforced in the service layer). `comment` is
    free text the user wrote; its length cap is also a service concern.

    Distinct from `Feedback`, which is a bug/idea report about the app itself.
    User-scoped via a non-nullable `user_id`, so it is removed on account
    deletion.
    """

    __tablename__ = "ai_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_ai_feedback_user_target"),
        Index("ix_ai_feedback_user_id", "user_id"),
        Index("ix_ai_feedback_course_id", "course_id"),
    )
