"""Invite code model for gated registration."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class InviteCode(Base):
    """A registration invite code.

    Gates `POST /api/auth/register` when `REGISTRATION_MODE=invite`. A code is
    spent by incrementing `used_count`, and stays redeemable until it reaches
    `max_uses`, passes `expires_at`, or is revoked.

    `created_by` is nullable and set to NULL when the issuing admin's account is
    deleted — losing the issuer must not invalidate outstanding invites.

    Two flavours share this table:

    * **Shared code** — `code` is handed out and typed in. `email` and
      `token_hash` are NULL. Good for one link in a group chat.
    * **Email invite** — addressed to one person, delivered as a link carrying
      a random token. `code` still exists (every row has one) but the token is
      what the recipient presents.

    Only a SHA-256 hash of the token is stored, exactly as `MagicLink` does: the
    raw token lives solely in the delivery URL. That pattern is not re-derived
    here — `core.auth.hash_magic_link_token` is reused.
    """

    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Set only for email invites. Recorded so the funnel can say WHO was
    # invited, not merely how many uses were issued.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Distinguishes "created" from "actually delivered": with SMTP down an
    # invite exists and its link works, but nothing was sent.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The conversion the funnel could not measure before. used_count says a use
    # was spent; this says when, and with `email` it says by whom.
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_invite_codes_code", "code", unique=True),
        # Unique so a token can never collide; partial-free because NULLs do not
        # conflict in Postgres, so every shared code coexists happily.
        Index("ix_invite_codes_token_hash", "token_hash", unique=True),
        Index("ix_invite_codes_email", "email"),
    )

    @property
    def is_email_invite(self) -> bool:
        """Whether this invite was addressed to one person by email."""
        return self.token_hash is not None

    @property
    def uses_remaining(self) -> int:
        """How many more times this code can be redeemed."""
        return max(0, self.max_uses - self.used_count)

    def is_redeemable(self, now: datetime | None = None) -> bool:
        """Whether this code can still be used.

        Args:
            now: Current time; defaults to `datetime.now(UTC)`.

        Returns:
            True if not revoked, not expired, and uses remain.
        """
        now = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return self.used_count < self.max_uses
