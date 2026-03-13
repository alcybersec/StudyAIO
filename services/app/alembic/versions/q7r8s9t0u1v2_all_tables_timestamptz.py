"""Alter all remaining datetime columns to timestamptz.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-03-13 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q7r8s9t0u1v2"
down_revision: str | None = "p6q7r8s9t0u1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, nullable)
COLUMNS = [
    ("achievements", "created_at", False),
    ("analytics_snapshots", "created_at", False),
    ("assessments", "created_at", False),
    ("assessments", "updated_at", False),
    ("calendar_events", "created_at", False),
    ("calendar_syncs", "last_synced_at", True),
    ("calendar_syncs", "created_at", False),
    ("calendar_syncs", "updated_at", False),
    ("chat_messages", "created_at", False),
    ("chat_sessions", "created_at", False),
    ("chat_sessions", "updated_at", False),
    ("chunks", "created_at", False),
    ("concept_relations", "created_at", False),
    ("concepts", "created_at", False),
    ("concepts", "updated_at", False),
    ("course_documents", "created_at", False),
    ("course_documents", "updated_at", False),
    ("courses", "created_at", False),
    ("courses", "updated_at", False),
    ("daily_challenges", "created_at", False),
    ("deadlines", "created_at", False),
    ("deadlines", "updated_at", False),
    ("exams", "exam_date", False),
    ("exams", "created_at", False),
    ("exams", "updated_at", False),
    ("extractions", "created_at", False),
    ("flashcard_reviews", "next_review_at", False),
    ("flashcard_reviews", "last_reviewed_at", True),
    ("flashcard_reviews", "created_at", False),
    ("flashcard_reviews", "updated_at", False),
    ("flashcards", "created_at", False),
    ("lecture_artifacts", "pipeline_started_at", True),
    ("lecture_artifacts", "pipeline_completed_at", True),
    ("lecture_artifacts", "created_at", False),
    ("lecture_artifacts", "updated_at", False),
    ("notification_preferences", "created_at", False),
    ("notification_preferences", "updated_at", False),
    ("oauth_accounts", "created_at", False),
    ("pipeline_runs", "started_at", False),
    ("pipeline_runs", "completed_at", True),
    ("push_subscriptions", "created_at", False),
    ("push_subscriptions", "updated_at", False),
    ("quiz_attempts", "created_at", False),
    ("quiz_questions", "created_at", False),
    ("review_items", "created_at", False),
    ("review_items", "resolved_at", True),
    ("study_sessions", "created_at", False),
    ("subscriptions", "current_period_start", True),
    ("subscriptions", "current_period_end", True),
    ("subscriptions", "created_at", False),
    ("subscriptions", "updated_at", False),
    ("summaries", "created_at", False),
    ("summaries", "updated_at", False),
    ("telegram_links", "created_at", False),
    ("telegram_links", "updated_at", False),
    ("usage_records", "created_at", False),
    ("usage_records", "updated_at", False),
    ("user_achievements", "earned_at", False),
    ("user_daily_challenges", "completed_at", True),
    ("user_daily_challenges", "created_at", False),
    ("user_settings", "created_at", False),
    ("user_settings", "updated_at", False),
    ("user_xp", "created_at", False),
    ("user_xp", "updated_at", False),
    ("xp_events", "created_at", False),
]


def upgrade() -> None:
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, column, nullable in reversed(COLUMNS):
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=nullable,
        )
