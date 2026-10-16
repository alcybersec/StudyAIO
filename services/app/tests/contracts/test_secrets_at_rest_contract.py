"""Contract test for `models.secrets-at-rest` v1 rules (docs/CONTRACTS.md, M34-S2-SEC-005).

OAuth and Google Calendar tokens and the TOTP seed (``users.mfa_secret``) are
encrypted at rest with the scheme the per-user AI credentials already use
(``app.core.secret_box``, SEC-06). The entry was first recorded as
``models.third-party-tokens v1`` and renamed before implementation when the
seed joined it. Pins:

1. ``secret_box.EncryptedText`` is a ``TypeDecorator`` over ``Text`` with the
   entry's constructor and two hooks, signature for signature.
2. The five columns the entry lists use it, with the listed nullability, each
   naming itself as ``EncryptedText(column="<table>.<column>")``.
3. Under the suite's (public, all-zero) test key: a write is ``enc:v1:``
   ciphertext that does not contain the plaintext; a read decrypts it; legacy
   plaintext reads back as is; a tampered value reads as ``None``, does not
   raise, and the log line carries the column's name (C3) and neither the
   plaintext nor the ciphertext.
4. An Alembic revision encrypts all three tables on upgrade and decrypts on
   downgrade; ``encrypt-user-secrets`` (the rotation command) covers them.
   Upgrade calls ``secret_box.check_startup()`` before altering anything, so a
   multi-user instance with no key aborts (C4). Downgrade checks the key and
   both narrowed widths and never commits part-way; the revision docstring and
   ``docs/security/`` say it removes at-rest protection (C5). Every engine
   passes ``hide_parameters=True`` (C6, a precondition).
5. No API response model has a token or seed field, and the export excludes
   them (floor 2). **Green today**: it pins what already holds.
6. Unreadable seed, MFA fails closed: ``mfa_secret`` is assigned only by
   ``enable_mfa``/``disable_mfa``/``clear_mfa`` (**green today**); a TOTP code
   against a ``None`` seed is refused exactly like a wrong code on both sign-in
   routes, throttled, and logged without a value; ``disable_mfa`` refuses with
   the entry's message and changes nothing.
7. Unreadable calendar token (C7): a ``None`` access token with a refresh
   token refreshes and persists; both ``None`` raise
   ``CalendarSyncError("reconnect required")`` with no Google call and a
   ``sync_id``-only log; ``disconnect_calendar`` skips the revoke on ``None``
   and sends the token with ``data=``, never ``params=``.

Red until ``backend`` lands ``EncryptedText``, the CLI change, the
unreadable-seed rules and the calendar rules, and ``data`` lands the model
types, the migration and ``hide_parameters`` in ``alembic/env.py``
(M34-S2-SEC-005). C3-C7 are the required changes of the safety review,
``docs/gates/M34/contracts-safety.md``.
"""

import ast
import inspect
import re
import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel
from structlog.testing import capture_logs

from tests.contracts._weakspot_docs import (
    APP_ROOT,
    contract_section,
    python_block,
    signature,
    table_rows,
    top_level,
)

HEADING = "### models.secrets-at-rest v2"
TOKEN_FIELD_NAMES = {"access_token", "refresh_token", "sync_token", "mfa_secret"}
SECRET = "ya29.contract-test-token-value"


@pytest.fixture(scope="module")
def section() -> str:
    return contract_section(HEADING)


@pytest.fixture(scope="module")
def rows(section) -> list[list[str]]:
    found = table_rows(section, "Table")
    assert len(found) == 5, f"{HEADING} lists {len(found)} columns; expected 5"
    return found


@pytest.fixture(scope="module")
def tables():
    import app.models  # noqa: F401  (registers every model on the metadata)
    from app.core.database import Base

    return Base.metadata.tables


@pytest.fixture(scope="module")
def encrypted_text():
    from app.core import secret_box

    cls = getattr(secret_box, "EncryptedText", None)
    assert cls is not None, "app.core.secret_box.EncryptedText does not exist yet (`backend`)"
    return cls


# --- 1. the type ----------------------------------------------------------------


