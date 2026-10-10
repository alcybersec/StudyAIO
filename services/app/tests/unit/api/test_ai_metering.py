"""COST-01: request-time AI calls (chat, stream, Q&A, concepts) are metered
with tokens, for the caller, and the record is committed."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ConceptData, ConceptExtractionResult
from app.config import settings

RECORD = "app.services.billing_service.record_ai_call"


@pytest.mark.asyncio
class TestChatMetering:
    async def test_send_records_an_estimate_for_the_caller(
        self, async_client, mock_session, default_test_user
    ):
        user_msg = MagicMock(id="m1", role="user", content="hello", citations_json=None)
        asst_msg = MagicMock(id="m2", role="assistant", content="hi there " * 50)
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
                "/api/chat/sessions/s1/messages", json={"content": "hello"}
            )

        assert response.status_code == 200
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.kwargs["prompt_text"] == "hello"
        assert record.await_args.kwargs["output_text"] == "hi there " * 50
        mock_session.commit.assert_awaited()

    async def test_stream_records_streamed_text_for_the_caller(
        self, async_client, mock_session, default_test_user
    ):
        async def fake_stream(**kwargs):
            yield {"event": "token", "data": "Hel"}
            yield {"event": "token", "data": "lo"}
            yield {"event": "done", "data": {"id": "m2"}}

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
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.kwargs["output_text"] == "Hello"
        mock_session.commit.assert_awaited()


def _msg_response() -> dict:

    return {
        "id": "m",
        "session_id": "s1",
        "role": "assistant",
        "content": "x",
        "citations": None,
        "created_at": "2026-01-01T00:00:00",
    }


@pytest.mark.asyncio
class TestQAMetering:
    async def test_ask_records_agent_tokens_and_commits(
        self, async_client, mock_session, default_test_user
    ):
        agent = MagicMock()
        agent.answer_question = AsyncMock(return_value=MagicMock(answer="42", citations=[]))
        chunk = {
            "ref": 1,
            "chunk_id": "c1",
            "text": "context",
            "text_snippet": "context",
            "course_code": "C1",
            "week": 1,
            "page_ref": 1,
        }
        with (
            patch("app.api.qa.quota_service.check_ai_quota", new_callable=AsyncMock),
            patch("app.api.qa.get_embedding_provider") as prov,
            patch(
                "app.api.qa.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[chunk],
            ),
            patch("app.api.qa.get_agent", return_value=agent),
            patch(
                "app.services.settings_service.get_user_ai_context",
                new_callable=AsyncMock,
                return_value=({}, "en"),
            ),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            prov.return_value.embed_texts.return_value = [[0.1]]
            await async_client.post("/api/qa/ask", json={"question": "why?"})

        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.kwargs["agent"] is agent
        assert record.await_args.kwargs["output_text"] == "42"
        assert "context" in record.await_args.kwargs["prompt_text"]
        mock_session.commit.assert_awaited()

    async def test_top_k_above_the_cap_is_rejected(self, async_client):
        response = await async_client.post(
            "/api/qa/ask", json={"question": "why?", "top_k": 100000}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestConceptMetering:
    async def test_extraction_meters_the_agent_call(self):
        from app.services import concept_service

        agent = MagicMock()
        agent.extract_concepts = AsyncMock(
            return_value=ConceptExtractionResult(
                concepts=[ConceptData(name="A", description="d", category="x")], relations=[]
            )
        )
        session = AsyncMock()
        session.add = MagicMock()
        empty = MagicMock()
        empty.all.return_value = []
        empty.scalar_one_or_none.return_value = None
        session.execute.return_value = empty

        with (
            patch("app.agents.factory.get_agent", return_value=agent),
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(concept_service, "_embed_concepts"),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            await concept_service.extract_and_save_concepts(
                session=session,
                artifact_id="a1",
                user_id="u1",
                course_id="c1",
                week=1,
                extraction_text="text",
            )

        assert record.await_args.args[1] == "u1"
        assert record.await_args.kwargs["agent"] is agent
        assert record.await_args.kwargs["prompt_text"] == "text"


class TestEstimateIsDocumentedFloor:
    def test_floor_is_positive(self):
        assert settings.ai_call_estimate_min_tokens > 0
