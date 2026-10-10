"""GL#8: the worker must pick up host-refreshed credentials without a restart."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.claude_code import ClaudeCodeAdapter
from app.core.exceptions import AgentError

STALE = "stale-token-SENTINEL-aaaaaaaa1111"
FRESH = "fresh-token-SENTINEL-bbbbbbbb2222"
AUTH_STDOUT = b"Failed to authenticate. API Error: 401 OAuth access token has been revoked."
SANDBOX_STDERR = b"Sandbox disabled: bubblewrap (bwrap) not installed"


def _write_host(path, token):
    path.write_text(json.dumps({"claudeAiOauth": {"accessToken": token}}))


def _proc(rc, out=b"", err=b""):
    p = MagicMock()
    p.returncode = rc
    p.communicate = AsyncMock(return_value=(out, err))
    return p


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    host = tmp_path / ".credentials.json"
    _write_host(host, STALE)
    monkeypatch.setenv("CLAUDE_HOST_CREDENTIALS_FILE", str(host))
    with patch("app.agents.claude_code.get_effective_setting", return_value="claude"):
        a = ClaudeCodeAdapter()
    a.host = host
    return a


@pytest.mark.asyncio
class TestStaleCredentialRetry:
    async def test_retries_once_with_refreshed_host_credentials(self, adapter):
        seen = []

        async def fake(*args, **kwargs):
            env = kwargs.get("env")
            if "CLAUDE_CONFIG_DIR" not in env:
                # first call: the container's own (stale) file; host refreshes meanwhile
                seen.append(None)
                _write_host(adapter.host, FRESH)
                return _proc(1, AUTH_STDOUT, SANDBOX_STDERR)
            path = os.path.join(env["CLAUDE_CONFIG_DIR"], ".credentials.json")
            with open(path) as f:
                seen.append(json.load(f)["claudeAiOauth"]["accessToken"])
            return _proc(0, b"OK")

        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            assert await adapter._run_claude_code("p") == "OK"
        assert seen == [None, FRESH]

    async def test_second_auth_failure_is_redacted_and_not_retried_again(self, adapter):
        calls = 0

        async def fake(*args, **kwargs):
            nonlocal calls
            calls += 1
            _write_host(adapter.host, FRESH)
            return _proc(1, AUTH_STDOUT + b" " + FRESH.encode())

        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(AgentError) as ei:
                await adapter._run_claude_code("p")
        assert calls == 2
        assert FRESH not in str(ei.value)
        assert STALE not in str(ei.value)
        assert "revoked" in str(ei.value)

    async def test_non_auth_failure_is_not_retried(self, adapter):
        calls = 0

        async def fake(*args, **kwargs):
            nonlocal calls
            calls += 1
            return _proc(1, b"model overloaded")

        with patch("asyncio.create_subprocess_exec", side_effect=fake):
            with pytest.raises(AgentError):
                await adapter._run_claude_code("p")
        assert calls == 1

    async def test_no_host_file_means_no_retry(self, adapter, monkeypatch):
        monkeypatch.delenv("CLAUDE_HOST_CREDENTIALS_FILE")
        mock = AsyncMock(return_value=_proc(1, AUTH_STDOUT))
        with patch("asyncio.create_subprocess_exec", mock):
            with pytest.raises(AgentError):
                await adapter._run_claude_code("p")
        assert mock.await_count == 1

    async def test_per_user_credentials_are_never_replaced_by_host_file(self, adapter):
        with patch("app.agents.claude_code.get_effective_setting", return_value="claude"):
            user = ClaudeCodeAdapter(credentials_json={"claudeAiOauth": {"accessToken": "u" * 30}})
        mock = AsyncMock(return_value=_proc(1, AUTH_STDOUT))
        with patch("asyncio.create_subprocess_exec", mock):
            with pytest.raises(AgentError):
                await user._run_claude_code("p")
        assert mock.await_count == 1
