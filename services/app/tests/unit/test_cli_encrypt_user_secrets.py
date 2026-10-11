"""`python -m app.cli encrypt-user-secrets` (SEC-06, GL#20)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app import cli
from app.config import settings
from app.core import secret_box


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(
        settings, "settings_encryption_key", SecretStr(Fernet.generate_key().decode())
    )


def _factory(rows):
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm), session


def _rows():
    return [
        SimpleNamespace(
            user_id="u1", settings_json={"openai_api_key": "sk-legacy-1", "openai_model": "x"}
        ),
        SimpleNamespace(
            user_id="u2", settings_json={"openai_api_key": secret_box.encrypt("sk-two-2")}
        ),
        SimpleNamespace(user_id="u3", settings_json={"other": 1}),
    ]


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(key, monkeypatch, capsys):
    rows = _rows()
    factory, session = _factory(rows)
    monkeypatch.setattr(cli, "async_session_factory", factory)
    monkeypatch.setattr(cli, "engine", MagicMock(dispose=AsyncMock()))
    assert await cli._encrypt_user_secrets(apply=False) == 0
    assert rows[0].settings_json["openai_api_key"] == "sk-legacy-1"
    session.commit.assert_not_awaited()
    out = capsys.readouterr().out
    assert "would encrypt" in out and "sk-legacy-1" not in out


@pytest.mark.asyncio
async def test_apply_encrypts_legacy_and_is_idempotent(key, monkeypatch):
    rows = _rows()
    factory, session = _factory(rows)
    monkeypatch.setattr(cli, "async_session_factory", factory)
    monkeypatch.setattr(cli, "engine", MagicMock(dispose=AsyncMock()))
    assert await cli._encrypt_user_secrets(apply=True) == 0
    stored = rows[0].settings_json["openai_api_key"]
    assert stored.startswith(secret_box.PREFIX)
    assert secret_box.decrypt(stored) == "sk-legacy-1"
    assert rows[0].settings_json["openai_model"] == "x"
    assert secret_box.decrypt(rows[1].settings_json["openai_api_key"]) == "sk-two-2"
    session.commit.assert_awaited()
    before = rows[0].settings_json["openai_api_key"]
    await cli._encrypt_user_secrets(apply=True)
    assert rows[0].settings_json["openai_api_key"] == before


@pytest.mark.asyncio
async def test_refuses_without_key(monkeypatch, capsys):
    monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
    assert await cli._encrypt_user_secrets(apply=True) == 1
    assert "SETTINGS_ENCRYPTION_KEY" in capsys.readouterr().err
