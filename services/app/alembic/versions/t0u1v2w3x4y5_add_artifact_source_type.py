"""Add source_type column to lecture_artifacts for quick captures.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-07-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "t0u1v2w3x4y5"
down_revision: str | None = "s9t0u1v2w3x4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lecture_artifacts",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="upload"),
    )


def downgrade() -> None:
    op.drop_column("lecture_artifacts", "source_type")
