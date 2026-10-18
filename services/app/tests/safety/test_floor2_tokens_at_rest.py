"""Floor 2 — no plaintext third-party token or TOTP seed in the database or logs.

M34-S2-SEC-005 (R-017, M32 N-7), contract ``models.secrets-at-rest v1`` (first
recorded as ``models.third-party-tokens v1``), with the user's 2026-10-16 ruling
that adds ``users.mfa_secret``. Before SEC-005 the OAuth and Google Calendar
tokens and the TOTP seed were plaintext, so a database dump or backup handed over
every user's Google/GitHub access and their second factor. They also reached the
logs: a failed flush renders its bound parameters into the exception text
(``[parameters: (...)]``), and ``auth.oauth_callback`` logs that exception with
``logger.exception``. Review: ``docs/gates/M34/contracts-safety.md`` (C1-C7) and
``docs/gates/M34/sec005-safety.md``.

Pins:

* every credential-named column in the metadata either encrypts on the way to
  the driver (and decrypts back) or is classified here with a reason, and the
  five known columns are among those that encrypt;
* the parameters a failed INSERT puts in its exception text are ciphertext;
* the engine hides bound parameters from exception text altogether;
* an unreadable TOTP seed never turns MFA off (C2): with ``mfa_enabled`` set and
  ``mfa_secret`` read back as ``None``, a TOTP code is refused like a wrong
  code on the password and the OAuth path, backup codes still sign in, and
  ``disable_mfa`` refuses without changing the account;
* rotation (C1) re-keys stored strings on real SQL and never rewrites an
  unreadable value; the revision's abort paths (C4, C5) change nothing;
* the call-time ``structlog.get_logger()`` sites still pass the redaction
  chain, and the calendar revoke keeps the token out of the URL (C7).

M34-S2-SEC-013 (``models.secrets-at-rest v2``) stops storing the OAuth sign-in
tokens; M34-S2-SEC-014 (``models.telegram-pairing-code v1``) stores the Telegram
pairing code as a SHA-256 digest. Review: ``docs/gates/M34/sec013-014-safety.md``.
The two ``oauth_accounts`` columns stay in ``MUST_ENCRYPT`` until they are dropped
(``models.secrets-at-rest v3``): a value the previous release writes during the
deploy window is still ciphertext. Further pins:

* no code path writes a non-``None`` OAuth token: ``create_or_link_oauth`` takes
  none, no ``app/`` code assigns or inserts one, both branches leave the row with
  ``None``, and the callback hands the provider's token dict to ``fetch_userinfo``
  only and never logs it; Google is not asked for a refresh token;
* the pairing code is never stored or logged in plaintext (nor its digest logged),
  is looked up by digest in SQL, and presenting the stored digest is a miss;
* revision ``c3e5a7b9d1f2`` deletes no row and touches no identity or link column
  (floor 4), its downgrade restores nothing for OAuth and nulls every digest.

Not pinned: pairing codes still never expire (R-048, open).

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
        "SHA-256 digest of our own one-time pairing code (models.telegram-pairing-code v1, "
        "SEC-014); the plaintext is never stored, so encrypting the digest adds nothing"
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


@pytest.mark.asyncio
async def test_floor2_unreadable_totp_seed_never_bypasses_oauth_mfa(async_client):
    """C2 on the OAuth path: the pending-MFA step refuses a code and counts the failure."""
    from app.core.auth import MFA_PENDING_COOKIE, create_mfa_pending_token

    user = _mfa_user(None)
    verify = MagicMock(return_value=True)
    async_client.cookies.set(MFA_PENDING_COOKIE, create_mfa_pending_token(user.id))
    try:
        with (
            patch(
                "app.api.auth.user_service.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock),
            patch(
                "app.api.auth.login_throttle.record_failure", new_callable=AsyncMock
            ) as record_failure,
            patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock) as clear,
            patch("app.api.auth.verify_totp", verify),
        ):
            response = await async_client.post("/api/auth/oauth/mfa", json={"totp_code": "123456"})
    finally:
        async_client.cookies.clear()
    assert response.status_code == 403, response.text
    assert "access_token" not in response.cookies
    assert "refresh_token" not in response.cookies
    record_failure.assert_awaited_once_with(user.email)
    clear.assert_not_awaited()
    assert user.mfa_enabled is True
    assert not any(c.args and c.args[0] is None for c in verify.call_args_list)


# ── rotation on stored strings (C1), against real SQL ──────────────────────


class _SqlSession:
    """Just enough of ``AsyncSession`` to run ``_rekey_raw_columns`` on SQLite.

    The command must issue Core statements over the stored strings; this runs
    them for real, so an ORM detour, a ``NULL`` write-back or a skipped
    ``UPDATE`` shows up in the table, not in a mock's call list.
    """

    def __init__(self, conn) -> None:
        self.conn = conn

    async def execute(self, stmt):
        return self.conn.execute(stmt)


def _rotation_db(rows: dict[tuple[str, str], dict[str, str | None]]):
    import sqlalchemy as sa

    from app import cli

    engine = sa.create_engine("sqlite://")
    md = sa.MetaData()
    columns: dict[str, list[str]] = {}
    for table, column in cli.RAW_SECRET_COLUMNS:
        columns.setdefault(table, []).append(column)
    tables = {
        name: sa.Table(
            name,
            md,
            sa.Column("id", sa.Text, primary_key=True),
            *(sa.Column(c, sa.Text) for c in cols),
        )
        for name, cols in columns.items()
    }
    md.create_all(engine)
    conn = engine.connect()
    by_row: dict[tuple[str, str], dict[str, str | None]] = {}
    for (table, column), values in rows.items():
        for row_id, value in values.items():
            by_row.setdefault((table, row_id), {})[column] = value
    for (table, row_id), values in by_row.items():
        conn.execute(tables[table].insert().values(id=row_id, **values))
    return conn, tables


def _stored(conn, tables) -> dict[tuple[str, str, str], str | None]:
    out = {}
    for name, table in tables.items():
        for row in conn.execute(table.select()).mappings():
            for col in table.columns:
                if col.name != "id":
                    out[(name, col.name, row["id"])] = row[col.name]
    return out


@pytest.mark.asyncio
async def test_floor2_rotation_rekeys_stored_strings_and_never_rewrites_an_unreadable_one(
    monkeypatch,
):
    """C1: plaintext and old-key values end under the first key; unreadable stay byte-for-byte."""
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from app import cli
    from app.config import settings
    from app.core import secret_box

    new, old, lost = (Fernet.generate_key().decode() for _ in range(3))

    def under(key: str, plaintext: str) -> str:
        return secret_box.PREFIX + Fernet(key.encode()).encrypt(plaintext.encode()).decode()

    current = under(new, "current-token")
    unreadable_token = under(lost, SENTINEL)
    unreadable_seed = under(lost, TOTP_SENTINEL)
    rows = {
        ("oauth_accounts", "access_token"): {"o1": SENTINEL, "o2": unreadable_token},
        ("oauth_accounts", "refresh_token"): {"o1": under(old, "1//old-refresh"), "o2": current},
        ("calendar_syncs", "access_token"): {"c1": under(old, "ya29.old-cal")},
        ("calendar_syncs", "refresh_token"): {"c1": None},
        ("users", "mfa_secret"): {"u1": TOTP_SENTINEL, "u2": unreadable_seed},
    }
    plain = {
        ("oauth_accounts", "access_token", "o1"): SENTINEL,
        ("oauth_accounts", "refresh_token", "o1"): "1//old-refresh",
        ("calendar_syncs", "access_token", "c1"): "ya29.old-cal",
        ("users", "mfa_secret", "u1"): TOTP_SENTINEL,
    }
    untouched = {
        ("oauth_accounts", "access_token", "o2"): unreadable_token,
        ("oauth_accounts", "refresh_token", "o2"): current,
        ("calendar_syncs", "refresh_token", "c1"): None,
        ("users", "mfa_secret", "u2"): unreadable_seed,
    }
    monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(f"{new},{old}"))

    conn, tables = _rotation_db(rows)
    before = _stored(conn, tables)
    dry = await cli._rekey_raw_columns(_SqlSession(conn), apply=False)
    assert _stored(conn, tables) == before, "a dry run wrote to the table"
    assert dry == (2, 2, 2)

    counts = await cli._rekey_raw_columns(_SqlSession(conn), apply=True)
    after = _stored(conn, tables)

    assert counts == (2, 2, 2), "(encrypted, rotated, unreadable) is wrong: the exit gate lies"
    for key, value in untouched.items():
        assert after[key] == value, f"{key} was rewritten (unreadable or current value)"
    first = Fernet(new.encode())
    for key, secret in plain.items():
        stored = after[key]
        assert secret_box.is_encrypted(stored) and secret not in stored, f"{key} left plaintext"
        token = stored[len(secret_box.PREFIX) :].encode()
        assert first.decrypt(token).decode() == secret, f"{key} is not under the first key"


# ── the new log sites still pass through the redaction chain ───────────────


@pytest.fixture
def log_stream():
    """The app's real logging configuration on a fresh root handler; restored after."""
    import io
    import logging

    import structlog

    from app.core.logging import configure_logging

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    out = io.StringIO()
    root.handlers = [logging.StreamHandler(out)]
    try:
        configure_logging("DEBUG")
        root.setLevel(logging.DEBUG)
        yield out
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_config)


