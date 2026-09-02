"""Magic link model for passwordless auth and password resets."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class MagicLink(Base):
    """A one-time-use token for passwordless login or password reset.

    Only a SHA-256 hash of the token is stored (`token_hash`); the raw token
    lives solely in the delivery URL. Lookups hash the presented token and
    match on `token_hash`.
    """

    __tablename__ = "magic_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    link_type: Mapped[str] = mapped_column(String(30), nullable=False, default="password_reset")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="magic_links")

    __table_args__ = (
        Index("ix_magic_links_token_hash", "token_hash", unique=True),
        Index("ix_magic_links_user_id", "user_id"),
    )
