"""M33-S1-AI-014 / GL#35: relevance floor and follow-up retrieval for chat."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from app.config import settings
from app.services import retrieval
from app.services.chat_service import send_message, stream_message
from tests.unit.services.test_chat_carried_scope import (
    _course,
    _owned,
    _patch_lookup,
    _send_session,
)
from tests.unit.services.test_chat_service import _make_chat_message, _rag_patches

USER = "user-001"
NOT_FOUND = "I couldn't find this in your materials for CSCI369."


def _chunk(sim: float) -> dict:
    return {"chunk_id": "c1", "text": "ASLR randomises addresses.", "similarity": sim}


def _counter(surface: str) -> float:
    return retrieval.RETRIEVAL_BELOW_FLOOR.labels(stage=surface)._value.get()


class TestHelpers:
    def test_filter_drops_chunks_below_floor(self):
        floor = settings.retrieval_min_similarity
        kept = retrieval.filter_by_floor([_chunk(floor + 0.1), _chunk(floor - 0.01)])
        assert [c["similarity"] for c in kept] == [floor + 0.1]

    def test_filter_keeps_chunk_exactly_at_floor(self):
        assert retrieval.filter_by_floor([_chunk(settings.retrieval_min_similarity)])

    def test_default_floor_is_inside_minilm_noise_band(self):
        assert 0.15 <= settings.retrieval_min_similarity <= 0.35

    @pytest.mark.parametrize(
        ("code", "week", "expected"),
        [
            ("CSCI369", 3, "I couldn't find this in your materials for CSCI369 Week 3."),
            ("CSCI369", None, "I couldn't find this in your materials for CSCI369."),
            (None, 3, "I couldn't find this in your materials for Week 3."),
            (None, None, "I couldn't find this in your materials for your courses."),
        ],
    )
    def test_not_found_reply_is_deterministic(self, code, week, expected):
        assert retrieval.not_found_reply(code, week) == expected

    def test_first_turn_query_is_bare_message(self):
        q = retrieval.build_retrieval_query(
            "what is ASLR?", code="CSCI369", week=3, previous_user_message=None
        )
        assert q == "what is ASLR?"

    def test_followup_query_carries_scope_previous_question_and_message(self):
        q = retrieval.build_retrieval_query(
            "what about the second one?",
            code="CSCI369",
            week=3,
            previous_user_message="list the stack protections",
        )
        assert "CSCI369 Week 3" in q
        assert "list the stack protections" in q
        assert q.endswith("what about the second one?")


class TestChatFloor:
    @pytest.mark.asyncio
    async def test_below_floor_replies_without_agent_or_usage(self):
        session = _send_session([_make_chat_message(role="user", content="about CSCI369")])
        agent = AsyncMock()
        search = AsyncMock(return_value=[_chunk(0.05)])
        before = _counter("chat")
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            _patch_lookup(_owned(_course("CSCI369", "c369"))),
            patch("app.services.billing_service.record_ai_call", AsyncMock()) as usage,
        ):
            _, assistant = await send_message(session, "session-001", USER, "any trivia?")
        assert assistant.content == NOT_FOUND
        assert assistant.citations_json is None
        assert assistant.ai_called is False
        agent.answer_question.assert_not_awaited()
        usage.assert_not_awaited()
        assert _counter("chat") == before + 1

    @pytest.mark.asyncio
    async def test_above_floor_is_answered_unchanged(self):
        session = _send_session([_make_chat_message(role="user", content="about CSCI369")])
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ASLR [1]", citations=[])
        search = AsyncMock(return_value=[_chunk(0.8), _chunk(0.01)])
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with p1, p2, p3, p4, _patch_lookup(_owned(_course("CSCI369", "c369"))):
            _, assistant = await send_message(session, "session-001", USER, "any trivia?")
        assert assistant.content == "ASLR [1]"
        assert assistant.ai_called is True
        sent = agent.answer_question.await_args.args[1]
        assert [c["similarity"] for c in sent] == [0.8]

    @pytest.mark.asyncio
    async def test_unscoped_below_floor_names_your_courses(self):
        session = _send_session([])
        agent = AsyncMock()
        search = AsyncMock(return_value=[_chunk(0.02)])
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with p1, p2, p3, p4:
            _, assistant = await send_message(session, "session-001", USER, "capital of France?")
        assert assistant.content == retrieval.not_found_reply(None, None)
        agent.answer_question.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_below_floor_skips_agent(self):
        session = _send_session([_make_chat_message(role="user", content="about CSCI369")])
        agent = MagicMock()
        search = AsyncMock(return_value=[_chunk(0.05)])
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with p1, p2, p3, p4, _patch_lookup(_owned(_course("CSCI369", "c369"))):
            events = [e async for e in stream_message(session, "session-001", USER, "any trivia?")]
        tokens = [e["data"] for e in events if e["event"] == "token"]
        assert tokens == [NOT_FOUND]
        agent.stream_answer.assert_not_called()
        done = next(e for e in events if e["event"] == "done")
        assert done["data"]["citations_json"] is None
        assert done["ai_called"] is False


def _embed_patches(agent, search):
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 384]
    return provider, (
        patch("app.services.chat_service.get_embedding_provider", return_value=provider),
        patch("app.services.chat_service.search_service.search_chunks", search),
        patch("app.services.chat_service.get_agent", return_value=agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
    )


class TestChatFollowUpQuery:
    @pytest.mark.asyncio
    async def test_followup_embeds_scope_previous_question_and_message(self):
        session = _send_session(
            [
                _make_chat_message(role="user", content="List the stack protections in CSCI369"),
                _make_chat_message(role="assistant", content="Canaries, ASLR, NX."),
            ]
        )
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ok", citations=[])
        search = AsyncMock(return_value=[_chunk(0.7)])
        provider, (p1, p2, p3, p4) = _embed_patches(agent, search)
        with p1, p2, p3, p4, _patch_lookup(_owned(_course("CSCI369", "c369"))):
            await send_message(session, "session-001", USER, "what about the second one?")
        text = provider.embed_texts.call_args.args[0][0]
        assert "CSCI369" in text
        assert "List the stack protections" in text
        assert "what about the second one?" in text
        # scoping wiring survives the rewrite (floor 1)
        assert search.await_args.kwargs["user_id"] == USER
        assert search.await_args.kwargs["course_id"] == "c369"

    @pytest.mark.asyncio
    async def test_first_turn_embeds_bare_message(self):
        session = _send_session([])
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ok", citations=[])
        search = AsyncMock(return_value=[_chunk(0.7)])
        provider, (p1, p2, p3, p4) = _embed_patches(agent, search)
        with p1, p2, p3, p4:
            await send_message(session, "session-001", USER, "what is ASLR?")
        assert provider.embed_texts.call_args.args[0] == ["what is ASLR?"]