def test_encrypted_text_is_a_text_type_decorator(encrypted_text):
    from sqlalchemy import Text
    from sqlalchemy.types import TypeDecorator

    assert issubclass(encrypted_text, TypeDecorator)
    assert isinstance(encrypted_text(column="users.mfa_secret").impl, Text)
    assert encrypted_text.cache_ok is True


def test_encrypted_text_hooks_match_the_entry(section, encrypted_text):
    block = python_block(section, HEADING)
    contract_cls = top_level(block)["EncryptedText"]
    mine_cls = top_level(ast.parse(inspect.getsource(encrypted_text)))["EncryptedText"]

    def methods(cls: ast.ClassDef) -> dict[str, tuple]:
        return {
            n.name: signature(n)
            for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    want, got = methods(contract_cls), methods(mine_cls)
    diff = {n: (want[n], got.get(n)) for n in want if want[n] != got.get(n)}
    assert not diff, f"EncryptedText hooks differ from {HEADING}: {diff}"


# --- 2. the columns -------------------------------------------------------------


def test_token_columns_use_encrypted_text(rows, tables, encrypted_text):
    problems = []
    for table, column, type_spec, null, _notes in rows:
        table, column = table.strip("`"), column.strip("`")
        assert type_spec.strip("`") == "EncryptedText", type_spec
        col = tables[table].columns.get(column)
        if col is None:
            problems.append(f"{table}.{column}: missing")
            continue
        if not isinstance(col.type, encrypted_text):
            problems.append(f"{table}.{column}: {col.type!r} is not EncryptedText")
        elif getattr(col.type, "column", None) != f"{table}.{column}":
            named = getattr(col.type, "column", None)
            problems.append(f"{table}.{column}: EncryptedText(column={named!r})")
        if col.nullable != (null == "yes"):
            problems.append(f"{table}.{column}: nullable={col.nullable}, entry says {null!r}")
    assert not problems, f"{HEADING} disagrees with the models:\n" + "\n".join(problems)


# --- 3. behaviour under the test key --------------------------------------------


@pytest.fixture
def column_type(encrypted_text):
    from sqlalchemy.dialects import postgresql

    return encrypted_text(column="users.mfa_secret"), postgresql.dialect()


def test_write_is_ciphertext_without_the_plaintext(column_type):
    typ, dialect = column_type
    stored = typ.process_bind_param(SECRET, dialect)
    assert stored.startswith("enc:v1:")
    assert SECRET not in stored


def test_write_encrypts_a_value_that_only_looks_encrypted(column_type):
    typ, dialect = column_type
    stored = typ.process_bind_param("enc:v1:not-really", dialect)
    assert stored.startswith("enc:v1:") and "not-really" not in stored


def test_none_passes_through_both_ways(column_type):
    typ, dialect = column_type
    assert typ.process_bind_param(None, dialect) is None
    assert typ.process_result_value(None, dialect) is None


def test_read_round_trips(column_type):
    typ, dialect = column_type
    assert typ.process_result_value(typ.process_bind_param(SECRET, dialect), dialect) == SECRET


def test_legacy_plaintext_reads_back_as_is(column_type):
    typ, dialect = column_type
    assert typ.process_result_value(SECRET, dialect) == SECRET


def test_tampered_ciphertext_reads_as_none_and_logs_no_value(column_type):
    typ, dialect = column_type
    stored = typ.process_bind_param(SECRET, dialect)
    tampered = stored[:-6] + ("A" if stored[-6] != "A" else "B") + stored[-5:]
    with capture_logs() as logs:
        assert typ.process_result_value(tampered, dialect) is None
    hits = [entry for entry in logs if entry.get("event") == "secret_at_rest_undecryptable"]
    assert hits, [entry.get("event") for entry in logs]
    for entry in hits:
        assert entry.get("column") == "users.mfa_secret", entry
        extra = set(entry) - {"event", "log_level", "column"}
        assert not extra, f"secret_at_rest_undecryptable carries more than column: {sorted(extra)}"
    dumped = repr(logs)
    assert SECRET not in dumped and tampered not in dumped and stored[7:40] not in dumped


# --- 4. migration and rotation ---------------------------------------------------


def _function_source(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    return ""


@pytest.fixture(scope="module")
def revision() -> tuple[str, ast.Module, str, str]:
    candidates = []
    for path in sorted((APP_ROOT / "alembic" / "versions").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        up, down = _function_source(tree, "upgrade"), _function_source(tree, "downgrade")
        if all(t in up for t in ("oauth_accounts", "calendar_syncs")) and "encrypt(" in up:
            candidates.append((path.name, tree, up, down))
    assert candidates, "no Alembic revision encrypts oauth_accounts and calendar_syncs (`data`)"
    assert len(candidates) == 1, f"more than one secrets revision: {[c[0] for c in candidates]}"
    return candidates[0]


def _helpers_inlined(tree: ast.Module, source: str) -> str:
    """``source`` plus every module-level helper it calls, one level deep."""
    helpers = {
        n.name: ast.unparse(n)
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name not in ("upgrade", "downgrade")
    }
    called = {
        n.func.id
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    return "\n".join([source, *(helpers[c] for c in sorted(called & set(helpers)))])


def test_a_revision_encrypts_on_upgrade_and_decrypts_on_downgrade(revision):
    name, tree, up, down = revision
    up, down = _helpers_inlined(tree, up), _helpers_inlined(tree, down)
    assert "decrypt(" in down, f"{name}: downgrade must decrypt back to plaintext"
    for direction, source in (("upgrade", up), ("downgrade", down)):
        missing = [t for t in ("oauth_accounts", "calendar_syncs", "mfa_secret") if t not in source]
        assert not missing, f"{name}: {direction} does not cover {missing}"


def test_upgrade_checks_the_key_before_altering_anything(revision):
    """C4: a multi-user instance with no key aborts, as ``check_startup`` does."""
    name, _tree, up, _down = revision
    assert "check_startup(" in up, f"{name}: upgrade must call secret_box.check_startup() (C4)"
    first_change = min(
        (up.find(t) for t in ("alter_column", "execute(", "update(") if t in up), default=-1
    )
    assert first_change == -1 or up.find("check_startup(") < first_change, (
        f"{name}: upgrade alters or writes before secret_box.check_startup() (C4)"
    )


def test_downgrade_checks_the_key_and_both_widths_and_never_commits(revision):
    """C5: abort with no key or on an over-long value; one transaction."""
    name, tree, _up, down = revision
    down = _helpers_inlined(tree, down)
    assert "is_configured(" in down, f"{name}: downgrade must abort with no key (C5)"
    assert "len(" in down, f"{name}: downgrade must check decrypted lengths (C5)"
    for width in ("1000", "64"):
        assert width in down, f"{name}: downgrade does not narrow to / check width {width} (C5)"
    assert "commit(" not in down.lower(), f"{name}: downgrade commits part-way (C5)"


def test_downgrade_is_documented_as_removing_protection(revision):
    """C5: the revision docstring and ``docs/security/`` both say so."""
    name, tree, _up, _down = revision
    phrase = "removes at-rest protection"
    doc = " ".join((ast.get_docstring(tree) or "").split()).lower()
    assert phrase in doc, f"{name}: the module docstring must say the downgrade {phrase} (C5)"
    security = APP_ROOT.parents[1] / "docs" / "security"
    texts = [
        " ".join(p.read_text(encoding="utf-8").split()).lower()
        for p in sorted(security.glob("*.md"))
    ]
    assert any(phrase in t for t in texts), (
        f"docs/security/ does not say the downgrade {phrase} (`safety`, C5)"
    )


def _engine_calls() -> list[tuple[str, ast.Call]]:
    found = []
    paths = [*sorted((APP_ROOT / "app").rglob("*.py")), APP_ROOT / "alembic" / "env.py"]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in {
                "create_engine",
                "create_async_engine",
                "engine_from_config",
                "async_engine_from_config",
            }:
                found.append((f"{path.relative_to(APP_ROOT).as_posix()}:{node.lineno}", node))
    return found


def test_every_engine_hides_bound_parameters():
    """C6, a precondition of SEC-005: error text never carries bound values."""
    calls = _engine_calls()
    assert any(where.startswith("app/core/database.py") for where, _ in calls), calls
    assert any(where.startswith("alembic/env.py") for where, _ in calls), calls
    bare = [
        where
        for where, call in calls
        if not any(
            k.arg == "hide_parameters"
            and isinstance(k.value, ast.Constant)
            and k.value.value is True
            for k in call.keywords
        )
    ]
    assert not bare, f"engines without hide_parameters=True (floor 2, C6): {bare}"


def test_rotation_command_covers_all_three_tables():
    from app import cli

    source = inspect.getsource(cli)
    wanted = {
        "oauth_accounts": ("OAuthAccount", "oauth_accounts"),
        "calendar_syncs": ("CalendarSync", "calendar_syncs"),
        "users.mfa_secret": ("mfa_secret",),
    }
    missing = [k for k, names in wanted.items() if not any(n in source for n in names)]
    assert not missing, f"`encrypt-user-secrets` does not re-key {missing} (`backend`)"


# --- 5. never returned (green today) ---------------------------------------------


def _field_names(model: type[BaseModel], seen: set[type]) -> set[str]:
    if model in seen:
        return set()
    seen.add(model)
    names: set[str] = set()
    for name, field in model.model_fields.items():
        names.add(field.alias or name)
        names.add(name)
        for arg in _models_in(field.annotation):
            names |= _field_names(arg, seen)
    return names


def _models_in(annotation) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for a in typing.get_args(annotation) for m in _models_in(a)]


def test_no_response_model_carries_a_token_field():
    from fastapi.routing import APIRoute

    from app.main import app

    leaks = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.response_model is not None:
            for model in _models_in(route.response_model):
                hit = _field_names(model, set()) & TOKEN_FIELD_NAMES
                if hit:
                    leaks.append(f"{sorted(route.methods)} {route.path}: {sorted(hit)}")
    assert not leaks, "response models expose token fields (floor 2):\n" + "\n".join(leaks)


def test_export_still_excludes_token_columns():
    from app.services.account_service import EXPORT_EXCLUDED_COLUMNS

    assert {
        "access_token",
        "refresh_token",
        "mfa_secret",
        "backup_codes",
    } <= EXPORT_EXCLUDED_COLUMNS


def test_entry_names_exactly_the_five_columns(rows):
    named = {(r[0].strip("`"), r[1].strip("`")) for r in rows}
    assert named == {
        ("oauth_accounts", "access_token"),
        ("oauth_accounts", "refresh_token"),
        ("calendar_syncs", "access_token"),
        ("calendar_syncs", "refresh_token"),
        ("users", "mfa_secret"),
    }
    assert re.search(r"`calendar_syncs\.sync_token` is", contract_section(HEADING))


# --- 6. unreadable TOTP seed: MFA fails closed -----------------------------------

MFA_SECRET_WRITERS = {"enable_mfa", "disable_mfa", "clear_mfa"}
UNAVAILABLE_MESSAGE = (
    "MFA secret unavailable; sign in with a backup code and ask an administrator to reset MFA"
)
SEED = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


def test_entry_states_the_unavailable_message():
    flat = " ".join(contract_section(HEADING).split())
    assert f'ValueError("{UNAVAILABLE_MESSAGE}")' in flat


def _mfa_secret_assignments() -> list[str]:
    """Every ``<x>.mfa_secret = …`` under ``app/``, as ``path:function``."""
    found = []
    for path in sorted((APP_ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                    targets = [node.target]
                if any(isinstance(t, ast.Attribute) and t.attr == "mfa_secret" for t in targets):
                    found.append(f"{path.relative_to(APP_ROOT).as_posix()}:{func.name}")
    return found


def test_mfa_secret_is_written_only_by_the_three_mfa_functions():
    writers = _mfa_secret_assignments()
    stray = [
        w
        for w in writers
        if not (
            w.startswith("app/services/user_service.py:")
            and w.split(":", 1)[1] in MFA_SECRET_WRITERS
        )
    ]
    assert not stray, f"mfa_secret assigned outside enable/disable/clear_mfa: {stray}"


def _mfa_user(make_user, *, secret: str | None):
    import json

    return make_user(
        id="user-mfa-001",
        email="mfa@example.com",
        mfa_enabled=True,
        mfa_secret=secret,
        backup_codes=json.dumps(["digest-a", "digest-b"]),
    )


def _only_user_id(logs: list[dict], event: str) -> list[dict]:
    hits = [entry for entry in logs if entry.get("event") == event]
    for entry in hits:
        extra = set(entry) - {"event", "log_level", "user_id"}
        assert not extra, f"{event} carries more than user_id: {sorted(extra)}"
    return hits


@pytest.fixture
def throttle():
    with (
        patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock) as delay,
        patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock) as record,
        patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock) as clear,
    ):
        yield MagicMock(apply_delay=delay, record_failure=record, clear=clear)


async def _password_login(client, user):
    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        return_value=user,
    ):
        return await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "TestPass1!", "totp_code": "123456"},
        )


