"""Tests for chat streaming service (stream_message)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentAdapter, AnswerResult
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services.chat_service import stream_message


def _make_chat_session(
    id: str = "session-001",
    user_id: str = "user-001",
    course_id: str | None = None,
    title: str = "New Chat",
    message_count: int = 0,
) -> MagicMock:
    """Create a mock ChatSession."""
    s = MagicMock(spec=ChatSession)
    s.id = id
    s.user_id = user_id
    s.course_id = course_id
    s.title = title
    s.message_count = message_count
    s.created_at = datetime(2026, 3, 5, 10, 0, 0)
    s.updated_at = datetime(2026, 3, 5, 10, 0, 0)
    return s


async def _collect_events(async_gen) -> list[dict]:
    """Collect all events from an async generator."""
    events = []
    async for event in async_gen:
        events.append(event)
    return events


class TestBaseStreamAnswer:
    """Tests for the default stream_answer implementation on AgentAdapter."""

    @pytest.mark.asyncio
    async def test_base_stream_answer_yields_full_response(self) -> None:
        """Default stream_answer calls answer_question and yields the full answer."""

        class ConcreteAgent(AgentAdapter):
            """Minimal concrete implementation for testing."""

            async def classify_lecture(self, *a, **kw): ...

            async def generate_summary(self, *a, **kw): ...

            async def generate_flashcards(self, *a, **kw): ...

            async def generate_quiz(self, *a, **kw): ...

            async def answer_question(self, question, context_chunks):
                return AnswerResult(
                    answer="The answer is 42.",
                    citations=[{"ref": 1, "text_snippet": "42"}],
                )

            async def extract_course_ops(self, *a, **kw): ...

            async def extract_concepts(self, *a, **kw): ...

        agent = ConcreteAgent()
        tokens = []
        async for token in agent.stream_answer("What is the answer?", []):
            tokens.append(token)

        assert len(tokens) == 1
        assert tokens[0] == "The answer is 42."


class TestStreamMessage:
    """Tests for stream_message."""

    @pytest.mark.asyncio
    async def test_stream_message_yields_events_in_order(self) -> None:
        """stream_message yields user_message, token(s), and done events in order."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session()

        # First call: ownership check
        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        # Second call: history (empty)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[ownership_result, history_result])

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        # Mock agent that yields tokens incrementally
        mock_agent = AsyncMock()

        async def mock_stream_answer(question, chunks):
            yield "Hello "
            yield "World"

        mock_agent.stream_answer = mock_stream_answer

        with (
            patch(
                "app.services.chat_service.get_embedding_provider",
                return_value=mock_provider,
            ),
            patch(
                "app.services.chat_service.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.chat_service.get_agent", return_value=mock_agent),
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            events = await _collect_events(
                stream_message(session, "session-001", "user-001", "Hi there")
            )

        # Verify event order: user_message, token(s), done
        event_types = [e["event"] for e in events]
        assert event_types[0] == "user_message"
        # Tokens in the middle
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1
        assert event_types[-1] == "done"

    @pytest.mark.asyncio
    async def test_stream_message_saves_messages_to_db(self) -> None:
        """stream_message saves both user and assistant messages to the database."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session(message_count=0, title="New Chat")

        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[ownership_result, history_result])

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        mock_agent = AsyncMock()

        async def mock_stream_answer(question, chunks):
            yield "Response text"

        mock_agent.stream_answer = mock_stream_answer

        with (
            patch(
                "app.services.chat_service.get_embedding_provider",
                return_value=mock_provider,
            ),
            patch(
                "app.services.chat_service.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.chat_service.get_agent", return_value=mock_agent),
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await _collect_events(
                stream_message(session, "session-001", "user-001", "What is TCP?")
            )

        # session.add should be called twice: user message + assistant message
        assert session.add.call_count == 2

        # First add: user message
        user_msg = session.add.call_args_list[0][0][0]
        assert isinstance(user_msg, ChatMessage)
        assert user_msg.role == "user"
        assert user_msg.content == "What is TCP?"

        # Second add: assistant message
        assistant_msg = session.add.call_args_list[1][0][0]
        assert isinstance(assistant_msg, ChatMessage)
        assert assistant_msg.role == "assistant"
        assert "Response text" in assistant_msg.content

        # Session metadata updated
        assert chat_session.message_count == 2
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stream_message_invalid_session_raises(self) -> None:
        """stream_message yields error event when session not found."""
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        events = await _collect_events(
            stream_message(session, "bad-session-id", "user-001", "Hello")
        )

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert "not found" in events[0]["data"].lower()

    @pytest.mark.asyncio
    async def test_stream_message_agent_error_yields_error_token(self) -> None:
        """Agent streaming failure yields error text as a token event."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session()

        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[ownership_result, history_result])

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        mock_agent = AsyncMock()

        async def mock_stream_answer_error(question, chunks):
            raise RuntimeError("LLM timeout")
            yield  # Make it an async generator  # noqa: E501

        mock_agent.stream_answer = mock_stream_answer_error

        with (
            patch(
                "app.services.chat_service.get_embedding_provider",
                return_value=mock_provider,
            ),
            patch(
                "app.services.chat_service.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.chat_service.get_agent", return_value=mock_agent),
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            events = await _collect_events(
                stream_message(session, "session-001", "user-001", "Help me")
            )

        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1
        # The error message token should contain "error"
        error_text = token_events[0]["data"]
        assert "error" in error_text.lower()
