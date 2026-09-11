"""Fold existing user emails to their normalized form and enforce it in the DB.

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-09-11 09:00:00.000000

Issue #91. Nothing normalised email case, so `alex@example.com` and
`Alex@example.com` were two accounts, an admin retyping an address in a
different case triggered a destructive repoint, and the repoint then stored
the new casing — which, lookups being exact-match, locked the user out.

The code fix normalises on the way in. This migration does the two things code
cannot: it folds the rows that already exist, and it adds a unique index on
`lower(email)` so the database refuses a case-differing duplicate whatever a
future call site forgets.

**Collisions are not resolved here.** If two rows already differ only by case,
folding them means choosing which account survives — which sessions, courses,
artifacts and OAuth links are kept and which are orphaned. That is an operator
decision with no safe default, so the migration aborts and names the rows
instead of silently picking one. On the live instance there are two accounts
and this is expected to be a no-op; it is written as though it is not.

The downgrade drops the index only. The original casing is not recoverable —
it was overwritten, not copied aside — and inventing one would be worse than
leaving the canonical form in place.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2g3h4i5"
down_revision: str | None = "c9d0e1f2g3h4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_users_email_lower"


def normalize_email(email: str) -> str:
    """Canonicalise an address the way `app.core.utils.normalize_email` does.

    Deliberately a copy rather than an import. A migration is a statement about
    one moment in the schema's history and has to keep producing the same
    result years from now; importing application code would let a later edit
    silently change what this migration did to rows that were folded long ago.

    The whole address is lower-cased, local part included. RFC 5321 §2.4 makes
    the local part formally case-sensitive; see the docstring on the
    application-side function for why that is ignored here.
    """
    return email.strip().lower()


def find_collisions(rows: Sequence[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group rows that would land on the same address once normalized.

    Args:
        rows: `(id, email)` pairs, as stored.

    Returns:
        A list of `(normalized_email, [(id, stored_email), ...])`, one entry per
        address claimed by more than one row, ordered by the normalized address.
        Empty when the fold is safe.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for user_id, email in rows:
        grouped.setdefault(normalize_email(email), []).append((user_id, email))
    return sorted((key, members) for key, members in grouped.items() if len(members) > 1)


def rows_to_fold(rows: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """The rows whose stored address is not already canonical.

    Args:
        rows: `(id, email)` pairs, as stored.

    Returns:
        `(id, normalized_email)` for each row that needs rewriting. Rows already
        in canonical form are left out, so the UPDATE touches nothing on an
        instance that was always well behaved.
    """
    return [
        (user_id, normalize_email(email))
        for user_id, email in rows
        if email != normalize_email(email)
    ]


def collision_report(collisions: Sequence[tuple[str, list[tuple[str, str]]]]) -> str:
    """Render the abort message for an operator who has to resolve a collision.

    Names every row involved, because "there is a duplicate" without the ids is
    not actionable against a database the operator has to open by hand.
    """
    lines = [
        f"Cannot normalize user emails: {len(collisions)} address(es) are held by "
        "more than one account once case is folded.",
        "",
        "Merging them means choosing which account survives — its sessions, courses, "
        "artifacts and linked OAuth identities are kept and the other's are orphaned. "
        "This migration will not make that choice for you.",
        "",
    ]
    for normalized, members in collisions:
        lines.append(f"  {normalized}")
        for user_id, stored in members:
            lines.append(f"    - id={user_id} email={stored!r}")
    lines += [
        "",
        "Resolve each group (merge or delete the redundant accounts), then run "
        "`alembic upgrade head` again.",
    ]
    return "\n".join(lines)


def upgrade() -> None:
    connection = op.get_bind()
    rows = [(row[0], row[1]) for row in connection.execute(sa.text("SELECT id, email FROM users"))]

    collisions = find_collisions(rows)
    if collisions:
        raise RuntimeError(collision_report(collisions))

    fold = rows_to_fold(rows)
    if fold:
        connection.execute(
            sa.text("UPDATE users SET email = :email WHERE id = :id"),
            [{"id": user_id, "email": email} for user_id, email in fold],
        )

    # Enforced by the database from here on, so the next
    # `select(User).where(User.email == ...)` written without a thought cannot
    # reintroduce duplicate accounts. The pre-existing exact-match
    # `ix_users_email` is left in place: it is now redundant but harmless, and
    # dropping a unique index on the login column buys nothing.
    op.create_index(INDEX_NAME, "users", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    # The folded casing is gone; only the constraint can be lifted.
    op.drop_index(INDEX_NAME, table_name="users")
