"""Add pg_trgm extension and trigram indexes for global search.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-07-04 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r8s9t0u1v2w3"
down_revision: str | None = "q7r8s9t0u1v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_courses_code_trgm "
        "ON courses USING gin (code gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_courses_name_trgm "
        "ON courses USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_summaries_content_md_trgm "
        "ON summaries USING gin (content_md gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_flashcards_front_trgm "
        "ON flashcards USING gin (front gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_title_trgm "
        "ON chat_sessions USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_sessions_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_flashcards_front_trgm")
    op.execute("DROP INDEX IF EXISTS ix_summaries_content_md_trgm")
    op.execute("DROP INDEX IF EXISTS ix_courses_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_courses_code_trgm")
