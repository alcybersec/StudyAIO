"""AgentError messages never carry the adapter's own credential values (R-012)."""

import json
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.anthropic_api import AnthropicAPIAdapter
from app.agents.claude_code import ClaudeCodeAdapter
from app.agents.ollama_adapter import OllamaAdapter
from app.agents.openai_adapter import OpenAIAdapter
from app.agents.zai_adapter import ZaiAdapter
from app.core.exceptions import AgentError, ClassificationError

SENTINEL = "sk-SENTINEL-user-key-0123456789"
CLI_TOKEN = "cli-token-SENTINEL-abcdef123456"


def _assert_clean(exc: BaseException) -> None:
    rendered = "".join(traceback.format_exception(exc))
    assert SENTINEL not in str(exc)
    assert SENTINEL not in rendered
    assert CLI_TOKEN not in rendered


def _instance_keys(mock_settings: MagicMock, anthropic: str = "", openai: str = "") -> None:
    mock_settings.anthropic_api_key.get_secret_value.return_value = anthropic
    mock_settings.openai_api_key.get_secret_value.return_value = openai
    mock_settings.zai_api_key.get_secret_value.return_value = ""


class TestApiAdapters:
    async def test_anthropic_call_error_is_redacted(self):
        adapter = AnthropicAPIAdapter(api_key=SENTINEL)
        client = MagicMock()
        client.messages.create = AsyncMock(side_effect=RuntimeError(f"401 bad key {SENTINEL}"))
        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=client):
            with pytest.raises(AgentError) as ei:
                await adapter._call_api("p")
        _assert_clean(ei.value)
        assert "401 bad key" in str(ei.value)

    async def test_anthropic_stream_error_is_redacted(self):
        adapter = AnthropicAPIAdapter(api_key=SENTINEL)
        client = MagicMock()
        client.messages.stream = MagicMock(side_effect=RuntimeError(f"bad {SENTINEL}"))
        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=client):
            with pytest.raises(AgentError) as ei:
                async for _ in adapter.stream_answer("q", []):
                    pass
        _assert_clean(ei.value)

    @pytest.mark.parametrize("cls", [OpenAIAdapter, ZaiAdapter])
    async def test_openai_family_call_error_is_redacted(self, cls):
        adapter = cls(api_key=SENTINEL, model="m")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError(f"nope {SENTINEL}"))
        with patch.object(adapter, "_client", return_value=client):
            with pytest.raises(AgentError) as ei:
                await adapter._call_api("p")
        _assert_clean(ei.value)

    async def test_openai_stream_error_is_redacted(self):
        adapter = OpenAIAdapter(api_key=SENTINEL, model="m")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError(f"nope {SENTINEL}"))
        with patch.object(adapter, "_client", return_value=client):
            with pytest.raises(AgentError) as ei:
                async for _ in adapter.stream_answer("q", []):
                    pass
        _assert_clean(ei.value)

    async def test_ollama_error_redacts_instance_key(self):
        adapter = OllamaAdapter(base_url="http://localhost:11434", model="m")
        client = MagicMock()
        client.chat = AsyncMock(side_effect=RuntimeError(f"boom {SENTINEL}"))
        with (
            patch("app.agents.ollama_adapter.AsyncClient", return_value=client),
            patch("app.agents.base.settings") as s,
        ):
            _instance_keys(s, anthropic=SENTINEL)
            with pytest.raises(AgentError) as ei:
                await adapter._call_api("p")
        _assert_clean(ei.value)


class TestInstanceKeys:
    async def test_instance_key_is_redacted_from_adapter_with_other_key(self):
        adapter = OpenAIAdapter(api_key="sk-user-own-key-000000", model="m")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError(f"x {SENTINEL}"))
        with (
            patch.object(adapter, "_client", return_value=client),
            patch("app.agents.base.settings") as s,
        ):
            _instance_keys(s, anthropic=SENTINEL)
            with pytest.raises(AgentError) as ei:
                await adapter._call_api("p")
        _assert_clean(ei.value)

    async def test_own_key_is_redacted_too(self):
        adapter = OpenAIAdapter(api_key="sk-user-own-key-000000", model="m")
        assert "sk-user-own-key-000000" not in str(adapter._agent_error("x sk-user-own-key-000000"))


class TestClaudeCode:
    async def test_stderr_with_nested_cli_token_is_redacted(self):
        creds = {"claudeAiOauth": {"accessToken": CLI_TOKEN, "refreshToken": SENTINEL}}
        adapter = ClaudeCodeAdapter(cli_path="claude", model="sonnet", credentials_json=creds)
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(
            return_value=(f"401 token {CLI_TOKEN}".encode(), f"refresh {SENTINEL}".encode())
        )
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            with pytest.raises(AgentError) as ei:
                await adapter._run_claude_code("p")
        _assert_clean(ei.value)
        assert "401 token" in str(ei.value)

    def test_json_string_credentials_are_scrubbed(self):
        adapter = ClaudeCodeAdapter(cli_path="claude", credentials_json=None)
        adapter._credentials_json = json.dumps({"a": {"t": CLI_TOKEN}})  # type: ignore[assignment]
        assert CLI_TOKEN not in str(adapter._agent_error(f"x {CLI_TOKEN}"))


class TestPipelineFailurePath:
    async def test_stage_error_wrapping_an_agent_error_has_no_sentinel(self):
        adapter = OpenAIAdapter(api_key=SENTINEL, model="m")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError(f"x {SENTINEL}"))
        with patch.object(adapter, "_client", return_value=client):
            with pytest.raises(AgentError) as ei:
                await adapter._call_api("p")
        # Stages wrap with f"...: {e}" ... from e; message and chain both stay clean.
        try:
            raise ClassificationError(f"Classification failed: {ei.value}") from ei.value
        except ClassificationError as wrapped:
            _assert_clean(wrapped)
