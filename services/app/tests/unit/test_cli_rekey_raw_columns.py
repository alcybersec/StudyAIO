"""`encrypt-user-secrets` over the five secrets-at-rest columns (M34-S2-SEC-005, C1).

The command works on raw stored strings through Core, never the ORM attribute:
an unreadable value must be left byte-for-byte as stored and reported.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app import cli
from app.config import settings
from app.core import secret_box

OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()
FOREIGN = Fernet.generate_key().decode()


def _under(key: str, plaintext: str) -> str:
    return secret_box.PREFIX + Fernet(key.encode()).encrypt(plaintext.encode()).decode()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _session(stored: dict[tuple[str, str], list[tuple[str, str | None]]]):
    """A session whose SELECTs return ``stored`` and which records UPDATEs."""
    session = MagicMock()

    async def execute(stmt):
        text = str(stmt)
        if text.startswith("SELECT"):
            for (table, column), rows in stored.items():
                if f"FROM {table}" in text and f"{table}.{column}" in text:
                    return _Result(rows)
            raise AssertionError(text)
        return MagicMock()

    session.execute = AsyncMock(side_effect=execute)
    return session


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(f"{NEW},{OLD}"))


@pytest.mark.asyncio
async def test_rekey_encrypts_plaintext_rotates_old_and_leaves_the_rest(keys):
    current = _under(NEW, "current")
    stored = {
        ("oauth_accounts", "access_token"): [
            ("o1", "plain-token"),
            ("o2", _under(OLD, "old-token")),
            ("o3", current),
        ],
        ("oauth_accounts", "refresh_token"): [("o1", None)],
        ("calendar_syncs", "access_token"): [("c1", _under(FOREIGN, "lost"))],
        ("calendar_syncs", "refresh_token"): [],
        ("users", "mfa_secret"): [("u1", "JBSWY3DPEHPK3PXP")],
    }
    session = _session(stored)

    encrypted, rotated, unreadable = await cli._rekey_raw_columns(session, apply=True)

    assert (encrypted, rotated, unreadable) == (2, 1, 1)
    written = {}
    for stmt_call in session.execute.await_args_list:
        stmt = stmt_call.args[0]
        if str(stmt).startswith("UPDATE"):
            params = stmt.compile().params
            written[(stmt.table.name, params["id_1"])] = next(
                v for k, v in params.items() if k != "id_1"
            )
    assert set(written) == {("oauth_accounts", "o1"), ("oauth_accounts", "o2"), ("users", "u1")}
    for value in written.values():
        assert secret_box.needs_rotation(value) is False
    assert secret_box.decrypt(written[("oauth_accounts", "o2")]) == "old-token"
    # The unreadable foreign value and the current-key value were never written.
    assert ("calendar_syncs", "c1") not in written
    assert ("oauth_accounts", "o3") not in written


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(keys):
    stored = {key: [] for key in cli.RAW_SECRET_COLUMNS}
    stored[("users", "mfa_secret")] = [("u1", "JBSWY3DPEHPK3PXP")]
    session = _session(stored)

    counts = await cli._rekey_raw_columns(session, apply=False)

    assert counts == (1, 0, 0)
    assert all(not str(c.args[0]).startswith("UPDATE") for c in session.execute.await_args_list)


@pytest.mark.asyncio
async def test_command_exits_nonzero_and_names_no_value_when_unreadable(keys, monkeypatch, capsys):
    secret = "lost-token-value"
    stored = {key: [] for key in cli.RAW_SECRET_COLUMNS}
    stored[("calendar_syncs", "access_token")] = [("c1", _under(FOREIGN, secret))]
    session = _session(stored)
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    real = session.execute.side_effect

    async def execute(stmt):
        if "user_settings" in str(stmt):
            return empty
        return await real(stmt)

    session.execute = AsyncMock(side_effect=execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(cli, "async_session_factory", MagicMock(return_value=cm))
    monkeypatch.setattr(cli, "engine", MagicMock(dispose=AsyncMock()))

    assert await cli._encrypt_user_secrets(apply=True) == 2

    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "unreadable: 1" in out
    assert "calendar_syncs.access_token row c1" in out
    assert secret not in out and "enc:v1:" not in out
    assert "Do NOT drop the old key" in captured.err
