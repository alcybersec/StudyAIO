"""Stop storing MFA backup codes in plaintext.

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-07 09:00:00.000000

`users.backup_codes` held a JSON array of the codes themselves, so anything
that could read the column -- a backup, a replica, a dump, an injection -- held
a complete MFA bypass. From this revision on it holds SHA-256 digests.

**Existing plaintext arrays are cleared, not hashed forward.** Nothing in the
application ever verified a backup code, so no stored value was a working
credential and clearing invalidates nothing that functioned. Hashing them
forward would do the opposite of what this revision is for: it would promote an
8-character `[A-Z0-9]` code -- about 41 bits, weak enough to grind offline
against a fast hash -- into a live credential for the first time. The new format
is wider precisely so that a fast hash is the right choice for it.

The cost is honest and worth stating: a user who wrote their old codes on paper
loses them silently, with no email and no prompt. They keep their authenticator,
which still works; if they have lost that too, an administrator can clear the
enrollment via `POST /api/admin/users/{id}/mfa-reset`, which did not exist
before this change. Re-enrolling MFA issues codes in the new format.

Values that are already digests are left untouched, so this is idempotent and
safe if a newer application version has already written to the column.

"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2g3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: What `hashlib.sha256(...).hexdigest()` produces: 64 lowercase hex chars.
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def needs_clearing(raw: str | None) -> bool:
    """Whether a stored `users.backup_codes` value must be discarded.

    Deliberately conservative in one direction only: anything this cannot
    positively identify as already-hashed is cleared. Getting that wrong the
    safe way costs a user a re-enrollment; getting it wrong the other way leaves
    a plaintext credential in the column, which is the whole point of the
    revision.

    Args:
        raw: The column value as stored.

    Returns:
        True if the row should be set to NULL.
    """
    if raw is None or not raw.strip():
        # Nothing stored, nothing to clear. Writing NULL over NULL would only
        # inflate the count this migration logs.
        return False

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        # Unparseable: not a value anything can authenticate against, and not
        # one we can inspect for plaintext either. Discard it.
        return True

    if not isinstance(parsed, list):
        return True

    if not parsed:
        # An empty array is what the application writes once the last code has
        # been spent. It carries no credential; leave it alone.
        return False

    return not all(isinstance(item, str) and _SHA256_HEX.match(item) for item in parsed)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, backup_codes FROM users WHERE backup_codes IS NOT NULL")
    ).fetchall()

    stale = [row[0] for row in rows if needs_clearing(row[1])]
    for user_id in stale:
        bind.execute(
            sa.text("UPDATE users SET backup_codes = NULL WHERE id = :id"), {"id": user_id}
        )

    if stale:
        # Alembic's stdout is the only channel a migration has, and this one
        # destroys data the operator may need to explain to a user.
        print(
            f"cleared plaintext MFA backup codes for {len(stale)} user(s); "
            "they must re-enroll MFA to get codes in the hashed format"
        )


def downgrade() -> None:
    # A digest cannot be turned back into a code, and the pre-revision
    # application read this column as the codes themselves -- it would hand
    # digests to a user as if they were usable. Clear it instead.
    op.execute("UPDATE users SET backup_codes = NULL")