def test_floor2_fresh_logger_proxy_is_redacted_like_a_module_logger(log_stream):
    """SEC-005 logs through ``structlog.get_logger()`` at call time; it must not skip redaction."""
    import structlog

    address = "floor2-fresh-proxy@example.com"
    structlog.get_logger().warning("fresh_proxy_probe", note=address)
    text = log_stream.getvalue()
    assert "fresh_proxy_probe" in text, "probe line never reached the handler (vacuous)"
    assert address not in text and "[redacted-email]" in text, text

    # Bound parameters in an error string. The backstop's `[parameters: ...]` match runs to
    # end of text, so on a rendered JSON line it also eats the fields after it (event
    # name included): over-redaction, logged as a non-floor finding in sec005-safety.md.
    structlog.get_logger().warning(
        "fresh_proxy_params", error=f"boom [parameters: ('{SENTINEL}',)]"
    )
    text = log_stream.getvalue()
    assert SENTINEL not in text and "[parameters: redacted]" in text, text


def test_floor2_undecryptable_column_log_names_the_column_not_the_value(log_stream):
    """The type-level event, through the real chain: the column, never ciphertext or plaintext."""
    from cryptography.fernet import Fernet

    from app.core import secret_box

    lost = Fernet(Fernet.generate_key())
    foreign = secret_box.PREFIX + lost.encrypt(SENTINEL.encode()).decode()
    assert _read("oauth_accounts", "access_token", foreign) is None
    text = log_stream.getvalue()
    assert "secret_at_rest_undecryptable" in text and "oauth_accounts.access_token" in text, text
    assert SENTINEL not in text and foreign[len(secret_box.PREFIX) :] not in text, text