async def test_password_login_with_unreadable_seed_fails_closed(async_client, make_user, throttle):
    # The reference: a readable seed and a code that is wrong for it.
    wrong = await _password_login(async_client, _mfa_user(make_user, secret=SEED))
    throttle.record_failure.reset_mock()

    user = _mfa_user(make_user, secret=None)
    with capture_logs() as logs:
        response = await _password_login(async_client, user)

    assert response.status_code == wrong.status_code
    assert 400 <= response.status_code < 500
    assert response.json() == wrong.json(), "an unreadable seed must look like a wrong code"
    assert "access_token" not in response.cookies
    throttle.record_failure.assert_awaited_once_with(user.email)
    assert user.mfa_enabled is True
    hits = _only_user_id(logs, "mfa_secret_unavailable")
    assert hits and hits[0].get("user_id") == user.id, (
        "the login route does not log `mfa_secret_unavailable` (`backend`)"
    )


async def _oauth_mfa(client, user):
    from app.core.auth import MFA_PENDING_COOKIE, create_mfa_pending_token

    client.cookies.set(MFA_PENDING_COOKIE, create_mfa_pending_token(user.id))
    try:
        with patch(
            "app.api.auth.user_service.get_user_by_id",
            new_callable=AsyncMock,
            return_value=user,
        ):
            return await client.post("/api/auth/oauth/mfa", json={"totp_code": "123456"})
    finally:
        client.cookies.clear()


