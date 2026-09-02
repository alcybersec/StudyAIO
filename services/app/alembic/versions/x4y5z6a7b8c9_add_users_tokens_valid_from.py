"""Add users.tokens_valid_from to revoke tokens on password reset/change.

Set to now() when a password is reset or changed, or MFA is disabled; tokens
whose `iat` is not newer than the cutoff are rejected by get_current_user and
the refresh endpoint. NULL (all existing rows) means no restriction.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-09-01 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x4y5z6a7b8c9"
down_revision: str | None = "w3x4y5z6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tokens_valid_from", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "tokens_valid_from")