# ── the rest of C2: disable refuses, backup codes still work ───────────────


@pytest.mark.asyncio
async def test_floor2_disable_mfa_with_unreadable_seed_refuses_and_changes_nothing():
    """C2.4/C2.5: no self-heal, and not the false "MFA is not enabled"."""
    from app.services import user_service

    user = _mfa_user(None)
    user.backup_codes = '["digest"]'
    session = MagicMock(flush=AsyncMock())
    with (
        patch.object(user_service, "get_user_by_id", new=AsyncMock(return_value=user)),
        patch.object(user_service, "verify_totp", MagicMock(return_value=True)),
        pytest.raises(ValueError) as caught,
    ):
        await user_service.disable_mfa(session, user.id, "123456")
    assert "not enabled" not in str(caught.value), caught.value
    assert (user.mfa_enabled, user.mfa_secret, user.backup_codes, user.tokens_valid_from) == (
        True,
        None,
        '["digest"]',
        None,
    ), "disable_mfa changed the account while refusing"
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_floor2_backup_code_still_signs_in_when_the_seed_is_unreadable(async_client):
    """C2.3: fail closed on TOTP must not lock out the backup-code path."""
    user = _mfa_user(None)
    user.backup_codes = '["digest"]'
    with (
        patch(
            "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user
        ),
        patch(
            "app.api.auth.user_service.consume_backup_code", new_callable=AsyncMock, return_value=0
        ) as consume,
        patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock),
        patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock),
        patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock),
    ):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "TestPass1!", "backup_code": "abcd-efgh"},
        )
    assert response.status_code == 200, response.text
    consume.assert_awaited_once()
    assert consume.await_args.args[1] is user


# ── C7: the revoke call keeps the token out of the URL ──────────────────────


