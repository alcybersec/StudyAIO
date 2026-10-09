"""Add chat_messages.action_json

Revision ID: f4b8d2a60c19
Revises: e3a7c1f95b28
Create Date: 2026-10-09

Persists the chat quiz-builder action (GL#10, decisions.md 2026-10-09).
Shape: {"type": "open_quiz_builder", "course_code": str|null,
"course_id": str|null, "week": int|null}, or NULL. Additive and nullable;
no existing rows are rewritten.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4b8d2a60c19"
down_revision = "e3a7c1f95b28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the nullable action_json column."""
    op.add_column(
        "chat_messages",
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Drop the action_json column."""
    op.drop_column("chat_messages", "action_json")
