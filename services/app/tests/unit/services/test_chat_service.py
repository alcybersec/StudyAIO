"""Tests for chat service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services.chat_service import (
    _build_contextual_question,
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    send_message,
)

# ── Helpers ────────────────────────────────────────────────────────


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


def _make_chat_message(
    id: str = "msg-001",
    session_id: str = "session-001",
    role: str = "user",
    content: str = "Hello",
    citations_json: dict | None = None,
) -> MagicMock:
    """Create a mock ChatMessage."""
    m = MagicMock(spec=ChatMessage)
    m.id = id
    m.session_id = session_id
    m.role = role
    m.content = content
    m.citations_json = citations_json
    m.token_count = None
    m.created_at = datetime(2026, 3, 5, 10, 0, 0)
    return m


# ── create_session ─────────────────────────────────────────────────


class TestCreateSession:
    """Tests for create_session."""

    @pytest.mark.asyncio
    async def test_creates_session_successfully(self):
        """Creates a chat session with correct fields."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        result = await create_session(session, user_id="user-001", title="My Chat")

        session.add.assert_called_once()
        assert result.user_id == "user-001"
        assert result.title == "My Chat"
        assert result.message_count == 0

    @pytest.mark.asyncio
    async def test_creates_session_with_course(self):
        """Creates a chat session scoped to a course."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        result = await create_session(
            session,
            user_id="user-001",
            title="Course Chat",
            course_id="course-001",
        )

        assert result.course_id == "course-001"
        assert result.title == "Course Chat"


# ── list_sessions ──────────────────────────────────────────────────


class TestListSessions:
    """Tests for list_sessions."""

    @pytest.mark.asyncio
    async def test_returns_sessions_ordered(self):
        """Returns sessions ordered by updated_at descending."""
        session = AsyncMock()
        mock_sessions = [
            _make_chat_session(id="s-002"),
            _make_chat_session(id="s-001"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_sessions(session, "user-001")

        assert len(result) == 2
        assert result[0].id == "s-002"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        """Returns empty list when user has no sessions."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_sessions(session, "user-001")

        assert result == []


# ── get_messages ───────────────────────────────────────────────────