@pytest.mark.asyncio
async def test_floor2_calendar_revoke_sends_the_token_in_the_body_not_the_url():
    """A URL lands in httpx error text and proxy logs; the form body does not."""
    from types import SimpleNamespace

    from app.services import gcal_service

    cal = SimpleNamespace(id="sync-f2", user_id="user-f2", access_token=SENTINEL)
    session = MagicMock(flush=AsyncMock(), delete=AsyncMock())
    result = MagicMock()
    result.scalar_one_or_none.return_value = cal
    session.execute = AsyncMock(return_value=result)
    client = MagicMock()
    client.post = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    with patch("httpx.AsyncClient", return_value=client):
        assert await gcal_service.disconnect_calendar(session, cal.user_id, cal.id) is True
    client.post.assert_awaited_once()
    args, kwargs = client.post.await_args
    assert SENTINEL not in repr(args) and SENTINEL not in repr(kwargs.get("params")), kwargs
    assert kwargs.get("data") == {"token": SENTINEL}


# ── the revision: abort paths change nothing (C4, C5) ──────────────────────

REVISION = "b2d4f6a8c0e1"


class _Op:
    """``alembic.op`` stand-in over a real SQLite connection; records column changes."""

    def __init__(self, conn) -> None:
        self.conn = conn
        self.altered: list[tuple[str, str]] = []

    def get_bind(self):
        return self.conn

    def alter_column(self, table, column, **_kw) -> None:
        self.altered.append((table, column))


def _revision(monkeypatch, conn):
    import importlib.util

    from tests.safety._source import APP_ROOT

    [path] = (APP_ROOT.parent / "alembic" / "versions").glob(f"{REVISION}_*.py")
    spec = importlib.util.spec_from_file_location(f"_floor2_rev_{REVISION}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    op = _Op(conn)
    monkeypatch.setattr(module, "op", op)
    return module, op


def _key(monkeypatch, key: str, *, single_user: bool = False) -> None:
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(key))
    monkeypatch.setattr(settings, "single_user_mode", single_user)


def _plain_rows() -> dict[tuple[str, str], dict[str, str | None]]:
    return {
        ("oauth_accounts", "access_token"): {"o1": SENTINEL},
        ("oauth_accounts", "refresh_token"): {"o1": "1//refresh"},
        ("calendar_syncs", "access_token"): {"c1": "ya29.cal"},
        ("calendar_syncs", "refresh_token"): {"c1": None},
        ("users", "mfa_secret"): {"u1": TOTP_SENTINEL},
    }


def test_floor2_upgrade_without_a_key_on_multi_user_aborts_before_touching_anything(
    monkeypatch,
):
    """C4: a migration that ran before the app must not report success over plaintext."""
    _key(monkeypatch, "")
    conn, tables = _rotation_db(_plain_rows())
    before = _stored(conn, tables)
    module, op = _revision(monkeypatch, conn)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert op.altered == [] and _stored(conn, tables) == before


def test_floor2_upgrade_with_a_key_leaves_no_plaintext(monkeypatch):
    from cryptography.fernet import Fernet

    from app.core import secret_box

    _key(monkeypatch, Fernet.generate_key().decode())
    conn, tables = _rotation_db(_plain_rows())
    module, _op = _revision(monkeypatch, conn)
    module.upgrade()
    after = {k: v for k, v in _stored(conn, tables).items() if v is not None}
    assert len(after) == 4
    for key, value in after.items():
        assert secret_box.is_encrypted(value), f"{key} left plaintext by the upgrade"
        assert SENTINEL not in value and TOTP_SENTINEL not in value


@pytest.mark.parametrize("case", ["no_key", "undecryptable", "too_long"])
def test_floor2_downgrade_abort_paths_change_nothing(monkeypatch, case):
    """C5: an abort leaves every value as it was, still encrypted, and narrows nothing."""
    from cryptography.fernet import Fernet

    from app.core import secret_box

    key = Fernet.generate_key().decode()
    _key(monkeypatch, key)
    rows = _plain_rows()
    for values in rows.values():
        for row_id, value in values.items():
            if value is not None:
                values[row_id] = secret_box.encrypt(value)
    if case == "undecryptable":
        lost = Fernet(Fernet.generate_key())
        rows[("users", "mfa_secret")]["u2"] = (
            secret_box.PREFIX + lost.encrypt(TOTP_SENTINEL.encode()).decode()
        )
    if case == "too_long":
        rows[("users", "mfa_secret")]["u2"] = secret_box.encrypt("A" * 65)
    if case == "no_key":
        _key(monkeypatch, "")
    conn, tables = _rotation_db(rows)
    before = _stored(conn, tables)
    module, op = _revision(monkeypatch, conn)
    with pytest.raises(RuntimeError):
        module.downgrade()
    assert op.altered == [], "the downgrade narrowed a column before aborting"
    assert _stored(conn, tables) == before, "the downgrade wrote values before aborting"


