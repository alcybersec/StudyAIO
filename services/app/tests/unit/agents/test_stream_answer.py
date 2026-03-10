"""Tests for stream_answer implementations across agent adapters."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentAdapter, AnswerResult


class TestBaseDefaultStreamAnswer:
    """Tests for the default stream_answer on AgentAdapter base class."""

    @pytest.mark.asyncio
    async def test_base_default_stream_yields_full_answer(self) -> None:
        """Default stream_answer calls answer_question and yields entire answer."""

        class MinimalAgent(AgentAdapter):
            """Minimal concrete implementation."""

            async def classify_lecture(self, *a, **kw): ...

            async def generate_summary(self, *a, **kw): ...

            async def generate_flashcards(self, *a, **kw): ...

            async def generate_quiz(self, *a, **kw): ...

            async def answer_question(self, question, context_chunks):
                return AnswerResult(
                    answer="Polymorphism allows objects to be treated as instances of their parent class.",
                    citations=[],
                )

            async def extract_course_ops(self, *a, **kw): ...

            async def extract_concepts(self, *a, **kw): ...

        agent = MinimalAgent()
        tokens = []
        async for token in agent.stream_answer("What is polymorphism?", []):
            tokens.append(token)

        assert len(tokens) == 1
        assert "Polymorphism" in tokens[0]


class TestAnthropicStreamAnswer:
    """Tests for AnthropicAPIAdapter.stream_answer."""

    @pytest.mark.asyncio
    async def test_anthropic_stream_answer_yields_tokens(self) -> None:
        """Anthropic stream_answer yields individual text tokens from the streaming API."""
        with (
            patch(
                "app.agents.anthropic_api.get_effective_setting",
                side_effect=lambda key: {
                    "anthropic_api_key": "test-key",
                    "claude_model": "sonnet",
                }.get(key, ""),
            ),
        ):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            adapter = AnthropicAPIAdapter(api_key="test-key", model="sonnet")

        # Mock the streaming context manager
        AsyncMock()

        async def mock_text_iter():
            for token in ["Hello", " ", "World", "!"]:
                yield token

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_cm)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)
        mock_stream_cm.text_stream = mock_text_iter()

        mock_client = AsyncMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream_cm)

        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client):
            tokens = []
            async for token in adapter.stream_answer("Test question", []):
                tokens.append(token)

        assert tokens == ["Hello", " ", "World", "!"]
        assert "".join(tokens) == "Hello World!"

    @pytest.mark.asyncio
    async def test_anthropic_stream_answer_raises_on_error(self) -> None:
        """Anthropic stream_answer wraps errors in AgentError."""
        from app.core.exceptions import AgentError

        with patch(
            "app.agents.anthropic_api.get_effective_setting",
            side_effect=lambda key: {
                "anthropic_api_key": "test-key",
                "claude_model": "sonnet",
            }.get(key, ""),
        ):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            adapter = AnthropicAPIAdapter(api_key="test-key", model="sonnet")

        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("Connection failed"))

        mock_client = AsyncMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream_cm)

        with (
            patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client),
            pytest.raises(AgentError, match="Anthropic streaming failed"),
        ):
            async for _ in adapter.stream_answer("Test", []):
                pass


class TestOpenAIStreamAnswer:
    """Tests for OpenAIAdapter.stream_answer."""

    @pytest.mark.asyncio
    async def test_openai_stream_answer_yields_tokens(self) -> None:
        """OpenAI stream_answer yields individual delta content tokens."""
        with patch(
            "app.agents.openai_adapter.get_effective_setting",
            side_effect=lambda key: {
                "openai_api_key": "test-key",
                "openai_model": "gpt-4",
            }.get(key, ""),
        ):
            from app.agents.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="test-key", model="gpt-4")

        # Build mock streaming response chunks
        def make_chunk(content: str | None):
            chunk = MagicMock()
            choice = MagicMock()
            delta = MagicMock()
            delta.content = content
            choice.delta = delta
            chunk.choices = [choice]
            return chunk

        chunks = [
            make_chunk("Hello"),
            make_chunk(" "),
            make_chunk("World"),
            make_chunk(None),  # Final chunk with no content
        ]

        async def mock_stream():
            for c in chunks:
                yield c

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            tokens = []
            async for token in adapter.stream_answer("Test question", []):
                tokens.append(token)

        assert tokens == ["Hello", " ", "World"]
        assert "".join(tokens) == "Hello World"

    @pytest.mark.asyncio
    async def test_openai_stream_answer_raises_on_error(self) -> None:
        """OpenAI stream_answer wraps errors in AgentError."""
        from app.core.exceptions import AgentError

        with patch(
            "app.agents.openai_adapter.get_effective_setting",
            side_effect=lambda key: {
                "openai_api_key": "test-key",
                "openai_model": "gpt-4",
            }.get(key, ""),
        ):
            from app.agents.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="test-key", model="gpt-4")

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API rate limit"))

        with (
            patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client),
            pytest.raises(AgentError, match="OpenAI streaming failed"),
        ):
            async for _ in adapter.stream_answer("Test", []):
                pass