class TestGetMessages:
    """Tests for get_messages."""

    @pytest.mark.asyncio
    async def test_verifies_ownership(self):
        """Raises ValueError when session not found for user."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Chat session not found"):
            await get_messages(session, "session-999", "user-001")

    @pytest.mark.asyncio
    async def test_returns_ordered_messages(self):
        """Returns messages ordered by created_at ascending."""
        session = AsyncMock()

        # First call: ownership check
        chat_session = _make_chat_session()
        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        # Second call: get messages
        messages = [
            _make_chat_message(id="m-001", role="user", content="Hello"),
            _make_chat_message(id="m-002", role="assistant", content="Hi there!"),
        ]
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = messages

        session.execute = AsyncMock(side_effect=[ownership_result, messages_result])

        result = await get_messages(session, "session-001", "user-001")

        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"


# ── send_message ───────────────────────────────────────────────────


class TestSendMessage:
    """Tests for send_message."""

    @pytest.mark.asyncio
    async def test_orchestration_returns_both_messages(self):
        """send_message returns (user_msg, assistant_msg) tuple."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session()

        # First call: ownership check
        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        # Second call: history (empty for first message)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[ownership_result, history_result])

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        mock_agent = AsyncMock()
        mock_agent.answer_question.return_value = AnswerResult(
            answer="Firewalls monitor network traffic [1].",
            citations=[{"ref": 1, "text_snippet": "Firewalls..."}],
        )

        mock_chunks = [
            {
                "chunk_id": "c-001",
                "text": "Firewalls are security systems.",
                "page_ref": 1,
                "course_code": "CSIT302",
                "week": 5,
                "similarity": 0.85,
            }
        ]

        with (
            patch(
                "app.services.chat_service.get_embedding_provider",
                return_value=mock_provider,
            ),
            patch(
                "app.services.chat_service.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=mock_chunks,
            ),
            patch("app.services.chat_service.get_agent", return_value=mock_agent),
        ):
            user_msg, assistant_msg = await send_message(
                session, "session-001", "user-001", "What is a firewall?"
            )

        assert user_msg.role == "user"
        assert user_msg.content == "What is a firewall?"
        assert assistant_msg.role == "assistant"
        assert "Firewalls" in assistant_msg.content
        assert assistant_msg.citations_json is not None

    @pytest.mark.asyncio
    async def test_auto_titles_from_first_message(self):
        """First message auto-generates the session title."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session(title="New Chat", message_count=0)

        ownership_result = MagicMock()
        ownership_result.scalar_one_or_none.return_value = chat_session

        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[ownership_result, history_result])

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]
        mock_agent = AsyncMock()
        mock_agent.answer_question.return_value = AnswerResult(answer="Sure!", citations=[])

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
        ):
            await send_message(
                session, "session-001", "user-001", "Explain TCP handshake"
            )

        assert chat_session.title == "Explain TCP handshake"

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self):
        """Raises ValueError when session not found for user."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Chat session not found"):
            await send_message(session, "bad-id", "user-001", "Hello")

    @pytest.mark.asyncio
    async def test_agent_error_returns_graceful_message(self):
        """Agent failure returns a graceful error message instead of raising."""
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
        mock_agent.answer_question.side_effect = RuntimeError("LLM timeout")

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
        ):
            user_msg, assistant_msg = await send_message(
                session, "session-001", "user-001", "Help me"
            )

        assert "error" in assistant_msg.content.lower()
        assert assistant_msg.citations_json is None

    @pytest.mark.asyncio
    async def test_rag_failure_continues_without_chunks(self):
        """RAG embedding/search failure doesn't break the conversation."""
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
        mock_provider.embed_texts.side_effect = RuntimeError("Embedding model not loaded")

        mock_agent = AsyncMock()
        mock_agent.answer_question.return_value = AnswerResult(
            answer="I can help with general questions!", citations=[]
        )

        with (
            patch(
                "app.services.chat_service.get_embedding_provider",
                return_value=mock_provider,
            ),
            patch("app.services.chat_service.get_agent", return_value=mock_agent),
        ):
            user_msg, assistant_msg = await send_message(
                session, "session-001", "user-001", "What is recursion?"
            )

        assert assistant_msg.role == "assistant"
        # Agent was called even though embedding failed
        mock_agent.answer_question.assert_called_once()


# ── delete_session ─────────────────────────────────────────────────


class TestDeleteSession:
    """Tests for delete_session."""

    @pytest.mark.asyncio
    async def test_deletes_existing_session(self):
        """Deletes session and returns True."""
        session = AsyncMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()

        chat_session = _make_chat_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chat_session
        session.execute = AsyncMock(return_value=mock_result)

        result = await delete_session(session, "session-001", "user-001")

        assert result is True
        session.delete.assert_called_once_with(chat_session)

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        """Returns False when session not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await delete_session(session, "bad-id", "user-001")

        assert result is False


# ── _build_contextual_question ─────────────────────────────────────


class TestBuildContextualQuestion:
    """Tests for _build_contextual_question helper."""

    def test_no_history_returns_raw_question(self):
        """Without history, returns the question unchanged."""
        result = _build_contextual_question("What is TCP?", [], [])
        assert result == "What is TCP?"

    def test_with_history_includes_context(self):
        """With history, prepends conversation context."""
        history = [
            {"role": "user", "content": "What is networking?"},
            {"role": "assistant", "content": "Networking is the practice of connecting computers."},
        ]
        result = _build_contextual_question("Tell me more about TCP", history, [])

        assert "[Conversation context]" in result
        assert "Student: What is networking?" in result
        assert "[Current question]" in result
        assert "Tell me more about TCP" in result
