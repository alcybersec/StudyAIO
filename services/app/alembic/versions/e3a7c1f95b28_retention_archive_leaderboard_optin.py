"""Retain summary versions, soft-retire assets, leaderboard opt-in

Revision ID: e3a7c1f95b28
Revises: d2c5b81a4f37
Create Date: 2026-10-04

Three user rulings (docs/decisions.md, 2026-10-04), all purely additive:

* ``summary_versions`` -- append-only history of superseded summaries.
* ``flashcards.archived_at`` / ``quiz_questions.archived_at`` -- regeneration
  retires rows instead of deleting them, so reviews/attempts survive.
* ``user_settings.leaderboard_opt_in`` -- false by default (hidden).

No data is deleted or rewritten by upgrade; existing flashcards and questions
stay active (NULL), existing users stay hidden.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3a7c1f95b28"
down_revision = "d2c5b81a4f37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create summary_versions and add the archive / opt-in columns."""
    op.create_table(
        "summary_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("source_artifacts", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "course_id", "week", "version", name="uq_summary_versions_course_week_ver"
        ),
    )
    op.create_index("ix_summary_versions_user_id", "summary_versions", ["user_id"])
    op.create_index("ix_summary_versions_course_week", "summary_versions", ["course_id", "week"])

    for table in ("flashcards", "quiz_questions"):
        op.add_column(table, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(
            f"ix_{table}_active",
            table,
            ["course_id", "week"],
            postgresql_where=sa.text("archived_at IS NULL"),
        )

    op.add_column(
        "user_settings",
        sa.Column("leaderboard_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Reverse the additions.

    Dropping ``summary_versions`` discards retained prior versions, and dropping
    ``archived_at`` makes retired cards/questions indistinguishable from active
    ones (they reappear in study sessions). The card/question rows are kept.
    """
    op.drop_column("user_settings", "leaderboard_opt_in")
    for table in ("quiz_questions", "flashcards"):
        op.drop_index(f"ix_{table}_active", table_name=table)
        op.drop_column(table, "archived_at")
    op.drop_index("ix_summary_versions_course_week", table_name="summary_versions")
    op.drop_index("ix_summary_versions_user_id", table_name="summary_versions")
    op.drop_table("summary_versions")
