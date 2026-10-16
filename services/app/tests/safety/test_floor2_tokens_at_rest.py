"""Floor 2 — no plaintext third-party token or TOTP seed in the database or logs.

M34-S2-SEC-005 (R-017, M32 N-7), contract ``models.third-party-tokens v1``, with
the user's 2026-10-16 ruling that adds ``users.mfa_secret``. Today the OAuth and
Google Calendar tokens and the TOTP seed are stored as plaintext, so a database
dump or backup hands over every user's Google/GitHub access and their second
factor. They also reach the logs: a failed flush renders its bound parameters
into the exception text (``[parameters: (...)]``), and
``auth.oauth_callback`` logs that exception with ``logger.exception``.

Pins (RED until SEC-005 lands ``EncryptedText``, the model types and
``hide_parameters``):

* every credential-named column in the metadata either encrypts on the way to
  the driver (and decrypts back) or is classified here with a reason, and the
  five known columns are among those that encrypt;
* the parameters a failed INSERT puts in its exception text are ciphertext;
* the engine hides bound parameters from exception text altogether;
* an unreadable TOTP seed never turns MFA off: with ``mfa_enabled`` set and
  ``mfa_secret`` read back as ``None``, a TOTP login is refused like a wrong
  code (green today; it pins the fail-closed branch the new ``None`` read relies
  on, so a later "no secret means no MFA" shortcut fails here).

The plaintext test key is the root conftest's public all-zero key.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import exc as sa_exc
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql

SENTINEL = "ya29.FLOOR2-SENTINEL-third-party-token-0123456789"
TOTP_SENTINEL = "JBSWY3DPEHPK3PXPFLOOR2SENTINEL"

#: Columns that must be ciphertext at rest (contract table + the 2026-10-16 ruling).
MUST_ENCRYPT = {
    ("oauth_accounts", "access_token"),
    ("oauth_accounts", "refresh_token"),
    ("calendar_syncs", "access_token"),
    ("calendar_syncs", "refresh_token"),
    ("users", "mfa_secret"),
}

#: Credential-shaped column names that are reviewed and NOT encrypted at rest.
NOT_ENCRYPTED_REVIEWED = {
    ("calendar_syncs", "sync_token"): "Google's incremental-sync cursor; authorises nothing alone",
    ("telegram_links", "link_token"): (
        "our own one-time pairing code, not a third-party credential; hashing it is "
        "a separate follow-up (contracts-safety.md R3)"
    ),
}

_CREDENTIAL_NAME = re.compile(r"(^|_)(token|secret|password|api_key|apikey)$")


def _tables():
    import app.models  # noqa: F401  (registers every model on the metadata)
    from app.core.database import Base

    return Base.metadata.tables


def _credential_columns() -> set[tuple[str, str]]:
    found = set()
    for table in _tables().values():
        for col in table.columns:
            if _CREDENTIAL_NAME.search(col.name) and col.name != "hashed_password":
                found.add((table.name, col.name))
    return found


def _bind(table: str, column: str, value: str) -> object:
    dialect = postgresql.dialect()
    col_type = _tables()[table].columns[column].type
    proc = col_type.bind_processor(dialect)
    return proc(value) if proc else value


def _read(table: str, column: str, stored: object) -> object:
    dialect = postgresql.dialect()
    col_type = _tables()[table].columns[column].type
    proc = col_type.result_processor(dialect, None)
    return proc(stored) if proc else stored


def test_floor2_credential_column_scan_is_not_vacuous():
    found = _credential_columns()
    assert found >= MUST_ENCRYPT, f"scan missed known credential columns: {MUST_ENCRYPT - found}"
    stale = set(NOT_ENCRYPTED_REVIEWED) - found
    assert not stale, f"stale NOT_ENCRYPTED_REVIEWED entries: {stale}"


def test_floor2_every_credential_column_is_encrypted_or_reviewed():
    unreviewed = _credential_columns() - MUST_ENCRYPT - set(NOT_ENCRYPTED_REVIEWED)
    assert not unreviewed, (
        "credential-named columns with no at-rest decision (encrypt with "
        f"secret_box.EncryptedText, or classify here with a reason): {sorted(unreviewed)}"
    )


@pytest.mark.parametrize(("table", "column"), sorted(MUST_ENCRYPT))
def test_floor2_credential_reaches_the_driver_as_ciphertext(table, column):
    secret = TOTP_SENTINEL if column == "mfa_secret" else SENTINEL
    stored = _bind(table, column, secret)
    assert isinstance(stored, str) and stored.startswith("enc:v1:"), (
        f"{table}.{column} is written as plaintext (SEC-005: EncryptedText)"
    )
    assert secret not in stored
    # Not a blanking type: the value must come back.
    assert _read(table, column, stored) == secret


@pytest.mark.parametrize(("table", "column"), sorted(MUST_ENCRYPT))
def test_floor2_failed_insert_error_text_carries_no_plaintext(table, column):
    """What ``logger.exception`` would render when a flush fails on this row."""
    secret = TOTP_SENTINEL if column == "mfa_secret" else SENTINEL
    tbl = _tables()[table]
    compiled = insert(tbl).values({column: secret}).compile(dialect=postgresql.dialect())
    params = compiled.construct_params()
    processed = {
        k: (compiled._bind_processors[k](v) if k in compiled._bind_processors else v)
        for k, v in params.items()
    }
    err = sa_exc.DBAPIError.instance(
        str(compiled), processed, Exception("duplicate key value"), Exception
    )
    assert secret not in str(err), f"{table}.{column}: plaintext in a DB error's [parameters]"


def test_floor2_engine_hides_bound_parameters_from_error_text():
    from app.core.database import engine

    assert engine.sync_engine.hide_parameters is True, (
        "create_async_engine(..., hide_parameters=True): a failed statement otherwise "
        "renders every bound value (tokens, emails) into the exception that is logged"
    )


def _mfa_user(secret: str | None):
    from datetime import datetime

    from app.core.auth import hash_password
    from app.models.user import User

    user = MagicMock(spec=User)
    for k, v in {
        "id": "user-mfa-1",
        "email": "mfa@example.com",
        "username": "mfa",
        "hashed_password": hash_password("TestPass1!"),
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": True,
        "mfa_enabled": True,
        "mfa_secret": secret,
        "avatar_url": None,
        "backup_codes": None,
        "last_login_at": None,
        "tokens_valid_from": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }.items():
        setattr(user, k, v)
    return user


@pytest.mark.asyncio
@pytest.mark.parametrize("body_extra", [{"totp_code": "123456"}, {}])
async def test_floor2_unreadable_totp_seed_never_bypasses_mfa(async_client, body_extra):
    """``mfa_enabled`` gates the second factor; a ``None`` seed is a failed code, not "no MFA"."""
    user = _mfa_user(None)
    verify = MagicMock(return_value=True)
    with (
        patch(
            "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user
        ),
        patch("app.api.auth.verify_totp", verify),
    ):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "mfa@example.com", "password": "TestPass1!", **body_extra},
        )
    assert response.status_code == 403, response.text
    assert "access_token" not in response.cookies
    assert "refresh_token" not in response.cookies
    assert not any(c.args and c.args[0] is None for c in verify.call_args_list), (
        "verify_totp was handed a None seed"
    )
