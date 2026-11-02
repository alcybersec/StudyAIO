"""Add user_id to review_items and quiz_attempts.

R-010: both tables were owner-scoped only through joins (review_items through the
polymorphic entity_type/entity_id pair, quiz_attempts through quiz_questions ->
courses). Each now carries its own ``user_id`` FK to ``users.id`` (ON DELETE
CASCADE, indexed).

Backfill, from the row each one already points at:

* quiz_attempts: quiz_questions.course_id -> courses.user_id. quiz_questions.course_id
  and courses.user_id are NOT NULL and quiz_attempts.quiz_question_id is a CASCADE
  FK, so every attempt has an owner; NOT NULL is applied unconditionally in effect
  (the check below simply never finds a NULL there).
* review_items, by entity_type (the only values the code writes or ever wrote):
    - ``lecture_artifact`` -> lecture_artifacts.user_id
    - ``summary`` (legacy) -> summaries.course_id -> courses.user_id

review_items.entity_id has no FK, so an item whose entity was deleted, or whose
entity_type is unknown, cannot be attributed. Nothing is deleted to make NOT NULL
possible (user data is never lost): if any NULL remains the column is left nullable
and the count is printed. Such rows stay invisible to every user, which is the
fail-closed behaviour ``review_service._owned_by`` already has for them.

Revision ID: d4f6b8c0e2a3
Revises: c3e5a7b9d1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6b8c0e2a3"
down_revision: str | None = "c3e5a7b9d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("review_items", "quiz_attempts")

_BACKFILL = (
    # quiz_attempts <- quiz_questions -> courses
    """
    UPDATE quiz_attempts SET user_id = (
        SELECT c.user_id FROM quiz_questions q
        JOIN courses c ON c.id = q.course_id
        WHERE q.id = quiz_attempts.quiz_question_id
    )
    """,
    # review_items, entity_type = lecture_artifact
    """
    UPDATE review_items SET user_id = (
        SELECT a.user_id FROM lecture_artifacts a WHERE a.id = review_items.entity_id
    )
    WHERE entity_type = 'lecture_artifact'
    """,
    # review_items, entity_type = summary (legacy)
    """
    UPDATE review_items SET user_id = (
        SELECT c.user_id FROM summaries s
        JOIN courses c ON c.id = s.course_id
        WHERE s.id = review_items.entity_id
    )
    WHERE entity_type = 'summary'
    """,
)


def upgrade() -> None:
    bind = op.get_bind()

    for table in _TABLES:
        op.add_column(table, sa.Column("user_id", sa.String(36), nullable=True))

    for statement in _BACKFILL:
        bind.execute(sa.text(statement))

    for table in _TABLES:
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        orphans = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL")
        ).scalar_one()
        if orphans:
            print(f"{table}: {orphans} rows have no resolvable owner; user_id left nullable")
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                f"fk_{table}_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )
            if not orphans:
                batch.alter_column("user_id", existing_type=sa.String(36), nullable=False)


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_user_id", type_="foreignkey")
            batch.drop_column("user_id")