async def test_oauth_mfa_with_unreadable_seed_fails_closed(async_client, make_user, throttle):
    wrong = await _oauth_mfa(async_client, _mfa_user(make_user, secret=SEED))
    throttle.record_failure.reset_mock()

    user = _mfa_user(make_user, secret=None)
    with capture_logs() as logs:
        response = await _oauth_mfa(async_client, user)

    assert response.status_code == wrong.status_code
    assert 400 <= response.status_code < 500
    assert response.json() == wrong.json(), "an unreadable seed must look like a wrong code"
    assert "access_token" not in response.cookies
    throttle.record_failure.assert_awaited_once_with(user.email)
    assert user.mfa_enabled is True
    hits = _only_user_id(logs, "mfa_secret_unavailable")
    assert hits and hits[0].get("user_id") == user.id, (
        "the OAuth MFA route does not log `mfa_secret_unavailable` (`backend`)"
    )


async def test_disable_mfa_with_unreadable_seed_refuses_and_changes_nothing(
    make_user, mock_session
):
    from app.services import user_service

    user = _mfa_user(make_user, secret=None)
    before = (
        user.mfa_enabled,
        user.mfa_secret,
        user.backup_codes,
        user.tokens_valid_from,
    )
    with (
        patch.object(user_service, "get_user_by_id", new=AsyncMock(return_value=user)),
        capture_logs() as logs,
        pytest.raises(ValueError) as caught,
    ):
        await user_service.disable_mfa(mock_session, user.id, "123456")

    assert str(caught.value) == UNAVAILABLE_MESSAGE
    after = (
        user.mfa_enabled,
        user.mfa_secret,
        user.backup_codes,
        user.tokens_valid_from,
    )
    assert after == before, "disable_mfa changed the account while refusing"
    hits = _only_user_id(logs, "mfa_secret_unavailable")
    assert hits and hits[0].get("user_id") == user.id


