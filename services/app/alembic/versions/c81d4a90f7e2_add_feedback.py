"""Add the feedback table.

The instance had no way for a tester to say anything. Sentry records what
crashed; the beta funnel records that someone stopped after their first upload.
Neither records *why*, and no amount of instrumentation infers it — that has to
come from the person.

`user_id` is NOT NULL on purpose, which makes the table user-scoped: the
account-deletion guard in `account_service` classifies it automatically and
`delete_user_account` removes it with the rest. That loses the signal when a
tester leaves, which is a real cost, but the message is free text the reporter
wrote and may name them or somebody else. Anonymising by nulling `user_id`
would keep exactly the part that carries the risk.

The revision id is random rather than the next value in any visible sequence:
two branches once picked the same "obvious" next id, and duplicate identifiers
are not two heads — Alembic refuses to load the directory at all.

Revision ID: c81d4a90f7e2
Revises: 4f1c7a2e9b63
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c81d4a90f7e2"
down_revision: str | None = "4f1c7a2e9b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="bug"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("route", sa.String(length=500), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    # The admin inbox reads newest-first within a status.
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")
