"""Add calendar_syncs and calendar_events tables for Google Calendar sync.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-06 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "o5p6q7r8s9t0"
down_revision: str | None = "n4o5p6q7r8s9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_syncs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("google_calendar_id", sa.String(255), nullable=False),
        sa.Column("sync_direction", sa.String(20), nullable=False, server_default="push"),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("sync_token", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_syncs_user_id", "calendar_syncs", ["user_id"])

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "calendar_sync_id",
            sa.String(36),
            sa.ForeignKey("calendar_syncs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("google_event_id", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("last_synced_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"])
    op.create_index("ix_calendar_events_entity", "calendar_events", ["entity_type", "entity_id"])
    op.create_unique_constraint(
        "uq_calendar_events_sync_google_event",
        "calendar_events",
        ["calendar_sync_id", "google_event_id"],
    )


def downgrade() -> None:
    op.drop_table("calendar_events")
    op.drop_table("calendar_syncs")
