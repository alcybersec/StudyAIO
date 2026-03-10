"""Add gamification tables (user_xp, xp_events, achievements, user_achievements, daily_challenges, user_daily_challenges).

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-03-05 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "i0j1k2l3m4n5"
down_revision: str | None = "h9i0j1k2l3m4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- user_xp --
    op.create_table(
        "user_xp",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("total_xp", sa.Integer, nullable=False, server_default="0"),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint("uq_user_xp_user_id", "user_xp", ["user_id"])
    op.create_index("ix_user_xp_total_xp", "user_xp", ["total_xp"])

    # -- xp_events --
    op.create_table(
        "xp_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("xp_amount", sa.Integer, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_xp_events_user_id", "xp_events", ["user_id"])
    op.create_index("ix_xp_events_event_type", "xp_events", ["event_type"])
    op.create_index("ix_xp_events_created_at", "xp_events", ["created_at"])

    # -- achievements --
    op.create_table(
        "achievements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False, server_default="star"),
        sa.Column("category", sa.String(50), nullable=False, server_default="milestone"),
        sa.Column("xp_reward", sa.Integer, nullable=False, server_default="0"),
        sa.Column("criteria_json", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- user_achievements --
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "achievement_id",
            sa.String(36),
            sa.ForeignKey("achievements.id"),
            nullable=False,
        ),
        sa.Column(
            "earned_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("notified", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_unique_constraint(
        "uq_user_achievement", "user_achievements", ["user_id", "achievement_id"]
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])

    # -- daily_challenges --
    op.create_table(
        "daily_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("challenge_date", sa.Date, nullable=False),
        sa.Column("challenge_type", sa.String(50), nullable=False),
        sa.Column("target", sa.Integer, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("xp_reward", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint("uq_daily_challenge_date", "daily_challenges", ["challenge_date"])

    # -- user_daily_challenges --
    op.create_table(
        "user_daily_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "daily_challenge_id",
            sa.String(36),
            sa.ForeignKey("daily_challenges.id"),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint(
        "uq_user_daily_challenge", "user_daily_challenges", ["user_id", "daily_challenge_id"]
    )
    op.create_index("ix_user_daily_challenges_user_id", "user_daily_challenges", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_daily_challenges_user_id", table_name="user_daily_challenges")
    op.drop_constraint("uq_user_daily_challenge", "user_daily_challenges", type_="unique")
    op.drop_table("user_daily_challenges")

    op.drop_constraint("uq_daily_challenge_date", "daily_challenges", type_="unique")
    op.drop_table("daily_challenges")

    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_constraint("uq_user_achievement", "user_achievements", type_="unique")
    op.drop_table("user_achievements")

    op.drop_table("achievements")

    op.drop_index("ix_xp_events_created_at", table_name="xp_events")
    op.drop_index("ix_xp_events_event_type", table_name="xp_events")
    op.drop_index("ix_xp_events_user_id", table_name="xp_events")
    op.drop_table("xp_events")

    op.drop_index("ix_user_xp_total_xp", table_name="user_xp")
    op.drop_constraint("uq_user_xp_user_id", "user_xp", type_="unique")
    op.drop_table("user_xp")
