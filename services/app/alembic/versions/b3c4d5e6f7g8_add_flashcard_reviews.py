"""Add flashcard_reviews table for spaced repetition.

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7g8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flashcard_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "flashcard_id",
            sa.String(36),
            sa.ForeignKey("flashcards.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ease_factor", sa.Float, nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("repetition_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime, nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_flashcard_reviews_next_review", "flashcard_reviews", ["next_review_at"])


def downgrade() -> None:
    op.drop_index("ix_flashcard_reviews_next_review", table_name="flashcard_reviews")
    op.drop_table("flashcard_reviews")
