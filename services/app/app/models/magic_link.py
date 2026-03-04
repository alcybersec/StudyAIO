"""Magic link model for passwordless auth and password resets."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class MagicLink(Base):
    """A one-time-use token for passwordless login or password reset."""

    __tablename__ = "magic_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    link_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="password_reset"
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="magic_links")

    __table_args__ = (
        Index("ix_magic_links_token", "token", unique=True),
        Index("ix_magic_links_user_id", "user_id"),
    )
