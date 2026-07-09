"""Add assessment_id to course_documents for per-assessment attachments.

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-07-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v2w3x4y5z6a7"
down_revision: str | None = "u1v2w3x4y5z6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_documents",
        sa.Column("assessment_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_course_documents_assessment_id",
        "course_documents",
        "assessments",
        ["assessment_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_course_documents_assessment_id",
        "course_documents",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_course_documents_assessment_id", table_name="course_documents")
    op.drop_constraint("fk_course_documents_assessment_id", "course_documents", type_="foreignkey")
    op.drop_column("course_documents", "assessment_id")
