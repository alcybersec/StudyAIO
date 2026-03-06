"""Tests for the chat streaming SSE API endpoint."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def _reset_sse_app_status():
    """Reset sse_starlette AppStatus to avoid event loop binding issues between tests."""
    try:
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = asyncio.Event()
    except Exception:
        pass


@pytest.mark.asyncio
class TestStreamEndpoint:
    """Tests for POST /api/chat/sessions/{session_id}/messages/stream."""

    async def test_stream_endpoint_returns_sse(self, async_client, mock_session) -> None:
        """Streaming endpoint returns text/event-stream content type with SSE events."""
        _reset_sse_app_status()

        async def mock_stream_gen(*args, **kwargs):
            yield {"event": "user_message", "data": {"id": "msg-001"}}
            yield {"event": "token", "data": "Hello"}
            yield {"event": "token", "data": " World"}
            yield {
                "event": "done",
                "data": {
                    "id": "msg-002",
                    "content": "Hello World",
                    "citations_json": None,
                },
            }

        with patch(
            "app.api.chat.chat_service.stream_message",
            side_effect=mock_stream_gen,
        ):
            response = await async_client.post(
                "/api/chat/sessions/session-001/messages/stream",
                json={"content": "Tell me about TCP"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Parse SSE body to verify events were streamed
        body = response.text
        assert "event: user_message" in body or "event:user_message" in body
        assert "event: token" in body or "event:token" in body
        assert "event: done" in body or "event:done" in body

    async def test_stream_endpoint_not_found_session(
        self, async_client, mock_session
    ) -> None:
        """Streaming endpoint handles session not found gracefully via SSE error event."""
        _reset_sse_app_status()

        async def mock_stream_not_found(*args, **kwargs):
            yield {"event": "error", "data": "Chat session not found"}

        with patch(
            "app.api.chat.chat_service.stream_message",
            side_effect=mock_stream_not_found,
        ):
            response = await async_client.post(
                "/api/chat/sessions/bad-session-id/messages/stream",
                json={"content": "Hello"},
            )

        # SSE endpoint returns 200 even for errors (error is in the stream)
        assert response.status_code == 200
        body = response.text
        assert "error" in body
        assert "not found" in body.lower()

    async def test_stream_endpoint_empty_content_returns_422(
        self, async_client
    ) -> None:
        """Empty content returns validation error."""
        response = await async_client.post(
            "/api/chat/sessions/session-001/messages/stream",
            json={"content": ""},
        )

        assert response.status_code == 422
