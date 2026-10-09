"""Add user_settings.timezone

Revision ID: a5c9e3d71b04
Revises: f4b8d2a60c19
Create Date: 2026-10-09

Per-user IANA time zone (R-023, decisions.md 2026-10-09 clock policy).
Additive; existing rows get 'UTC'. The zone name is validated in the
service layer, not by a DB constraint.
"""

import sqlalchemy as sa
from alembic import op

revision = "a5c9e3d71b04"
down_revision = "f4b8d2a60c19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the NOT NULL timezone column defaulting to UTC."""
    op.add_column(
        "user_settings",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    """Drop the timezone column."""
    op.drop_column("user_settings", "timezone")
