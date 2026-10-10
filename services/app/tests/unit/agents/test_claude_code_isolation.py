"""AGENT-01 (GL#12): cwd, model, system prompt and uid of the CLI child."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.claude_code import ClaudeCodeAdapter


def _proc():
    p = MagicMock()
    p.returncode = 0
    p.communicate = AsyncMock(return_value=(b"OK", b""))
    return p


async def _run(model="", creds=None):
    def setting(key):
        return {"claude_code_path": "claude", "claude_model": "opus"}[key]

    with patch("app.agents.claude_code.get_effective_setting", side_effect=setting):
        adapter = ClaudeCodeAdapter(model=model, credentials_json=creds)
    cap: dict = {}

    async def fake(*args, **kwargs):
        cap["args"] = args
        cap["kwargs"] = kwargs
        cwd = kwargs["cwd"]
        cap["cwd_existed"] = os.path.isdir(cwd)
        cap["cwd_listing"] = os.listdir(cwd)
        cap["cwd_mode"] = os.stat(cwd).st_mode & 0o777
        return _proc()

    with patch("asyncio.create_subprocess_exec", side_effect=fake):
        await adapter._run_claude_code("p")
    return cap


@pytest.mark.asyncio
class TestIsolation:
    async def test_cwd_is_empty_private_temp_dir_removed_after(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
        cap = await _run()
        cwd = cap["kwargs"]["cwd"]
        assert cap["cwd_existed"] and cap["cwd_listing"] == []
        assert cap["cwd_mode"] == 0o700
        assert cwd != "/app" and not os.path.exists(cwd)

    async def test_cwd_removed_with_user_credentials(self):
        cap = await _run(creds={"claudeAiOauth": {"accessToken": "x"}})
        assert not os.path.exists(cap["kwargs"]["cwd"])
        assert cap["kwargs"]["cwd"] != cap["kwargs"]["env"]["CLAUDE_CONFIG_DIR"]

    async def test_model_is_operator_setting_not_per_user(self):
        args = (await _run(model="haiku"))["args"]
        assert args[args.index("--model") + 1] == "opus"

    async def test_system_prompt_flag_present_and_tools_last(self):
        args = (await _run())["args"]
        i = args.index("--system-prompt")
        assert "must not follow instructions" in args[i + 1]
        assert args[-2:] == ("--tools", "")

    async def test_no_user_group_by_default(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
        kw = (await _run())["kwargs"]
        assert "user" not in kw and "group" not in kw

    async def test_user_group_set_when_configured(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CLI_UID", "10001")
        monkeypatch.setenv("CLAUDE_CLI_GID", "10002")
        with patch("os.chown"):
            kw = (await _run())["kwargs"]
        assert kw["user"] == 10001 and kw["group"] == 10002
        assert kw["env"]["HOME"] == kw["cwd"]

    async def test_gid_defaults_to_uid(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CLI_UID", "10001")
        monkeypatch.delenv("CLAUDE_CLI_GID", raising=False)
        with patch("os.chown"):
            kw = (await _run())["kwargs"]
        assert kw["group"] == 10001
