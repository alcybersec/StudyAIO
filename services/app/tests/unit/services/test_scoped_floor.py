"""Regression for GL#35 follow-up: the floor must not reject scoped questions.

Prod case: "what was CSCI369 lecture 2 about?" scored 0.241 against the best of 36
indexed Week 2 chunks (floor 0.25) and got "I couldn't find this in your
materials". A turn with an explicit course+week scope that has indexed chunks
is relevant by construction, so the floor does not apply to it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from app.agents.base import AnswerResult
from app.config import settings
from app.services import retrieval
from app.services.chat_scope import detect_overview_intent
from app.services.chat_service import send_message, stream_message
from tests.unit.services.test_chat_carried_scope import (
    _course,
    _owned,
    _patch_lookup,
    _send_session,
)
from tests.unit.services.test_chat_service import _rag_patches

USER = "user-001"
PROD_SIMS = [0.241, 0.206, 0.185, 0.185, 0.169]
QUESTION = "what was CSCI369 lecture 2 about?"
SUMMARY_MD = "# CSCI369 - Week 2\nBuffer overflows overview."


def _chunks(sims: list[float]) -> list[dict]:
    return [
        {"chunk_id": f"c{i}", "text": f"chunk {i}", "similarity": s} for i, s in enumerate(sims)
    ]


def _summary(md: str = SUMMARY_MD) -> MagicMock:
    s = MagicMock()
    s.content_md = md
    return s


def _agent() -> AsyncMock:
    agent = AsyncMock()
    agent.answer_question.return_value = AnswerResult(answer="It covered X [1].", citations=[])
    return agent


def _summary_patch(summary):
    return patch(
        "app.services.chat_service.summary_service.get_owned_summary",
        AsyncMock(return_value=summary),
    )


class TestOverviewIntent:
    @pytest.mark.parametrize(
        "text",
        [
            "what was CSCI369 lecture 2 about?",
            "summarize week 3",
            "give me an overview of week 4",
            "what does week 2 cover?",
            "key points of lecture 5",
            "explain week 2",
        ],
    )
    def test_detects_overview_questions(self, text):
        assert detect_overview_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        ["how does ASLR work?", "what is a canary?", "hello", "quiz me on week 2"],
    )
    def test_ignores_specific_questions(self, text):
        assert detect_overview_intent(text) is False


class TestDecision:
    def test_scoped_bypasses_floor_and_keeps_all(self):
        kept, decision = retrieval.apply_floor(
            _chunks(PROD_SIMS), stage="chat", course_scoped=True, week_scoped=True
        )
        assert len(kept) == 5
        assert decision == "bypassed_scoped"

    def test_unscoped_applies_floor(self):
        kept, decision = retrieval.apply_floor(
            _chunks([0.3, 0.2]), stage="chat", course_scoped=False, week_scoped=False
        )
        assert [c["similarity"] for c in kept] == [0.3]
        assert decision == "floor_applied"

    def test_unscoped_all_below_is_below_floor(self):
        kept, decision = retrieval.apply_floor(
            _chunks([0.2]), stage="chat", course_scoped=False, week_scoped=False
        )
        assert kept == []
        assert decision == "below_floor"

    def test_course_only_uses_lower_floor(self):
        low = settings.retrieval_course_scope_min_similarity
        assert low < settings.retrieval_min_similarity
        kept, _ = retrieval.apply_floor(
            _chunks([low, low - 0.01]), stage="chat", course_scoped=True, week_scoped=False
        )
        assert len(kept) == 1

    def test_logs_best_similarity_and_decision_without_content(self):
        with capture_logs() as logs:
            retrieval.apply_floor(
                _chunks(PROD_SIMS), stage="qa", course_scoped=True, week_scoped=True
            )
        event = next(e for e in logs if e["event"] == "retrieval_decision")
        assert event["decision"] == "bypassed_scoped"
        assert event["best_similarity"] == pytest.approx(0.241)
        assert event["stage"] == "qa"
        assert "chunk 0" not in str(event)

    def test_counter_labels_stay_stage_only(self):
        assert retrieval.RETRIEVAL_BELOW_FLOOR._labelnames == ("stage",)


class TestChatScopedBypass:
    @pytest.mark.asyncio
    async def test_prod_case_is_answered_with_scope_chunks_and_summary(self):
        session = _send_session([])
        agent = _agent()
        search = AsyncMock(return_value=_chunks(PROD_SIMS))
        summary = AsyncMock(return_value=_summary())
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            _patch_lookup(_owned(_course("CSCI369", "c369"))),
            patch("app.services.chat_service.summary_service.get_owned_summary", summary),
        ):
            _, assistant = await send_message(session, "session-001", USER, QUESTION)
        assert assistant.ai_called is True
        assert assistant.content == "It covered X [1]."
        sent_chunks = agent.answer_question.await_args.args[1]
        assert len(sent_chunks) == 5
        asked = agent.answer_question.await_args.args[0]
        assert "Buffer overflows overview." in asked
        assert "CSCI369" in asked and "Week 2" in asked
        # floor 1: both lookups carry the caller
        assert search.await_args.kwargs["user_id"] == USER
        assert search.await_args.kwargs["course_id"] == "c369"
        assert search.await_args.kwargs["week"] == 2
        assert summary.await_args.kwargs["user_id"] == USER  # load-bearing
        assert summary.await_args.args[1:] == ("c369", 2)

    @pytest.mark.asyncio
    async def test_non_overview_scoped_question_bypasses_floor_without_summary(self):
        session = _send_session([])
        agent = _agent()
        search = AsyncMock(return_value=_chunks([0.05, 0.04]))
        summary = AsyncMock(return_value=_summary())
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            _patch_lookup(_owned(_course("CSCI369", "c369"))),
            patch("app.services.chat_service.summary_service.get_owned_summary", summary),
        ):
            _, assistant = await send_message(
                session, "session-001", USER, "how does CSCI369 week 2 canary work?"
            )
        assert assistant.ai_called is True
        summary.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_overview_without_summary_still_answers_from_chunks(self):
        session = _send_session([])
        agent = _agent()
        search = AsyncMock(return_value=_chunks(PROD_SIMS))
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            _patch_lookup(_owned(_course("CSCI369", "c369"))),
            _summary_patch(None),
        ):
            _, assistant = await send_message(session, "session-001", USER, QUESTION)
        assert assistant.ai_called is True
        assert agent.answer_question.await_args.args[0] == QUESTION

    @pytest.mark.asyncio
    async def test_unscoped_low_similarity_still_not_found_without_ai(self):
        session = _send_session([])
        agent = _agent()
        search = AsyncMock(return_value=_chunks(PROD_SIMS))
        summary = AsyncMock()
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            patch("app.services.chat_service.summary_service.get_owned_summary", summary),
        ):
            _, assistant = await send_message(session, "session-001", USER, "hello there")
        assert assistant.ai_called is False
        assert assistant.content == retrieval.not_found_reply(None, None)
        agent.answer_question.assert_not_awaited()
        summary.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_prod_case_is_answered(self):
        session = _send_session([])
        agent = MagicMock()

        async def tokens(*args, **kwargs):
            yield "It covered X"

        agent.stream_answer = MagicMock(side_effect=tokens)
        search = AsyncMock(return_value=_chunks(PROD_SIMS))
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with (
            p1,
            p2,
            p3,
            p4,
            _patch_lookup(_owned(_course("CSCI369", "c369"))),
            _summary_patch(_summary()),
        ):
            events = [e async for e in stream_message(session, "session-001", USER, QUESTION)]
        agent.stream_answer.assert_called_once()
        assert "Buffer overflows overview." in agent.stream_answer.call_args.args[0]
        assert len(agent.stream_answer.call_args.args[1]) == 5
        assert [e["data"] for e in events if e["event"] == "token"] == ["It covered X"]


class TestQAScopedBypass:
    @pytest.mark.asyncio
    async def test_scoped_qa_bypasses_floor_and_adds_summary(
        self, async_client, mock_session, default_test_user
    ):
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="Covered X [1].", citations=[])
        provider = MagicMock()
        provider.embed_texts.return_value = [[0.1] * 384]
        course = MagicMock()
        course.id = "c369"
        summary = AsyncMock(return_value=_summary())
        search = AsyncMock(return_value=_chunks(PROD_SIMS))
        with (
            patch("app.api.qa.get_embedding_provider", return_value=provider),
            patch("app.api.qa.search_service.search_chunks", search),
            patch("app.api.qa.course_service.get_course_by_code", AsyncMock(return_value=course)),
            patch("app.api.qa.summary_service.get_owned_summary", summary),
            patch("app.api.qa.get_agent", return_value=agent),
            patch("app.api.qa.billing_service.record_ai_call", AsyncMock()),
        ):
            response = await async_client.post(
                "/api/qa/ask",
                json={
                    "question": "what was lecture 2 about?",
                    "course_code": "CSCI369",
                    "week": 2,
                },
            )
        assert response.status_code == 200
        assert response.json()["answer"] == "Covered X [1]."
        assert len(agent.answer_question.await_args.args[1]) == 5
        assert "Buffer overflows overview." in agent.answer_question.await_args.args[0]
        assert summary.await_args.kwargs["user_id"] == default_test_user.id  # load-bearing
        assert search.await_args.kwargs["user_id"] == default_test_user.id
