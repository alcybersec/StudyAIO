"""Add ai_feedback, usage_events and AI-processing consent columns.

* `ai_feedback`: a user's latest thumbs up/down on one piece of AI output,
  unique per (user, target_type, target_id) so a re-vote replaces the old one.
* `usage_events`: append-only product events for D7/D30 retention queries.
  `properties` carries ids/counts only, never content or PII.
* `users.ai_processing_consent_at` / `ai_processing_consent_version`: when and
  to which wording the user consented to AI processing of their material.
  Existing users stay NULL (not consented).

`course_id` is SET NULL on course delete so the signal survives the course.

Revision ID: e5b7d2c94a08
Revises: c8e2a5f93d16
Create Date: 2026-10-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5b7d2c94a08"
down_revision: str | None = "c8e2a5f93d16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("course_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_ai_feedback_user_target"
        ),
    )
    op.create_index("ix_ai_feedback_user_id", "ai_feedback", ["user_id"])
    op.create_index("ix_ai_feedback_course_id", "ai_feedback", ["course_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event", sa.String(length=50), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("course_id", sa.String(length=36), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_events_event_occurred", "usage_events", ["event", "occurred_at"])
    op.create_index("ix_usage_events_user_occurred", "usage_events", ["user_id", "occurred_at"])

    op.add_column(
        "users",
        sa.Column("ai_processing_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("ai_processing_consent_version", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "ai_processing_consent_version")
    op.drop_column("users", "ai_processing_consent_at")
    op.drop_index("ix_usage_events_user_occurred", table_name="usage_events")
    op.drop_index("ix_usage_events_event_occurred", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_ai_feedback_course_id", table_name="ai_feedback")
    op.drop_index("ix_ai_feedback_user_id", table_name="ai_feedback")
    op.drop_table("ai_feedback")
