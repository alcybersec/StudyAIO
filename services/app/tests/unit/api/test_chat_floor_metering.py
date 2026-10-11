"""GL#35: a chat turn answered without the AI (below the floor) records no usage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.api.test_ai_metering import RECORD, _msg_response


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """sse_starlette binds a global Event to the first loop; give each test a fresh one."""
    import asyncio

    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = asyncio.Event()


@pytest.mark.asyncio
class TestNoSpendMetering:
    async def test_send_below_floor_records_no_usage(self, async_client, mock_session):
        user_msg = MagicMock(id="m1", role="user", content="q", citations_json=None)
        asst_msg = MagicMock(id="m2", role="assistant", content="not found", ai_called=False)
        with (
            patch("app.api.chat.quota_service.check_ai_quota", new_callable=AsyncMock),
            patch("app.api.chat._resolve_scope_course", new_callable=AsyncMock, return_value=None),
            patch(
                "app.api.chat.chat_service.send_message",
                new_callable=AsyncMock,
                return_value=(user_msg, asst_msg),
            ),
            patch("app.api.chat._message_to_response", return_value=_msg_response()),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(
                "/api/chat/sessions/s1/messages", json={"content": "q"}
            )
        assert response.status_code == 200
        record.assert_not_awaited()

    async def test_stream_below_floor_records_no_usage(self, async_client, mock_session):
        async def fake_stream(**kwargs):
            yield {"event": "token", "data": "not found"}
            yield {"event": "done", "data": {"id": "m2"}, "ai_called": False}

        with (
            patch("app.api.chat.quota_service.check_ai_quota", new_callable=AsyncMock),
            patch("app.api.chat._resolve_scope_course", new_callable=AsyncMock, return_value=None),
            patch("app.api.chat.chat_service.stream_message", new=fake_stream),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(
                "/api/chat/sessions/s1/messages/stream", json={"content": "q"}
            )
        assert response.status_code == 200
        assert "ai_called" not in response.text  # internal signal, not on the wire
        record.assert_not_awaited()
