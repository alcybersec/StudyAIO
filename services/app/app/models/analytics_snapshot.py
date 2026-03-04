"""AnalyticsSnapshot model — stores nightly metrics rollups."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class AnalyticsSnapshot(Base):
    """Stores daily analytics snapshots for each user."""

    __tablename__ = "analytics_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_analytics_snapshot_user_date"),
        Index("ix_analytics_snapshots_user_id", "user_id"),
    )
