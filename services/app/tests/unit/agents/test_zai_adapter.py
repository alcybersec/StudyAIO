"""Tests for ZaiAdapter.

Z.ai is OpenAI-compatible, so the adapter inherits every prompt method from
OpenAIAdapter. What actually needs testing is the part that differs: that
requests are pointed at Z.ai rather than api.openai.com, that the right
credentials and model are used, and that the inherited behaviour still works
through the subclass.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ClassificationResult
from app.agents.openai_adapter import OpenAIAdapter
from app.agents.zai_adapter import ZAI_BASE_URL, ZAI_DEFAULT_MODEL, ZaiAdapter
from app.core.exceptions import AgentError


def _mock_response(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.fixture
def no_env_settings():
    """No Z.ai settings configured in the environment."""
    with patch("app.agents.zai_adapter.get_effective_setting", return_value="") as m:
        yield m


class TestConfiguration:
    def test_uses_zai_endpoint_by_default(self, no_env_settings):
        assert ZaiAdapter(api_key="k")._base_url == ZAI_BASE_URL

    def test_endpoint_is_the_openai_compatible_path(self):
        """The SDK appends /chat/completions, so the base must end at /v4/."""
        assert ZAI_BASE_URL == "https://api.z.ai/api/paas/v4/"

    def test_defaults_to_the_flagship_model(self, no_env_settings):
        assert ZaiAdapter(api_key="k")._model == ZAI_DEFAULT_MODEL

    def test_explicit_arguments_win(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k1", model="glm-4.6", base_url="https://self.hosted/v4/")
        assert adapter._api_key == "k1"
        assert adapter._model == "glm-4.6"
        assert adapter._base_url == "https://self.hosted/v4/"

    def test_falls_back_to_configured_settings(self):
        values = {
            "zai_api_key": "env-key",
            "zai_model": "glm-4.6",
            "zai_base_url": "https://regional.z.ai/api/paas/v4/",
            "zai_thinking": "disabled",
        }
        with patch("app.agents.zai_adapter.get_effective_setting", side_effect=lambda k: values[k]):
            adapter = ZaiAdapter()
        assert adapter._api_key == "env-key"
        assert adapter._model == "glm-4.6"
        assert adapter._base_url == "https://regional.z.ai/api/paas/v4/"

    def test_is_an_openai_adapter(self):
        """Inheritance is the point — all prompt methods come for free."""
        assert issubclass(ZaiAdapter, OpenAIAdapter)

    def test_reports_itself_as_zai(self):
        assert ZaiAdapter.provider_name == "Z.ai"


class TestClientConstruction:
    def test_client_is_pointed_at_zai(self, no_env_settings):
        adapter = ZaiAdapter(api_key="secret-key")
        with patch("app.agents.openai_adapter.AsyncOpenAI") as mock_client:
            adapter._client()
        mock_client.assert_called_once_with(api_key="secret-key", base_url=ZAI_BASE_URL)

    def test_openai_adapter_still_uses_the_sdk_default(self):
        """Adding base_url support must not change OpenAI's own behaviour."""
        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            adapter = OpenAIAdapter(api_key="k", model="gpt-4o")
        with patch("app.agents.openai_adapter.AsyncOpenAI") as mock_client:
            adapter._client()
        mock_client.assert_called_once_with(api_key="k")


class TestApiKeyRequired:
    @pytest.mark.asyncio
    async def test_missing_key_names_zai_in_the_error(self, no_env_settings):
        adapter = ZaiAdapter()
        with pytest.raises(AgentError, match="Z.ai API key not configured"):
            await adapter._call_api("hello")

    @pytest.mark.asyncio
    async def test_openai_error_still_names_openai(self):
        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            adapter = OpenAIAdapter()
        with pytest.raises(AgentError, match="OpenAI API key not configured"):
            await adapter._call_api("hello")


