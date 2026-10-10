"""Use-time SSRF check on user-supplied provider base URLs (SEC-03, GL#14)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.ollama_adapter import OllamaAdapter
from app.agents.zai_adapter import ZaiAdapter
from app.core.exceptions import AgentError
from app.core.url_safety import UnsafeURLError


def _env(key: str) -> str:
    return {
        "ollama_base_url": "http://ollama:11434",
        "ollama_model": "m",
        "zai_base_url": "http://internal-glm:8000/v1",
        "zai_model": "glm",
        "zai_api_key": "k",
    }.get(key, "")


@pytest.mark.asyncio
class TestOllama:
    async def test_user_url_validated_before_client_built(self):
        with (
            patch("app.agents.ollama_adapter.get_effective_setting", _env),
            patch(
                "app.agents.ollama_adapter.validate_outbound_url",
                side_effect=UnsafeURLError("private"),
            ) as validate,
            patch("app.agents.ollama_adapter.AsyncClient") as client,
        ):
            adapter = OllamaAdapter(base_url="http://169.254.169.254", user_supplied_url=True)
            with pytest.raises(AgentError):
                await adapter._call_api("hi")
        validate.assert_called_once_with("http://169.254.169.254")
        client.assert_not_called()

    async def test_operator_default_url_not_validated(self):
        chat = AsyncMock(return_value=MagicMock(message=MagicMock(content="ok")))
        with (
            patch("app.agents.ollama_adapter.get_effective_setting", _env),
            patch("app.agents.ollama_adapter.validate_outbound_url") as validate,
            patch("app.agents.ollama_adapter.AsyncClient") as client,
        ):
            client.return_value.chat = chat
            await OllamaAdapter()._call_api("hi")
        validate.assert_not_called()

    async def test_client_never_follows_redirects(self):
        chat = AsyncMock(return_value=MagicMock(message=MagicMock(content="ok")))
        with (
            patch("app.agents.ollama_adapter.get_effective_setting", _env),
            patch("app.agents.ollama_adapter.validate_outbound_url"),
            patch("app.agents.ollama_adapter.AsyncClient") as client,
        ):
            client.return_value.chat = chat
            await OllamaAdapter(base_url="http://x.example", user_supplied_url=True)._call_api("hi")
        assert client.call_args.kwargs["follow_redirects"] is False


class TestZai:
    def test_user_url_validated_before_client_built(self):
        with (
            patch("app.agents.zai_adapter.get_effective_setting", _env),
            patch(
                "app.agents.openai_adapter.validate_outbound_url",
                side_effect=UnsafeURLError("private"),
            ) as validate,
        ):
            adapter = ZaiAdapter(api_key="k", base_url="http://10.0.0.5/v1", user_supplied_url=True)
            with pytest.raises(AgentError):
                adapter._client()
        validate.assert_called_once_with("http://10.0.0.5/v1")

    def test_operator_url_not_validated_and_redirects_off(self):
        with (
            patch("app.agents.zai_adapter.get_effective_setting", _env),
            patch("app.agents.openai_adapter.validate_outbound_url") as validate,
        ):
            client = ZaiAdapter(api_key="k")._client()
        validate.assert_not_called()
        assert client._client.follow_redirects is False

    def test_user_url_client_redirects_off(self):
        with (
            patch("app.agents.zai_adapter.get_effective_setting", _env),
            patch("app.agents.openai_adapter.validate_outbound_url"),
        ):
            client = ZaiAdapter(
                api_key="k", base_url="https://api.example.com/v1", user_supplied_url=True
            )._client()
        assert client._client.follow_redirects is False


class TestFactory:
    def test_user_urls_flagged_user_supplied(self):
        from app.agents.factory import get_agent

        z = get_agent(
            {"agent_backend": "zai", "zai_api_key": "k", "zai_base_url": "https://a.example/v1"}
        )
        assert z._user_supplied_url is True
        o = get_agent({"agent_backend": "ollama", "ollama_base_url": "https://o.example"})
        assert o._user_supplied_url is True

    def test_user_without_url_not_flagged(self):
        from app.agents.factory import get_agent

        z = get_agent({"agent_backend": "zai", "zai_api_key": "k"})
        assert z._user_supplied_url is False