# --- 7. unreadable calendar token (C7) ------------------------------------------


def _cal_sync(*, access: str | None, refresh: str | None):
    from types import SimpleNamespace

    return SimpleNamespace(
        id="sync-0001",
        user_id="user-cal-001",
        google_calendar_id="primary",
        sync_direction="bidirectional",
        access_token=access,
        refresh_token=refresh,
        sync_token=None,
    )


def _returning(session, cal_sync) -> None:
    session.execute.return_value.scalar_one_or_none.return_value = cal_sync


async def test_none_access_token_with_refresh_token_refreshes_and_persists(mock_session):
    from google.oauth2.credentials import Credentials

    from app.services import gcal_service

    cal = _cal_sync(access=None, refresh="1//contract-refresh")
    _returning(mock_session, cal)
    order: list[str] = []
    listing = MagicMock()
    listing.execute.return_value = {"items": []}
    service = MagicMock()
    service.events.return_value.list.side_effect = lambda **_kw: order.append("list") or listing

    def fake_refresh(self, _request):
        order.append("refresh")
        self.token = "ya29.fresh"

    with (
        patch("googleapiclient.discovery.build", return_value=service),
        patch.object(Credentials, "refresh", autospec=True, side_effect=fake_refresh),
    ):
        await gcal_service.pull_events(mock_session, cal.user_id, cal.id)

    assert order[:2] == ["refresh", "list"], f"refresh must precede the first Google call: {order}"
    assert cal.access_token == "ya29.fresh", "the refreshed access token was not persisted"
    mock_session.flush.assert_awaited()


