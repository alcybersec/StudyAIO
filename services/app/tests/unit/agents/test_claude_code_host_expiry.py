"""SAFETY-046: never retry with an already-expired host access token."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.claude_code import ClaudeCodeAdapter
from app.core.exceptions import AgentError

TOKEN = "host-token-SENTINEL-cccccccc3333"
REFRESH = "host-refresh-SENTINEL-dddddddd4444"
AUTH_STDOUT = b"Failed to authenticate. API Error: 401 OAuth access token has been revoked."
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)


def _proc(rc, out=b""):
    p = MagicMock()
    p.returncode = rc
    p.communicate = AsyncMock(return_value=(out, b""))
    return p


def _adapter(tmp_path, monkeypatch, oauth):
    host = tmp_path / ".credentials.json"
    host.write_text(json.dumps({"claudeAiOauth": oauth}))
    monkeypatch.setenv("CLAUDE_HOST_CREDENTIALS_FILE", str(host))
    with patch("app.agents.claude_code.get_effective_setting", return_value="claude"):
        return ClaudeCodeAdapter()


async def _run(adapter):
    calls = []

    async def fake(*args, **kwargs):
        calls.append(kwargs.get("env"))
        return _proc(1, AUTH_STDOUT) if len(calls) == 1 else _proc(0, b"OK")

    with (
        patch("asyncio.create_subprocess_exec", side_effect=fake),
        patch("app.agents.claude_code.utc_now", return_value=NOW),
    ):
        try:
            return await adapter._run_claude_code("p"), calls
        except AgentError as e:
            return e, calls


@pytest.mark.asyncio
class TestHostTokenExpiry:
    async def test_expired_token_is_not_retried(self, tmp_path, monkeypatch):
        a = _adapter(
            tmp_path,
            monkeypatch,
            {"accessToken": TOKEN, "refreshToken": REFRESH, "expiresAt": NOW_MS - 1000},
        )
        result, calls = await _run(a)
        assert isinstance(result, AgentError)
        assert len(calls) == 1
        assert "expired" in str(result)
        assert "refresh it on the host" in str(result)
        assert TOKEN not in str(result)
        assert REFRESH not in str(result)

    async def test_valid_token_is_retried_once(self, tmp_path, monkeypatch):
        a = _adapter(tmp_path, monkeypatch, {"accessToken": TOKEN, "expiresAt": NOW_MS + 60_000})
        result, calls = await _run(a)
        assert result == "OK"
        assert len(calls) == 2

    @pytest.mark.parametrize("value", [None, "garbage", "", [1]])
    async def test_missing_or_unparseable_expiry_is_retried(self, tmp_path, monkeypatch, value):
        oauth = {"accessToken": TOKEN}
        if value is not None:
            oauth["expiresAt"] = value
        a = _adapter(tmp_path, monkeypatch, oauth)
        result, calls = await _run(a)
        assert result == "OK"
        assert len(calls) == 2

    async def test_host_retry_logs_has_user_credentials_false(self, tmp_path, monkeypatch):
        a = _adapter(tmp_path, monkeypatch, {"accessToken": TOKEN, "expiresAt": NOW_MS + 60_000})
        with patch("app.agents.claude_code.logger") as log:
            await _run(a)
        flags = [
            c.kwargs["has_user_credentials"]
            for c in log.info.call_args_list
            if c.args and c.args[0] == "claude_code_call"
        ]
        assert flags == [False, False]