# ── SEC-013: OAuth sign-in tokens are never stored ─────────────────────────

REFRESH_SENTINEL = "1//FLOOR2-SENTINEL-refresh-token-0123456789"
_OAUTH_TOKEN_ATTRS = {"access_token", "refresh_token"}


def test_floor2_create_or_link_oauth_accepts_no_provider_token():
    """No caller can hand the service a token: no named parameter, no ``**kwargs``."""
    import inspect

    from app.services.user_service import create_or_link_oauth

    params = inspect.signature(create_or_link_oauth).parameters
    assert not _OAUTH_TOKEN_ATTRS & set(params), sorted(params)
    assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()), sorted(params)


def _is_none(node) -> bool:
    import ast

    return isinstance(node, ast.Constant) and node.value is None


def test_floor2_no_app_code_writes_a_non_none_oauth_token():
    """Static: in every module that touches ``OAuthAccount``, a token write is ``None`` or nothing.

    Covers the constructor keyword, attribute assignment (``acct.access_token = …``),
    ``setattr(acct, "access_token", …)`` and Core ``.values(access_token=…)``.
    """
    import ast

    from tests.safety._source import app_modules, parse, rel

    offences: list[str] = []
    none_writes = 0
    scanned: list[str] = []
    for path in app_modules(exclude=("app/models/",)):
        src = path.read_text(encoding="utf-8")
        if "OAuthAccount" not in src and "oauth_account" not in src:
            continue
        scanned.append(rel(path))
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Attribute) and t.attr in _OAUTH_TOKEN_ATTRS:
                        if isinstance(node, ast.AugAssign) or not _is_none(node.value):
                            offences.append(f"{rel(path)}:{node.lineno} {ast.unparse(node)}")
                        else:
                            none_writes += 1
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if name == "OAuthAccount" and any(
                    kw.arg in _OAUTH_TOKEN_ATTRS or kw.arg is None for kw in node.keywords
                ):
                    offences.append(f"{rel(path)}:{node.lineno} {ast.unparse(node)}")
                if name == "values" and any(
                    kw.arg in _OAUTH_TOKEN_ATTRS and not _is_none(kw.value) for kw in node.keywords
                ):
                    offences.append(f"{rel(path)}:{node.lineno} {ast.unparse(node)}")
                if (
                    name == "setattr"
                    and len(node.args) >= 3
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in _OAUTH_TOKEN_ATTRS
                    and not _is_none(node.args[2])
                ):
                    offences.append(f"{rel(path)}:{node.lineno} {ast.unparse(node)}")
    assert "app/services/user_service.py" in scanned, scanned
    # The known-identity branch sweeps both columns to None: proof the scan sees writes.
    assert none_writes >= 2, f"scan saw {none_writes} None writes; vacuous over {scanned}"
    assert not offences, "OAuth provider token written (SEC-013: never stored):\n" + "\n".join(
        offences
    )


class _RecSession:
    """MiniSession over MiniDB that records statements and answers commit/rollback."""

    def __init__(self, db) -> None:
        from tests.safety._minidb import MiniSession

        self._inner = MiniSession(db)
        self.statements: list = []

    async def execute(self, statement, *a, **k):
        self.statements.append(statement)
        return await self._inner.execute(statement, *a, **k)

    async def scalar(self, statement, *a, **k):
        self.statements.append(statement)
        return await self._inner.scalar(statement, *a, **k)

    def add(self, obj, *a, **k) -> None:
        self._inner.add(obj)

    async def delete(self, obj) -> None:
        await self._inner.delete(obj)

    async def flush(self, *a, **k) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _oauth_db(*, existing_link: bool):
    from app.models.oauth_account import OAuthAccount
    from app.models.user import User
    from tests.safety._minidb import MiniDB

    db = MiniDB()
    db.add(
        User(
            id="floor2-oauth-user",
            email="floor2-oauth@example.com",
            username="floor2oauth",
            hashed_password=None,
            role="user",
            tier="free",
            is_active=True,
            email_verified=True,
            mfa_enabled=False,
        )
    )
    if existing_link:
        # A value the previous release wrote during the deploy window.
        db.add(
            OAuthAccount(
                id="floor2-oauth-acct",
                user_id="floor2-oauth-user",
                provider="google",
                provider_user_id="goog-floor2",
                access_token=SENTINEL,
                refresh_token=REFRESH_SENTINEL,
            )
        )
    return db


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_link", [True, False], ids=["known_identity", "link"])
async def test_floor2_both_oauth_branches_leave_the_row_without_tokens(existing_link):
    """Real service over MiniDB: the account row exists, is the user's, and holds no token."""
    from app.services import user_service

    db = _oauth_db(existing_link=existing_link)
    user = await user_service.create_or_link_oauth(
        _RecSession(db),
        "google",
        "goog-floor2",
        "floor2-oauth@example.com",
        email_verified=True,
    )
    assert user is not None and user.id == "floor2-oauth-user"
    [acct] = db.rows["oauth_accounts"]
    assert (acct.user_id, acct.provider, acct.provider_user_id) == (
        "floor2-oauth-user",
        "google",
        "goog-floor2",
    ), "the identity link changed"
    assert (acct.access_token, acct.refresh_token) == (None, None), "a provider token was stored"


