"""Stripe webhook dedupe and ordering state."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class StripeWebhookEvent(Base):
    """One processed Stripe webhook event.

    Replaces the Redis dedupe and ordering keys: the unique `stripe_event_id`
    is the claim, and `(stripe_customer_id, stripe_created)` is the ordering
    watermark read. Holds Stripe's ids and our decision only: no user id, no
    payload, no email. Rows are kept indefinitely. `stripe_customer_id` is
    nulled (never the row deleted) on account deletion.
    """

    __tablename__ = "stripe_webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # applied | stale
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_stripe_webhook_events_customer_created", "stripe_customer_id", "stripe_created"),
    )