class TestInheritedBehaviour:
    @pytest.mark.asyncio
    async def test_classify_works_through_the_subclass(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k", model="glm-5.3")
        payload = json.dumps(
            {
                "course_code": "CSIT302",
                "week": 5,
                "title": "Network Security",
                "confidence": 0.93,
                "reasoning": "explicit header",
            }
        )
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_mock_response(payload))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            result = await adapter.classify_lecture(
                "CSIT302 Week 5 ...", "lecture.pdf", ["CSIT302"]
            )

        assert isinstance(result, ClassificationResult)
        assert result.course_code == "CSIT302"
        assert result.week == 5

    @pytest.mark.asyncio
    async def test_sends_the_configured_glm_model(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k", model="glm-4.6")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_mock_response("hi"))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        assert client.chat.completions.create.call_args.kwargs["model"] == "glm-4.6"

    @pytest.mark.asyncio
    async def test_api_failure_becomes_an_agent_error(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("upstream down"))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            # The error must name Z.ai, not OpenAI — otherwise a failing GLM
            # call sends the operator looking at the wrong provider.
            with pytest.raises(AgentError, match="Z.ai API call failed"):
                await adapter._call_api("prompt")


class TestThinkingMode:
    """GLM's thinking mode roughly doubles response verbosity, which blows the
    summarize stage's 8192 token cap before the response structure completes
    (measured: 2/8 sections, truncated, no footer). Disabling it produced a
    complete response (8/8 sections, footer present) within the same cap, so
    it is disabled by default."""

    @pytest.mark.asyncio
    async def test_disables_thinking_by_default(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_mock_response("hi"))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    @pytest.mark.asyncio
    async def test_zai_thinking_setting_enabled_sends_enabled(self):
        values = {
            "zai_api_key": "env-key",
            "zai_model": "glm-5.3",
            "zai_base_url": "",
            "zai_thinking": "enabled",
        }
        with patch("app.agents.zai_adapter.get_effective_setting", side_effect=lambda k: values[k]):
            adapter = ZaiAdapter()

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_mock_response("hi"))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}

    @pytest.mark.asyncio
    async def test_explicit_thinking_argument_wins(self, no_env_settings):
        adapter = ZaiAdapter(api_key="k", thinking="enabled")
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_mock_response("hi"))

        with patch.object(ZaiAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}

    @pytest.mark.asyncio
    async def test_streaming_path_also_disables_thinking(self, no_env_settings):
        """The streaming path (chat, not summarize) must carry the same
        thinking override — a fix limited to the non-streaming path would
        leave GLM chat streaming still verbose and prone to truncation."""
        adapter = ZaiAdapter(api_key="k")

        async def mock_stream():
            return
            yield  # pragma: no cover - makes this an async generator

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch.object(ZaiAdapter, "_client", return_value=client):
            async for _ in adapter.stream_answer("question", []):
                pass

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


class TestFactoryRouting:
    def test_zai_backend_returns_a_zai_adapter(self):
        from app.agents.factory import get_agent

        with patch("app.agents.factory.get_effective_setting", return_value="zai"):
            with patch("app.agents.zai_adapter.get_effective_setting", return_value=""):
                agent = get_agent()
        assert isinstance(agent, ZaiAdapter)

    def test_per_user_credentials_are_routed(self):
        from app.agents.factory import get_agent

        agent = get_agent(
            user_settings={
                "agent_backend": "zai",
                "zai_api_key": "user-key",
                "zai_model": "glm-4.6",
                "zai_base_url": "",
            }
        )
        assert isinstance(agent, ZaiAdapter)
        assert agent._api_key == "user-key"
        assert agent._model == "glm-4.6"
        # Blank per-user base URL must fall back to Z.ai, not to OpenAI.
        assert agent._base_url == ZAI_BASE_URL

    def test_zai_is_an_accepted_backend(self):
        from app.services.settings_service import VALID_BACKENDS, validate_setting

        assert "zai" in VALID_BACKENDS
        assert validate_setting("agent_backend", "zai") == "zai"
