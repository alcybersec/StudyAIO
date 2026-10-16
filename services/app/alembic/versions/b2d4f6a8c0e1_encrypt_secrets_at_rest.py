"""Encrypt third-party tokens and the TOTP seed at rest.

M34-S2-SEC-005 (``models.secrets-at-rest v1``). Five columns hold a secret:
``oauth_accounts.access_token`` / ``refresh_token``, ``calendar_syncs.access_token`` /
``refresh_token`` and ``users.mfa_secret``. They are stored as ``enc:v1:<token>``
under ``SETTINGS_ENCRYPTION_KEY`` (the scheme per-user AI credentials use).

Upgrade calls ``secret_box.check_startup()`` before touching anything: a multi-user
instance with no key aborts. A single-user instance with no key keeps its values and
prints how many are still plaintext and the ``encrypt-user-secrets --apply`` command.
It widens the OAuth columns and ``mfa_secret`` to Text, then encrypts plaintext with
a primary-key UPDATE for the values that change. The rows are read through plain Text
columns (``sa.table``), never the ORM and never ``EncryptedText``.

The downgrade removes at-rest protection: every secret is written back as plaintext.
It decrypts every value first and aborts, changing nothing, when there is no key while
ciphertext exists, when a value fails authentication, or when a decrypted value is
longer than its narrowed width (1000 for the OAuth tokens, 64 for ``mfa_secret``).
Everything runs in the one migration transaction. It prints counts only.

Revision ID: b2d4f6a8c0e1
Revises: a1c2d3e4f5a6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core import secret_box

revision: str = "b2d4f6a8c0e1"
down_revision: str | None = "a1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table(name: str, column: str) -> sa.TableClause:
    return sa.table(name, sa.column("id", sa.String), sa.column(column, sa.Text))


def _read(bind: sa.Connection, name: str, column: str) -> list[tuple[str, str]]:
    t = _table(name, column)
    stmt = sa.select(t.c.id, t.c[column]).where(t.c[column].is_not(None))
    return [(r[0], r[1]) for r in bind.execute(stmt)]


def _write(bind: sa.Connection, name: str, column: str, pk: str, value: str) -> None:
    t = _table(name, column)
    bind.execute(sa.update(t).where(t.c.id == pk).values({column: value}))


def upgrade() -> None:
    secret_box.check_startup()
    bind = op.get_bind()
    # (table, column, width the column had before this revision, or None for Text)
    columns: tuple[tuple[str, str, int | None], ...] = (
        ("oauth_accounts", "access_token", 1000),
        ("oauth_accounts", "refresh_token", 1000),
        ("calendar_syncs", "access_token", None),
        ("calendar_syncs", "refresh_token", None),
        ("users", "mfa_secret", 64),
    )

    for table, column, width in columns:
        if width is not None:
            op.alter_column(
                table,
                column,
                existing_type=sa.String(width),
                type_=sa.Text(),
                existing_nullable=True,
            )

    plaintext_left = 0
    done = 0
    for table, column, _width in columns:
        for pk, value in _read(bind, table, column):
            if secret_box.is_encrypted(value):
                continue
            new = secret_box.encrypt(value)
            if new == value:
                plaintext_left += 1
                continue
            _write(bind, table, column, pk, new)
            done += 1

    print(f"secrets-at-rest: encrypted {done} value(s)")
    if plaintext_left:
        print(
            f"secrets-at-rest: {plaintext_left} value(s) remain plaintext because "
            f"{secret_box.ENV_VAR} is not set. Set it, then run: "
            "python -m app.cli encrypt-user-secrets --apply"
        )


def downgrade() -> None:
    bind = op.get_bind()
    # (table, column, width the column had before this revision, or None for Text)
    columns: tuple[tuple[str, str, int | None], ...] = (
        ("oauth_accounts", "access_token", 1000),
        ("oauth_accounts", "refresh_token", 1000),
        ("calendar_syncs", "access_token", None),
        ("calendar_syncs", "refresh_token", None),
        ("users", "mfa_secret", 64),
    )

    plain: list[tuple[str, str, str, str]] = []
    has_ciphertext = False
    undecryptable = 0
    too_long = 0
    for table, column, width in columns:
        for pk, value in _read(bind, table, column):
            if secret_box.is_encrypted(value):
                has_ciphertext = True
                if not secret_box.is_configured():
                    continue
                try:
                    value_plain = secret_box.decrypt(value)
                except secret_box.SecretDecryptError:
                    undecryptable += 1
                    continue
            else:
                value_plain = value
            if width is not None and len(value_plain) > width:
                too_long += 1
            plain.append((table, column, pk, value_plain))

    if has_ciphertext and not secret_box.is_configured():
        raise RuntimeError(
            f"downgrade aborted: encrypted values exist and {secret_box.ENV_VAR} is not set; "
            "nothing was changed"
        )
    if undecryptable or too_long:
        raise RuntimeError(
            f"downgrade aborted: {undecryptable} value(s) cannot be decrypted and "
            f"{too_long} value(s) exceed the narrowed width (1000 for OAuth tokens, 64 for "
            "mfa_secret); nothing was changed"
        )

    written = 0
    for table, column, pk, value_plain in plain:
        _write(bind, table, column, pk, value_plain)
        written += 1
    for table, column, width in columns:
        if width is not None:
            op.alter_column(
                table,
                column,
                existing_type=sa.Text(),
                type_=sa.String(width),
                existing_nullable=True,
            )
    print(f"secrets-at-rest: wrote {written} value(s) back as plaintext (protection removed)")