def _callback_userinfo():
    from app.core.oauth import OAuthUserInfo

    return OAuthUserInfo(
        provider_user_id="goog-floor2",
        email="floor2-oauth@example.com",
        name="Floor Two",
        avatar_url=None,
        email_verified=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "service_error"])
async def test_floor2_oauth_callback_uses_the_token_for_userinfo_only_and_never_logs_it(
    async_client, log_stream, outcome
):
    """The token dict reaches ``fetch_userinfo`` (positive control) and nothing else."""
    from app.core.oauth import OAUTH_STATE_COOKIE

    token = {"access_token": SENTINEL, "refresh_token": REFRESH_SENTINEL, "id_token": SENTINEL}
    user = _mfa_user("unused")
    user.mfa_enabled = False
    service = AsyncMock(return_value=user)
    if outcome == "service_error":
        service.side_effect = RuntimeError("flush failed")
    fetch = AsyncMock(return_value=_callback_userinfo())
    async_client.cookies.set(OAUTH_STATE_COOKIE, "floor2-state")
    try:
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.auth.exchange_code_for_token", new_callable=AsyncMock, return_value=token
            ),
            patch("app.api.auth.fetch_userinfo", fetch),
            patch("app.api.auth.user_service.create_or_link_oauth", service),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google/callback?code=abc&state=floor2-state",
                follow_redirects=False,
            )
    finally:
        async_client.cookies.clear()
    assert response.status_code == 302, response.text
    fetch.assert_awaited_once()
    assert token in fetch.await_args.args, "fetch_userinfo no longer gets the token (vacuous)"
    service.assert_awaited_once()
    passed = repr(service.await_args)
    assert SENTINEL not in passed and REFRESH_SENTINEL not in passed, passed
    assert not _OAUTH_TOKEN_ATTRS & set(service.await_args.kwargs)
    text = log_stream.getvalue()
    assert "oauth_" in text, "no callback log line reached the handler (vacuous)"
    assert SENTINEL not in text and REFRESH_SENTINEL not in text, text
    assert SENTINEL not in response.headers.get("location", "")


def test_floor2_google_authorize_url_does_not_ask_for_a_refresh_token():
    """``access_type=offline`` requested a refresh token that is then discarded."""
    from urllib.parse import parse_qs, urlsplit

    from app.core.oauth import build_authorize_url

    config = {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "client_id": "floor2-client",
        "scope": "openid email profile",
    }
    with patch("app.core.oauth.get_provider_config", return_value=config):
        url = build_authorize_url("google", "floor2-state")
    query = parse_qs(urlsplit(url).query)
    assert query.get("state") == ["floor2-state"], url  # the URL was really built
    assert "access_type" not in query and "offline" not in url, url
    assert query.get("scope") == ["openid email profile"], "scopes changed"


# ── SEC-014: the Telegram pairing code is a digest at rest ─────────────────


def _digest(code: str) -> str:
    import hashlib

    return hashlib.sha256(code.encode()).hexdigest()


def _telegram_db():
    """User A with no link yet; user B with a pending code (stored as its digest)."""
    from app.models.telegram_link import TelegramLink
    from tests.safety._minidb import MiniDB

    db = MiniDB()
    db.add(
        TelegramLink(
            id="tl-b",
            user_id="floor2-tg-b",
            link_token=_digest("code-of-user-b"),
            verified=False,
        )
    )
    return db


def _stored_values(db) -> list[str]:
    return [
        str(v)
        for bucket in db.rows.values()
        for obj in bucket
        for v in db.row(obj).values()
        if v is not None
    ]


def _bound_values(statement) -> list:
    from sqlalchemy.dialects import postgresql

    return list(statement.compile(dialect=postgresql.dialect()).params.values())


