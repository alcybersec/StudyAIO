"""Store only a SHA-256 hash of magic link tokens.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-09-01 10:00:00.000000

Hash the existing plaintext token values in place, then drop the plaintext
column. Outstanding links keep working across the deploy: the raw token a
user already holds hashes to the stored value. Raw tokens cannot be
reconstructed from hashes, so the downgrade drops all magic link rows —
each is a single-use credential that expires within the hour, and a
re-request is the recovery path.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w3x4y5z6a7b8"
down_revision: str | None = "v2w3x4y5z6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("magic_links", sa.Column("token_hash", sa.String(length=64), nullable=True))
    # Backfill from the plaintext tokens while they are still readable.
    # Postgres sha256() + encode(..., 'hex') matches
    # hashlib.sha256(token.encode()).hexdigest() exactly (lowercase hex).
    op.execute("UPDATE magic_links SET token_hash = encode(sha256(token::bytea), 'hex')")
    op.alter_column("magic_links", "token_hash", existing_type=sa.String(length=64), nullable=False)
    op.create_index("ix_magic_links_token_hash", "magic_links", ["token_hash"], unique=True)
    # Postgres drops the column's unique constraint and index automatically.
    op.drop_index("ix_magic_links_token", table_name="magic_links")
    op.drop_column("magic_links", "token")


def downgrade() -> None:
    # Raw tokens cannot be recovered from their hashes. Drop the rows rather
    # than write back unusable values — the pre-migration schema requires the
    # plaintext token to authenticate a reset.
    op.execute("DELETE FROM magic_links")
    op.add_column("magic_links", sa.Column("token", sa.String(length=255), nullable=False))
    op.create_index("ix_magic_links_token", "magic_links", ["token"], unique=True)
    op.drop_index("ix_magic_links_token_hash", table_name="magic_links")
    op.drop_column("magic_links", "token_hash")
