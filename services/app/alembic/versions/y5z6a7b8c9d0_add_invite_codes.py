"""Add invite_codes and users.invite_code_id for gated registration.

Backs `REGISTRATION_MODE=invite`: registration requires a redeemable code.
`users.invite_code_id` records which invite an account signed up with, so a
leaked code can be traced to the accounts it created.

Both FKs are ON DELETE SET NULL — deleting the issuing admin must not
invalidate outstanding invites, and deleting an invite must not delete the
users who redeemed it.

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-09-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "y5z6a7b8c9d0"
down_revision: str | None = "x4y5z6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"], unique=True)

    op.add_column("users", sa.Column("invite_code_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_users_invite_code_id",
        "users",
        "invite_codes",
        ["invite_code_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_invite_code_id", "users", type_="foreignkey")
    op.drop_column("users", "invite_code_id")
    op.drop_index("ix_invite_codes_code", table_name="invite_codes")
    op.drop_table("invite_codes")