@pytest.mark.asyncio
async def test_floor2_pairing_code_is_stored_and_looked_up_only_as_its_digest(log_stream):
    from app.core.exceptions import TelegramLinkError
    from app.services import telegram_service

    db = _telegram_db()
    session = _RecSession(db)

    code = await telegram_service.generate_link_token(session, "floor2-tg-a")
    digest = _digest(code)
    [link_a] = [o for o in db.rows["telegram_links"] if o.user_id == "floor2-tg-a"]
    assert link_a.link_token == digest and len(digest) == 64
    assert not any(code in v for v in _stored_values(db)), "the plaintext code was stored"

    # Regenerating replaces the digest; the old code stops matching.
    code2 = await telegram_service.generate_link_token(session, "floor2-tg-a")
    assert link_a.link_token == _digest(code2) and code2 != code
    assert not any(code2 in v for v in _stored_values(db))
    with pytest.raises(TelegramLinkError):
        await telegram_service.verify_link(session, code, 4242)

    # Presenting the stored digest is a miss: someone with a dump cannot pair.
    with pytest.raises(TelegramLinkError):
        await telegram_service.verify_link(session, _digest(code2), 4242)
    assert link_a.verified is False and link_a.chat_id is None

    # The real code pairs A, by digest in SQL, and leaves B's pending row alone.
    session.statements.clear()
    assert await telegram_service.verify_link(session, code2, 4242, "floor2") is True
    [lookup] = session.statements
    bound = _bound_values(lookup)
    assert _digest(code2) in bound and code2 not in bound, bound
    assert (link_a.verified, link_a.chat_id, link_a.link_token) == (True, 4242, None)
    [link_b] = [o for o in db.rows["telegram_links"] if o.user_id == "floor2-tg-b"]
    assert (link_b.verified, link_b.chat_id, link_b.link_token) == (
        False,
        None,
        _digest("code-of-user-b"),
    )

    text = log_stream.getvalue()
    assert "telegram_link_token_generated" in text and "telegram_link_verified" in text, text
    for secret in (code, code2, _digest(code), _digest(code2)):
        assert secret not in text, "a pairing code or its digest was logged"


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["valid", "digest", "unknown"])
async def test_floor2_webhook_start_never_logs_the_code(log_stream, which):
    from app.services import telegram_service

    db = _telegram_db()
    presented = {
        "valid": "code-of-user-b",
        "digest": _digest("code-of-user-b"),
        "unknown": "floor2-no-such-code",
    }[which]
    update = {
        "message": {
            "text": f"/start {presented}",
            "chat": {"id": 777},
            "from": {"username": "floor2"},
        }
    }
    reply = await telegram_service.handle_telegram_webhook(_RecSession(db), update)
    [link_b] = db.rows["telegram_links"]
    assert link_b.verified is (which == "valid"), reply
    text = log_stream.getvalue()
    for secret in ("code-of-user-b", _digest("code-of-user-b"), presented):
        assert secret not in text, f"{which}: pairing code or digest logged"


def test_floor2_no_telegram_log_call_carries_a_code():
    """Static: log calls in the two Telegram modules never pass the code, its digest or /start text."""
    import ast

    from tests.safety._source import APP_ROOT, parse

    banned = {"token", "code", "link_token", "deep_link", "text", "update", "message", "body"}
    offences, seen = [], 0
    for rel_path in ("services/telegram_service.py", "api/notifications.py"):
        path = APP_ROOT / rel_path
        for node in ast.walk(parse(path)):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logger"
            ):
                continue
            seen += 1
            for arg in [*node.args[1:], *(kw.value for kw in node.keywords)]:
                names = {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
                names |= {n.attr for n in ast.walk(arg) if isinstance(n, ast.Attribute)}
                if names & banned:
                    offences.append(f"{rel_path}:{node.lineno} {ast.unparse(node)}")
    assert seen >= 3, "no log calls found (vacuous)"
    assert not offences, "\n".join(offences)


# ── revision c3e5a7b9d1f2: nothing lost, downgrade semantics ───────────────

SEC013_REVISION = "c3e5a7b9d1f2"


def _sec013_db():
    import sqlalchemy as sa

    engine = sa.create_engine("sqlite://")
    md = sa.MetaData()
    oauth = sa.Table(
        "oauth_accounts",
        md,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text),
        sa.Column("provider", sa.Text),
        sa.Column("provider_user_id", sa.Text),
        sa.Column("access_token", sa.Text),
        sa.Column("refresh_token", sa.Text),
    )
    tg = sa.Table(
        "telegram_links",
        md,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text),
        sa.Column("chat_id", sa.Integer),
        sa.Column("username", sa.Text),
        sa.Column("verified", sa.Boolean),
        sa.Column("link_token", sa.Text),
    )
    md.create_all(engine)
    conn = engine.connect()
    conn.execute(
        oauth.insert(),
        [
            {
                "id": "o1",
                "user_id": "u1",
                "provider": "google",
                "provider_user_id": "g1",
                "access_token": "enc:v1:" + SENTINEL,
                "refresh_token": "enc:v1:" + REFRESH_SENTINEL,
            },
            {
                "id": "o2",
                "user_id": "u2",
                "provider": "github",
                "provider_user_id": "h2",
                "access_token": None,
                "refresh_token": None,
            },
        ],
    )
    conn.execute(
        tg.insert(),
        [
            {
                "id": "t1",
                "user_id": "u1",
                "chat_id": 11,
                "username": "a",
                "verified": True,
                "link_token": None,
            },
            {
                "id": "t2",
                "user_id": "u2",
                "chat_id": None,
                "username": None,
                "verified": False,
                "link_token": "plaintext-pending-code-0123456789",
            },
        ],
    )
    return conn, oauth, tg


