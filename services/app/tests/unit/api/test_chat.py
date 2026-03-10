"""Tests for the chat API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


def _mock_session_obj(
    id: str = "session-001",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    course_id: str | None = None,
    title: str = "Test Chat",
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


def _mock_message_obj(
    id: str = "msg-001",
    session_id: str = "session-001",
    role: str = "user",
    content: str = "Hello",
    citations_json: list | None = None,
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


@pytest.mark.asyncio
class TestCreateSession:
    """Tests for POST /api/chat/sessions."""

    async def test_create_session_success(self, async_client, mock_session):
        """Creates a chat session and returns 201."""
        mock_chat = _mock_session_obj()

        with patch(
            "app.api.chat.chat_service.create_session",
            new_callable=AsyncMock,
            return_value=mock_chat,
        ):
            response = await async_client.post(
                "/api/chat/sessions",
                json={"title": "Test Chat"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "session-001"
        assert data["title"] == "Test Chat"
        assert data["message_count"] == 0

    async def test_create_session_with_course(self, async_client, mock_session):
        """Creates a session scoped to a course by code."""
        mock_course = MagicMock()
        mock_course.id = "course-001"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        mock_session.execute.return_value = mock_result

        mock_chat = _mock_session_obj(course_id="course-001")

        with patch(
            "app.api.chat.chat_service.create_session",
            new_callable=AsyncMock,
            return_value=mock_chat,
        ):
            response = await async_client.post(
                "/api/chat/sessions",
                json={"title": "Course Chat", "course_code": "CSIT302"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["course_id"] == "course-001"

    async def test_create_session_unknown_course_returns_404(self, async_client, mock_session):
        """Unknown course code returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        response = await async_client.post(
            "/api/chat/sessions",
            json={"title": "Bad", "course_code": "INVALID"},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestListSessions:
    """Tests for GET /api/chat/sessions."""

    async def test_list_sessions_success(self, async_client, mock_session):
        """Returns list of sessions."""
        mock_sessions = [
            _mock_session_obj(id="s-002", title="Second"),
            _mock_session_obj(id="s-001", title="First"),
        ]

        with patch(
            "app.api.chat.chat_service.list_sessions",
            new_callable=AsyncMock,
            return_value=mock_sessions,
        ):
            response = await async_client.get("/api/chat/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2
        assert data["sessions"][0]["id"] == "s-002"


@pytest.mark.asyncio
class TestGetMessages:
    """Tests for GET /api/chat/sessions/{session_id}/messages."""

    async def test_get_messages_success(self, async_client, mock_session):
        """Returns paginated messages for a session."""
        mock_msgs = [
            _mock_message_obj(id="m-001", role="user", content="Hello"),
            _mock_message_obj(id="m-002", role="assistant", content="Hi!"),
        ]

        with patch(
            "app.api.chat.chat_service.get_messages",
            new_callable=AsyncMock,
            return_value=mock_msgs,
        ):
            response = await async_client.get("/api/chat/sessions/session-001/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"

    async def test_get_messages_not_found(self, async_client, mock_session):
        """Returns 404 for unknown session."""
        with patch(
            "app.api.chat.chat_service.get_messages",
            new_callable=AsyncMock,
            side_effect=ValueError("Chat session not found"),
        ):
            response = await async_client.get("/api/chat/sessions/bad-id/messages")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestSendMessage:
    """Tests for POST /api/chat/sessions/{session_id}/messages."""

    async def test_send_message_success(self, async_client, mock_session):
        """Sends a message and returns user + assistant messages."""
        user_msg = _mock_message_obj(id="m-001", role="user", content="What is TCP?")
        assistant_msg = _mock_message_obj(
            id="m-002",
            role="assistant",
            content="TCP is a transport protocol [1].",
            citations_json=[{"ref": 1, "text_snippet": "TCP..."}],
        )

        with patch(
            "app.api.chat.chat_service.send_message",
            new_callable=AsyncMock,
            return_value=(user_msg, assistant_msg),
        ):
            response = await async_client.post(
                "/api/chat/sessions/session-001/messages",
                json={"content": "What is TCP?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "What is TCP?"
        assert data["assistant_message"]["role"] == "assistant"
        assert "TCP" in data["assistant_message"]["content"]
        assert data["assistant_message"]["citations_json"] is not None

    async def test_send_message_session_not_found(self, async_client, mock_session):
        """Returns 404 when session not found."""
        with patch(
            "app.api.chat.chat_service.send_message",
            new_callable=AsyncMock,
            side_effect=ValueError("Chat session not found"),
        ):
            response = await async_client.post(
                "/api/chat/sessions/bad-id/messages",
                json={"content": "Hello"},
            )

        assert response.status_code == 404

    async def test_send_message_empty_content_returns_422(self, async_client):
        """Empty content returns validation error."""
        response = await async_client.post(
            "/api/chat/sessions/session-001/messages",
            json={"content": ""},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestDeleteSession:
    """Tests for DELETE /api/chat/sessions/{session_id}."""

    async def test_delete_session_success(self, async_client, mock_session):
        """Deletes a session and returns 204."""
        with patch(
            "app.api.chat.chat_service.delete_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await async_client.delete("/api/chat/sessions/session-001")

        assert response.status_code == 204

    async def test_delete_session_not_found(self, async_client, mock_session):
        """Returns 404 when session not found."""
        with patch(
            "app.api.chat.chat_service.delete_session",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await async_client.delete("/api/chat/sessions/bad-id")

        assert response.status_code == 404
