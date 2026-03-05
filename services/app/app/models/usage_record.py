"""UsageRecord model for tracking daily resource consumption."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class UsageRecord(Base):
    """Tracks daily usage metrics per user for quota enforcement."""

    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    ai_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploads_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_usage_user_date"),
        Index("ix_usage_records_user_id", "user_id"),
        Index("ix_usage_records_date", "record_date"),
    )