@pytest.mark.parametrize("entry_point", ["push_events", "pull_events"])
async def test_both_tokens_none_is_reconnect_required(mock_session, entry_point):
    from google.oauth2.credentials import Credentials

    from app.core.exceptions import CalendarSyncError
    from app.services import gcal_service

    cal = _cal_sync(access=None, refresh=None)
    _returning(mock_session, cal)
    service = MagicMock()
    with (
        patch("googleapiclient.discovery.build", return_value=service),
        patch.object(Credentials, "refresh", autospec=True) as refresh,
        capture_logs() as logs,
        pytest.raises(CalendarSyncError) as caught,
    ):
        await getattr(gcal_service, entry_point)(mock_session, cal.user_id, cal.id)

    assert str(caught.value) == "reconnect required"
    refresh.assert_not_called()
    assert not service.events.called, "a Google call was made with no usable token"
    assert cal.access_token is None and cal.refresh_token is None, "the row was written"
    hits = [e for e in logs if e.get("event") == "calendar_reconnect_required"]
    assert hits, [e.get("event") for e in logs]
    for entry in hits:
        assert entry.get("sync_id") == cal.id
        extra = set(entry) - {"event", "log_level", "sync_id"}
        assert not extra, f"calendar_reconnect_required carries more than sync_id: {sorted(extra)}"


def _http_client() -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    return client


async def test_disconnect_with_none_token_skips_revoke_and_still_deletes(mock_session):
    from app.services import gcal_service

    cal = _cal_sync(access=None, refresh="1//contract-refresh")
    _returning(mock_session, cal)
    client = _http_client()
    with patch("httpx.AsyncClient", return_value=client):
        assert await gcal_service.disconnect_calendar(mock_session, cal.user_id, cal.id) is True
    client.post.assert_not_awaited()
    mock_session.delete.assert_awaited_once_with(cal)


async def test_revoke_sends_the_token_in_the_body_not_the_url(mock_session):
    from app.services import gcal_service

    cal = _cal_sync(access="ya29.contract-live", refresh="1//contract-refresh")
    _returning(mock_session, cal)
    client = _http_client()
    with patch("httpx.AsyncClient", return_value=client):
        assert await gcal_service.disconnect_calendar(mock_session, cal.user_id, cal.id) is True
    client.post.assert_awaited_once()
    args, kwargs = client.post.await_args
    assert "params" not in kwargs, "the token must not go in the query string"
    assert kwargs.get("data") == {"token": "ya29.contract-live"}
    assert "ya29.contract-live" not in repr(args), "the token is in the URL"
