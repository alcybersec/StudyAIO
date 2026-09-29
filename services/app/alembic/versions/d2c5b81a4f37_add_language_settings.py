"""User settings: interface language and whether it reaches AI output

Revision ID: d2c5b81a4f37
Revises: b7e3d92a5c14
Create Date: 2026-09-29

Two columns rather than one enum: `language` says which language, and
`content_language` says how far it reaches. Separating them means turning
content translation off does not lose the interface preference, and a third
language later needs no new states.

`content_language` defaults to false on purpose. Existing users get the new
setting at its current behaviour — nobody's summaries change language because
the app gained a menu that can.
"""

import sqlalchemy as sa
from alembic import op

revision = "d2c5b81a4f37"
down_revision = "b7e3d92a5c14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add `language` and `content_language` to user_settings.

    Both non-null with server defaults, so existing rows are filled in place
    and no backfill is needed.
    """
    op.add_column(
        "user_settings",
        sa.Column("language", sa.String(length=5), nullable=False, server_default="en"),
    )
    op.add_column(
        "user_settings",
        sa.Column("content_language", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Drop both columns.

    Loses every stored language preference; the app then serves English to
    everyone, which is what it did before this revision.
    """
    op.drop_column("user_settings", "content_language")
    op.drop_column("user_settings", "language")
