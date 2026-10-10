"""AI-051 (R-026): long-lived ``claude setup-token`` token for the worker."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from app.agents.claude_code import ClaudeCodeAdapter
from app.core.exceptions import AgentError

TOKEN = "sk-ant-oat01-SENTINEL-eeeeeeee5555"
TOKEN2 = "sk-ant-oat01-ROTATED-ffffffff6666"
ENV = "CLAUDE_CODE_OAUTH_TOKEN"


def _proc(rc, out=b"", err=b""):
    p = MagicMock()
    p.returncode = rc
    p.communicate = AsyncMock(return_value=(out, err))
    return p


def _adapter(creds=None):
    with patch("app.agents.claude_code.get_effective_setting", return_value="claude"):
        return ClaudeCodeAdapter(credentials_json=creds)


def _token_file(tmp_path, monkeypatch, content):
    f = tmp_path / "oauth-token"
    f.write_text(content)
    monkeypatch.setenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", str(f))
    monkeypatch.delenv("CLAUDE_HOST_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv(ENV, raising=False)
    return f


async def _run(adapter, proc):
    captured = {}

    async def fake(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env")
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake):
        try:
            return await adapter._run_claude_code("p"), captured
        except AgentError as e:
            return e, captured


@pytest.mark.asyncio
class TestHostOAuthToken:
    async def test_token_goes_to_subprocess_env_only(self, tmp_path, monkeypatch):
        _token_file(tmp_path, monkeypatch, TOKEN + "\n")
        result, cap = await _run(_adapter(), _proc(0, b"OK"))
        assert result == "OK"
        assert cap["env"][ENV] == TOKEN
        assert all(TOKEN not in str(a) for a in cap["args"])
        assert ENV not in os.environ

    async def test_per_user_credentials_win(self, tmp_path, monkeypatch):
        _token_file(tmp_path, monkeypatch, TOKEN)
        user = {"claudeAiOauth": {"accessToken": "user-token-SENTINEL-1234567890"}}
        result, cap = await _run(_adapter(user), _proc(0, b"OK"))
        assert result == "OK"
        assert ENV not in cap["env"]
        assert "CLAUDE_CONFIG_DIR" in cap["env"]

    @pytest.mark.parametrize("content", ["", "  \n"])
    async def test_empty_file_is_ignored(self, tmp_path, monkeypatch, content):
        _token_file(tmp_path, monkeypatch, content)
        result, cap = await _run(_adapter(), _proc(0, b"OK"))
        assert result == "OK"
        assert cap["env"] is None

    async def test_missing_file_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", str(tmp_path / "nope"))
        monkeypatch.delenv(ENV, raising=False)
        result, cap = await _run(_adapter(), _proc(0, b"OK"))
        assert result == "OK"
        assert cap["env"] is None

    async def test_unset_env_is_ignored(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", raising=False)
        _, cap = await _run(_adapter(), _proc(0, b"OK"))
        assert cap["env"] is None

    async def test_token_is_reread_every_call(self, tmp_path, monkeypatch):
        f = _token_file(tmp_path, monkeypatch, TOKEN)
        a = _adapter()
        _, first = await _run(a, _proc(0, b"OK"))
        f.write_text(TOKEN2)
        _, second = await _run(a, _proc(0, b"OK"))
        assert first["env"][ENV] == TOKEN
        assert second["env"][ENV] == TOKEN2

    async def test_token_echoed_by_cli_is_redacted(self, tmp_path, monkeypatch):
        _token_file(tmp_path, monkeypatch, TOKEN)
        out = f"boom: token {TOKEN} rejected".encode()
        result, _ = await _run(_adapter(), _proc(1, out, f"err {TOKEN}".encode()))
        assert isinstance(result, AgentError)
        assert TOKEN not in str(result)
        assert "boom" in str(result)

    async def test_auth_failure_with_token_does_not_fall_back(self, tmp_path, monkeypatch):
        _token_file(tmp_path, monkeypatch, TOKEN)
        creds = tmp_path / ".credentials.json"
        creds.write_text('{"claudeAiOauth": {"accessToken": "x"}}')
        monkeypatch.setenv("CLAUDE_HOST_CREDENTIALS_FILE", str(creds))
        calls = []

        async def fake(*args, **kwargs):
            calls.append(kwargs.get("env"))
            return _proc(1, b"401 token has expired")

        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(AgentError) as e:
                await _adapter()._run_claude_code("p")
        assert len(calls) == 1
        assert TOKEN not in str(e.value)

    async def test_logs_never_contain_token(self, tmp_path, monkeypatch):
        _token_file(tmp_path, monkeypatch, TOKEN)
        with structlog.testing.capture_logs() as logs:
            await _run(_adapter(), _proc(0, b"OK"))
        assert TOKEN not in repr(logs)
        assert any(entry["event"] == "claude_code_using_host_oauth_token" for entry in logs)
