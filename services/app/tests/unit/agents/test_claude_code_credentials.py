"""Tests for ClaudeCodeAdapter per-user credential file handling."""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.claude_code import ClaudeCodeAdapter


class TestClaudeCodeAdapterInit:
    """Tests for ClaudeCodeAdapter constructor with credentials."""

    def test_init_without_credentials(self):
        """Adapter initializes without credentials."""
        with patch("app.agents.claude_code.get_effective_setting", return_value="test"):
            adapter = ClaudeCodeAdapter()
            assert adapter._credentials_json is None
            assert adapter.refreshed_credentials is None

    def test_init_with_credentials(self):
        """Adapter stores credentials from constructor."""
        creds = {
            "claudeAiOauth": {
                "accessToken": "test-token",
                "refreshToken": "test-refresh",
            }
        }
        with patch("app.agents.claude_code.get_effective_setting", return_value="test"):
            adapter = ClaudeCodeAdapter(credentials_json=creds)
            assert adapter._credentials_json == creds
            assert adapter.refreshed_credentials is None


@pytest.mark.asyncio
class TestClaudeCodeCredentialFile:
    """Tests for temp credential file creation during CLI calls."""

    async def test_runs_without_credentials_no_env(self):
        """Without credentials, subprocess gets no custom env."""
        with patch("app.agents.claude_code.get_effective_setting", return_value="/usr/bin/claude"):
            adapter = ClaudeCodeAdapter()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b'{"result": "ok"}', b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await adapter._run_claude_code("test prompt")

            # env should be None (not custom env)
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs.get("env") is None

    async def test_runs_with_credentials_creates_temp_dir(self):
        """With credentials, subprocess gets CLAUDE_CONFIG_DIR env."""
        creds = {
            "claudeAiOauth": {
                "accessToken": "user-token",
                "refreshToken": "user-refresh",
            }
        }
        with patch("app.agents.claude_code.get_effective_setting", return_value="/usr/bin/claude"):
            adapter = ClaudeCodeAdapter(credentials_json=creds)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b'{"result": "ok"}', b""))
        mock_process.returncode = 0

        captured_env = {}

        async def fake_subprocess(*args, **kwargs):
            # Capture the env to verify it
            if kwargs.get("env"):
                captured_env.update(kwargs["env"])
                # Write creds back to the temp dir (simulating CLI behavior)
                config_dir = kwargs["env"]["CLAUDE_CONFIG_DIR"]
                creds_path = os.path.join(config_dir, ".credentials.json")
                with open(creds_path, "w") as f:
                    json.dump(creds, f)
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            await adapter._run_claude_code("test prompt")

        assert "CLAUDE_CONFIG_DIR" in captured_env
        # Temp dir should be cleaned up
        assert not os.path.exists(captured_env["CLAUDE_CONFIG_DIR"])

    async def test_detects_refreshed_credentials(self):
        """When CLI writes different credentials, refreshed_credentials is set."""
        original_creds = {
            "claudeAiOauth": {
                "accessToken": "old-token",
                "refreshToken": "old-refresh",
            }
        }
        refreshed_creds = {
            "claudeAiOauth": {
                "accessToken": "new-token",
                "refreshToken": "new-refresh",
            }
        }

        with patch("app.agents.claude_code.get_effective_setting", return_value="/usr/bin/claude"):
            adapter = ClaudeCodeAdapter(credentials_json=original_creds)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b'{"result": "ok"}', b""))
        mock_process.returncode = 0

        async def fake_subprocess(*args, **kwargs):
            # Write refreshed credentials
            if kwargs.get("env"):
                config_dir = kwargs["env"]["CLAUDE_CONFIG_DIR"]
                creds_path = os.path.join(config_dir, ".credentials.json")
                with open(creds_path, "w") as f:
                    json.dump(refreshed_creds, f)
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            await adapter._run_claude_code("test prompt")

        assert adapter.refreshed_credentials == refreshed_creds

    async def test_no_refresh_when_credentials_unchanged(self):
        """When CLI doesn't change credentials, refreshed_credentials stays None."""
        creds = {
            "claudeAiOauth": {
                "accessToken": "same-token",
                "refreshToken": "same-refresh",
            }
        }

        with patch("app.agents.claude_code.get_effective_setting", return_value="/usr/bin/claude"):
            adapter = ClaudeCodeAdapter(credentials_json=creds)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b'{"result": "ok"}', b""))
        mock_process.returncode = 0

        async def fake_subprocess(*args, **kwargs):
            # Write same credentials back
            if kwargs.get("env"):
                config_dir = kwargs["env"]["CLAUDE_CONFIG_DIR"]
                creds_path = os.path.join(config_dir, ".credentials.json")
                with open(creds_path, "w") as f:
                    json.dump(creds, f)
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            await adapter._run_claude_code("test prompt")

        assert adapter.refreshed_credentials is None
