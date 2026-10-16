"""Add stripe_webhook_events and users.onboarding_checklist.

M34-S2-SEC-008: Stripe webhook dedupe and ordering state moves from Redis to
Postgres. The table holds Stripe's ids and our decision only (no user id, no
payload). M34-S3-BACKEND-012: the stored first-run checklist state; the server
default backfills existing users to 'auto'.

Revision ID: a1c2d3e4f5a6
Revises: f7c3a9d15e24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2d3e4f5a6"
down_revision: str | None = "f7c3a9d15e24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("stripe_event_id", name="uq_stripe_webhook_events_stripe_event_id"),
    )
    op.create_index(
        "ix_stripe_webhook_events_customer_created",
        "stripe_webhook_events",
        ["stripe_customer_id", "stripe_created"],
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_checklist",
            sa.String(20),
            nullable=False,
            server_default="auto",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_checklist")
    op.drop_index("ix_stripe_webhook_events_customer_created", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
