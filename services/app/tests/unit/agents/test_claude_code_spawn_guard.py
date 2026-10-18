"""SEC-006 option F: fail-closed spawn guard for the Claude Code CLI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import claude_code
from app.agents.claude_code import (
    CLI_SPAWN_REFUSALS,
    ClaudeCliUnavailableError,
    ClaudeCodeAdapter,
)
from app.agents.transient import TransientAgentError
from app.core.exceptions import AgentError


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", raising=False)
    monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
    monkeypatch.setattr(claude_code.settings, "single_user_mode", False)
    claude_code._refusal_logged.clear()


def _adapter(creds=None):
    with patch(
        "app.agents.claude_code.get_effective_setting",
        side_effect=lambda k: {"claude_code_path": "claude", "claude_model": "m"}[k],
    ):
        return ClaudeCodeAdapter(credentials_json=creds)


def _proc():
    p = MagicMock()
    p.returncode = 0
    p.communicate = AsyncMock(return_value=(b"OK", b""))
    return p


def _refused(error_class="ClaudeCliUnavailableError"):
    return CLI_SPAWN_REFUSALS.labels(
        stage="claude_cli_spawn", outcome="refused", error_class=error_class
    )._value.get()


@pytest.mark.asyncio
class TestSpawnGuard:
    @pytest.mark.parametrize("creds", [None, {"claudeAiOauth": {"accessToken": "x"}}])
    async def test_nonroot_multiuser_refuses_without_spawn_or_token_read(self, creds):
        before = _refused()
        with (
            patch("os.geteuid", return_value=999),
            patch("asyncio.create_subprocess_exec") as spawn,
            patch("app.agents.claude_code._read_host_oauth_token") as tok,
        ):
            with pytest.raises(ClaudeCliUnavailableError) as ei:
                await _adapter(creds)._run_claude_code("p")
        spawn.assert_not_called()
        tok.assert_not_called()
        assert not isinstance(ei.value, TransientAgentError)
        assert isinstance(ei.value, AgentError)
        assert _refused() == before + 1

    async def test_opt_in_flag_spawns(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", "true")
        with (
            patch("os.geteuid", return_value=999),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc())) as spawn,
        ):
            assert await _adapter()._run_claude_code("p") == "OK"
        spawn.assert_awaited_once()

    async def test_single_user_mode_spawns(self, monkeypatch):
        monkeypatch.setattr(claude_code.settings, "single_user_mode", True)
        with (
            patch("os.geteuid", return_value=999),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc())) as spawn,
        ):
            await _adapter()._run_claude_code("p")
        spawn.assert_awaited_once()

    async def test_flag_false_still_refuses(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", "false")
        with patch("os.geteuid", return_value=999), pytest.raises(ClaudeCliUnavailableError):
            await _adapter()._run_claude_code("p")

    @pytest.mark.parametrize("single", [False, True])
    async def test_uid_set_on_nonroot_refuses_clearly_not_permissionerror(
        self, monkeypatch, single
    ):
        monkeypatch.setenv("CLAUDE_CLI_UID", "10001")
        monkeypatch.setenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", "true")
        monkeypatch.setattr(claude_code.settings, "single_user_mode", single)
        with (
            patch("os.geteuid", return_value=999),
            patch("asyncio.create_subprocess_exec") as spawn,
            pytest.raises(ClaudeCliUnavailableError, match="CLAUDE_CLI_UID"),
        ):
            await _adapter()._run_claude_code("p")
        spawn.assert_not_called()

    async def test_root_keeps_drop_path_unchanged(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CLI_UID", "10001")
        monkeypatch.setenv("CLAUDE_CLI_GID", "10002")
        with (
            patch("os.geteuid", return_value=0),
            patch("os.chown"),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc())) as spawn,
        ):
            await _adapter()._run_claude_code("p")
        assert spawn.await_args.kwargs["user"] == 10001

    async def test_root_without_uid_spawns_without_flag(self):
        with (
            patch("os.geteuid", return_value=0),
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc())) as spawn,
        ):
            await _adapter()._run_claude_code("p")
        spawn.assert_awaited_once()

    async def test_refusal_logged_once_without_secrets(self):
        creds = {"claudeAiOauth": {"accessToken": "sk-ant-SECRETVALUE"}}
        with (
            patch("os.geteuid", return_value=999),
            patch.object(claude_code.logger, "error") as log,
        ):
            for _ in range(3):
                with pytest.raises(ClaudeCliUnavailableError) as ei:
                    await _adapter(creds)._run_claude_code("p")
        assert log.call_count == 1
        assert "SECRETVALUE" not in repr(log.call_args) + str(ei.value)
