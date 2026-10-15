"""Add weak-spot engine storage (ADR 0007 Decision 6).

* `study_plans`: one persisted plan per user per user-local day.
* `targeted_generations`: on-demand quiz/flashcard generation requests, with a
  partial unique index so only one request per (user, course, week, kind) can
  be queued or running, and an index on (user_id, created_at) for the daily cap.
* `quiz_questions` / `flashcards`: `origin` (server default 'pipeline', so
  existing rows backfill without a data pass), `targeted_generation_id`,
  `focus_topic`.
* `quiz_attempts (quiz_question_id, created_at)` index for the scoring query.

Revision ID: f7c3a9d15e24
Revises: e5b7d2c94a08
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7c3a9d15e24"
down_revision: str | None = "e5b7d2c94a08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ITEM_TABLES = ("quiz_questions", "flashcards")


def upgrade() -> None:
    op.create_table(
        "study_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("focus", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("algorithm_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "plan_date", name="uq_study_plans_user_date"),
    )
    op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])

    op.create_table(
        "targeted_generations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dropped_duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dropped_uncited_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_targeted_generations_user_created",
        "targeted_generations",
        ["user_id", "created_at"],
    )
    op.create_index(
        "uq_targeted_generations_in_flight",
        "targeted_generations",
        ["user_id", "course_id", "week", "kind"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    for table in _ITEM_TABLES:
        op.add_column(
            table,
            sa.Column("origin", sa.String(length=20), server_default="pipeline", nullable=False),
        )
        op.add_column(
            table, sa.Column("targeted_generation_id", sa.String(length=36), nullable=True)
        )
        op.add_column(table, sa.Column("focus_topic", sa.String(length=200), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_targeted_generation_id",
            table,
            "targeted_generations",
            ["targeted_generation_id"],
            ["id"],
        )

    op.create_index(
        "ix_quiz_attempts_question_created",
        "quiz_attempts",
        ["quiz_question_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_question_created", table_name="quiz_attempts")

    for table in reversed(_ITEM_TABLES):
        op.drop_constraint(f"fk_{table}_targeted_generation_id", table, type_="foreignkey")
        op.drop_column(table, "focus_topic")
        op.drop_column(table, "targeted_generation_id")
        op.drop_column(table, "origin")

    op.drop_index("uq_targeted_generations_in_flight", table_name="targeted_generations")
    op.drop_index("ix_targeted_generations_user_created", table_name="targeted_generations")
    op.drop_table("targeted_generations")

    op.drop_index("ix_study_plans_user_id", table_name="study_plans")
    op.drop_table("study_plans")
