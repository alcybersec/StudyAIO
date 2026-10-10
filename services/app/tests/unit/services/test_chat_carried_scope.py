"""GL#31: follow-up chat messages keep the course/week named in earlier turns."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from app.services import chat_service
from app.services.chat_service import _plan_message, send_message
from tests.unit.services.test_chat_service import (
    _make_chat_message,
    _make_chat_session,
    _rag_patches,
)

USER = "user-001"


def _course(code: str, cid: str) -> MagicMock:
    c = MagicMock()
    c.code = code
    c.id = cid
    return c


def _owned(*courses: MagicMock) -> AsyncMock:
    """get_course_by_code stand-in that only knows the caller's courses."""
    by_code = {c.code: c for c in courses}
    return AsyncMock(side_effect=lambda session, code, *, user_id: by_code.get(code))


def _patch_lookup(lookup: AsyncMock):
    return patch.object(chat_service.course_service, "get_course_by_code", lookup)


class TestCarriedScope:
    @pytest.mark.asyncio
    async def test_followup_carries_course_and_week_scope(self):
        lookup = _owned(_course("CSCI369", "c369"), _course("CSCI323", "c323"))
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(),
                USER,
                "What was the lecture 3 about",
                None,
                None,
                None,
                ["Explain buffer overflows in CSCI369"],
            )
        assert plan.course_id == "c369"
        assert plan.week == 3
        assert plan.from_message is True
        assert lookup.await_args.kwargs["user_id"] == USER  # load-bearing

    @pytest.mark.asyncio
    async def test_explicit_new_course_overrides_carried(self):
        lookup = _owned(_course("CSCI369", "c369"), _course("CSCI323", "c323"))
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(),
                USER,
                "and CSCI323 week 2?",
                None,
                None,
                None,
                ["Explain buffer overflows in CSCI369"],
            )
        assert plan.course_id == "c323"
        assert plan.week == 2

    @pytest.mark.asyncio
    async def test_explicit_request_course_wins_over_carried(self):
        lookup = _owned(_course("CSCI369", "c369"))
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(),
                USER,
                "what about lecture 3",
                "c999",
                None,
                None,
                ["Explain CSCI369"],
            )
        assert plan.course_id == "c999"
        lookup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_foreign_or_deleted_carried_course_is_not_used(self):
        # CSCI999 is not the caller's; the older CSCI369 is.
        lookup = _owned(_course("CSCI369", "c369"))
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(),
                USER,
                "explain more",
                None,
                None,
                None,
                ["about CSCI999", "about CSCI369"],
            )
        assert plan.course_id == "c369"
        # Only a foreign course in history: nothing carried, session scope kept.
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(), USER, "explain more", None, None, "c-session", ["about CSCI999"]
            )
        assert plan.course_id == "c-session"
        assert plan.from_message is False
        assert all(c.kwargs["user_id"] == USER for c in lookup.await_args_list)

    @pytest.mark.asyncio
    async def test_window_is_bounded(self):
        lookup = _owned(_course("CSCI369", "c369"))
        recent = ["hello"] * chat_service.CARRY_WINDOW + ["about CSCI369"]
        with _patch_lookup(lookup):
            plan = await _plan_message(AsyncMock(), USER, "more", None, None, None, recent)
        assert plan.course_id is None

    @pytest.mark.asyncio
    async def test_quiz_action_uses_carried_course(self):
        lookup = _owned(_course("CSCI369", "c369"))
        with _patch_lookup(lookup):
            plan = await _plan_message(
                AsyncMock(), USER, "create a test", None, None, None, ["about CSCI369"]
            )
        assert plan.action["course_code"] == "CSCI369"
        assert plan.action["course_id"] == "c369"


class TestWeekOnly:
    @pytest.mark.asyncio
    async def test_week_only_asks_which_course_listing_callers_courses(self):
        with patch.object(
            chat_service, "_courses_with_week", AsyncMock(return_value=["CSCI323", "CSCI369"])
        ) as cw:
            plan = await _plan_message(
                AsyncMock(), USER, "What was the lecture 3 about", None, None, None, []
            )
        assert plan.reply == "Which course for Week 3 — CSCI323 or CSCI369?"
        assert plan.course_id is None
        assert cw.await_args.args[1:] == (USER, 3)  # load-bearing

    @pytest.mark.asyncio
    async def test_week_only_single_matching_course_is_used(self):
        lookup = _owned(_course("CSCI369", "c369"))
        with (
            _patch_lookup(lookup),
            patch.object(chat_service, "_courses_with_week", AsyncMock(return_value=["CSCI369"])),
        ):
            plan = await _plan_message(AsyncMock(), USER, "lecture 3?", None, None, None, [])
        assert plan.course_id == "c369"
        assert plan.reply is None

    @pytest.mark.asyncio
    async def test_week_only_nothing_indexed_says_so(self):
        with patch.object(chat_service, "_courses_with_week", AsyncMock(return_value=[])):
            plan = await _plan_message(AsyncMock(), USER, "lecture 3?", None, None, None, [])
        assert "None of your courses have Week 3" in plan.reply


def _send_session(history: list) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    own = MagicMock()
    own.scalar_one_or_none.return_value = _make_chat_session()
    hist = MagicMock()
    hist.scalars.return_value.all.return_value = history
    session.execute = AsyncMock(side_effect=[own, hist])
    return session


class TestSendMessageCarried:
    @pytest.mark.asyncio
    async def test_two_turn_scenario_searches_only_carried_course_week(self):
        session = _send_session(
            [
                _make_chat_message(role="user", content="Explain ASLR in CSCI369"),
                _make_chat_message(role="assistant", content="ASLR is..."),
            ]
        )
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ok", citations=[])
        search = AsyncMock(return_value=[{"text": "x"}])
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with p1, p2, p3, p4, _patch_lookup(_owned(_course("CSCI369", "c369"))):
            await send_message(session, "session-001", USER, "What was the lecture 3 about")
        kw = search.await_args.kwargs
        assert (kw["course_id"], kw["week"], kw["user_id"]) == ("c369", 3, USER)

    @pytest.mark.asyncio
    async def test_carried_scope_with_no_chunks_replies_plainly(self):
        session = _send_session(
            [_make_chat_message(role="user", content="Explain ASLR in CSCI369")]
        )
        agent = AsyncMock()
        search = AsyncMock(return_value=[])
        p1, p2, p3, p4 = _rag_patches(agent, search)
        with p1, p2, p3, p4, _patch_lookup(_owned(_course("CSCI369", "c369"))):
            _, assistant = await send_message(session, "session-001", USER, "lecture 3?")
        assert assistant.content == "CSCI369 has no Week 3 material indexed yet."
        agent.answer_question.assert_not_called()
