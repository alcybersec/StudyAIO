"""DailyChallenge model — one challenge per day."""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class DailyChallenge(Base):
    """A daily challenge with a type, target, and XP reward."""

    __tablename__ = "daily_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    challenge_date: Mapped[date] = mapped_column(Date, nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (UniqueConstraint("challenge_date", name="uq_daily_challenge_date"),)
