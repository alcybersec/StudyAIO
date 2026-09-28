"""Email invites: address, token, sent/accepted timestamps

Revision ID: b7e3d92a5c14
Revises: c81d4a90f7e2
Create Date: 2026-09-28

Adds the columns that turn an invite from a quantity into a person.

`invites_issued` counted capacity — "five uses outstanding" — so a gap between
invited and registered could not distinguish never-sent from never-opened from
opened-and-abandoned. `email` says who, `sent_at` says whether it actually went
out, and `accepted_at` says whether they arrived.

All nullable: every existing row is a shared code and stays one.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e3d92a5c14"
down_revision = "c81d4a90f7e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add email-invite columns and their indexes."""
    op.add_column("invite_codes", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("invite_codes", sa.Column("token_hash", sa.String(length=64), nullable=True))
    op.add_column("invite_codes", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "invite_codes", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Unique, and safe alongside every existing shared code: Postgres treats
    # NULLs as distinct in a unique index, so unlimited rows may have no token.
    op.create_index("ix_invite_codes_token_hash", "invite_codes", ["token_hash"], unique=True)
    # Not unique. The same person may be invited again after an expiry or a
    # revoke, and refusing that would make a resend impossible.
    op.create_index("ix_invite_codes_email", "invite_codes", ["email"])


def downgrade() -> None:
    """Drop the email-invite columns.

    Destroys the record of who was invited and whether they accepted. The
    invites themselves survive as shared codes, since `code` was always
    populated.
    """
    op.drop_index("ix_invite_codes_email", table_name="invite_codes")
    op.drop_index("ix_invite_codes_token_hash", table_name="invite_codes")
    op.drop_column("invite_codes", "accepted_at")
    op.drop_column("invite_codes", "sent_at")
    op.drop_column("invite_codes", "token_hash")
    op.drop_column("invite_codes", "email")
