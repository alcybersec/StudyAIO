"""CalendarSync model — Google Calendar integration connections."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class CalendarSync(Base):
    """A user's connection to a Google Calendar for bidirectional sync."""

    __tablename__ = "calendar_syncs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    google_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sync_direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="push"
    )  # "push", "pull", "bidirectional"
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sync_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="calendar_sync", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_calendar_syncs_user_id", "user_id"),)
