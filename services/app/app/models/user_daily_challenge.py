"""UserDailyChallenge model — tracks user progress on daily challenges."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class UserDailyChallenge(Base):
    """Tracks a user's progress toward completing a daily challenge."""

    __tablename__ = "user_daily_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    daily_challenge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_challenges.id"), nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "daily_challenge_id", name="uq_user_daily_challenge"),
        Index("ix_user_daily_challenges_user_id", "user_id"),
    )
