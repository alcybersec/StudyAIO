"""CalendarEvent model — mapping between StudyAIO entities and Google Calendar events."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class CalendarEvent(Base):
    """Maps a StudyAIO entity (deadline/exam) to a Google Calendar event."""

    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    calendar_sync_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_syncs.id", ondelete="CASCADE"), nullable=False
    )
    google_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "deadline", "exam", "class_schedule"
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_synced_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    calendar_sync: Mapped["CalendarSync"] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint(
            "calendar_sync_id", "google_event_id",
            name="uq_calendar_events_sync_google_event",
        ),
        Index("ix_calendar_events_user_id", "user_id"),
        Index("ix_calendar_events_entity", "entity_type", "entity_id"),
    )