def _rows(conn, table) -> dict[str, dict]:
    return {r["id"]: dict(r) for r in conn.execute(table.select()).mappings()}


def _sec013_revision(monkeypatch, conn):
    import importlib.util

    from tests.safety._source import APP_ROOT

    [path] = (APP_ROOT.parent / "alembic" / "versions").glob(f"{SEC013_REVISION}_*.py")
    spec = importlib.util.spec_from_file_location(f"_floor2_rev_{SEC013_REVISION}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "op", _Op(conn))
    return module


def test_floor2_floor4_sec013_upgrade_nulls_only_the_secrets_and_keeps_every_row(
    monkeypatch, capsys
):
    conn, oauth, tg = _sec013_db()
    before_o, before_t = _rows(conn, oauth), _rows(conn, tg)
    module = _sec013_revision(monkeypatch, conn)
    module.upgrade()
    after_o, after_t = _rows(conn, oauth), _rows(conn, tg)

    assert after_o.keys() == before_o.keys() and after_t.keys() == before_t.keys(), "rows lost"
    for rid, row in after_o.items():
        assert (row["access_token"], row["refresh_token"]) == (None, None)
        keep = ("user_id", "provider", "provider_user_id")
        assert {k: row[k] for k in keep} == {k: before_o[rid][k] for k in keep}
    for rid, row in after_t.items():
        assert row["link_token"] is None
        keep = ("user_id", "chat_id", "username", "verified")
        assert {k: row[k] for k in keep} == {k: before_t[rid][k] for k in keep}, "a link changed"
    out = capsys.readouterr().out
    assert SENTINEL not in out and "plaintext-pending-code" not in out, out

    module.upgrade()  # idempotent
    assert (_rows(conn, oauth), _rows(conn, tg)) == (after_o, after_t)


def test_floor2_sec013_downgrade_restores_no_token_and_nulls_every_digest(monkeypatch, capsys):
    """OAuth: nothing to restore, nothing touched. Telegram: a digest would match as a code."""
    conn, oauth, tg = _sec013_db()
    module = _sec013_revision(monkeypatch, conn)
    module.upgrade()
    # The new release wrote a digest; a straggler old api wrote a ciphertext token.
    conn.execute(tg.update().where(tg.c.id == "t2").values(link_token=_digest("fresh")))
    conn.execute(oauth.update().where(oauth.c.id == "o2").values(access_token="enc:v1:straggler"))
    before_o, before_t = _rows(conn, oauth), _rows(conn, tg)
    capsys.readouterr()
    module.downgrade()
    assert _rows(conn, oauth) == before_o, "the downgrade changed oauth_accounts"
    after_t = _rows(conn, tg)
    assert after_t.keys() == before_t.keys()
    assert all(r["link_token"] is None for r in after_t.values()), "a digest survived downgrade"
    assert after_t["t1"]["verified"] is True and after_t["t1"]["chat_id"] == 11
    out = capsys.readouterr().out
    assert _digest("fresh") not in out and "straggler" not in out, out
    doc = module.__doc__ or ""
    assert "cannot be restored" in doc, "the docstring must say the tokens cannot be restored"
