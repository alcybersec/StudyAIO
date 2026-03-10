"""UserSettings model — per-user configuration stored in DB."""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class UserSettings(Base):
    """Per-user application settings, stored as JSONB for flexibility."""

    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dashboard_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="settings")
