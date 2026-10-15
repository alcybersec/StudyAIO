"""Targeted generation worker end to end (pipeline.targeted_generation v1, ADR 0007 Decision 5).

The task opens its own sessions and drives them with ``run_async`` on a fresh event
loop, so nothing here can live in the ``db_session`` SAVEPOINT. These tests are
therefore synchronous: each owns committed rows, runs every coroutine on a throwaway
loop (the pooled connections never reach the session loop) and deletes the users it
made, with everything they own, when it ends.

AI is a fake adapter handed in through the ``get_agent`` seam the task imported; no
provider is reached. Nothing asserts generated text, only what the worker did with it.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import func, select, update

from app.agents.base import FlashcardData, QuizQuestionData
from app.core.auth import ACCESS_TOKEN_COOKIE, create_access_token, hash_password
from app.core.database import async_session_factory, engine
from app.core.exceptions import AgentError
from app.core.rate_limit import limiter
from app.core.utils import generate_id
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.targeted_generation import TargetedGeneration
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.pipeline import targeted_task
from app.services import account_service

from ._support import FakeAgent, seed_course

SECRET = "sk-provider-secret-text-must-not-be-stored"


def _run(coro):
    """Drive a coroutine on a throwaway loop, leaving no pooled connection behind."""
    engine.sync_engine.dispose(close=False)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        engine.sync_engine.dispose(close=False)


class TargetedFake(FakeAgent):
    """A complete adapter that accepts ``focus`` and returns scripted items."""

    def __init__(self, quiz=None, cards=None, error=None, during=None):
        super().__init__()
        self.quiz, self.cards, self.error, self.during = quiz or [], cards or [], error, during
        self.focus = None

    async def _answer(self, items, focus):
        self.focus = focus
        self.usage.add(7, 11)
        if self.during is not None:
            await self.during()
        if self.error is not None:
            raise self.error
        return items

    async def generate_quiz(self, summary, extraction, count, focus=None):
        return await self._answer(self.quiz, focus)

    async def generate_flashcards(self, summary, extraction, count, focus=None):
        return await self._answer(self.cards, focus)


def _q(stem: str, page: int | None = 1) -> QuizQuestionData:
    return QuizQuestionData(
        question_type="short_answer",
        question=stem,
        correct_answer="ans",
        explanation="why",
        source_page_ref=page,
    )


def _c(front: str, page: int = 1) -> FlashcardData:
    return FlashcardData(front=front, back="b", tags=[], source_page_ref=page)


@pytest.fixture
def users(_run_migrations):
    """Factory for committed, consented users; deleted with their data afterwards."""
    made: list[str] = []

    async def _make() -> User:
        uid = generate_id()
        async with async_session_factory() as s:
            user = User(
                id=uid,
                email=f"tw-{uid[-12:]}@example.com",
                username=f"tw_{uid[-12:]}",
                hashed_password=hash_password("correct-horse-battery"),
                role="user",
                tier="free",
                is_active=True,
                email_verified=True,
                mfa_enabled=False,
                ai_processing_consent_at=datetime.now(UTC),
                ai_processing_consent_version=1,
            )
            s.add(user)
            await s.commit()
        made.append(uid)
        return user

    yield lambda: _run(_make())

    async def _cleanup() -> None:
        for uid in made:
            async with async_session_factory() as s:
                await account_service.delete_user_account(s, uid)
                await s.commit()

    _run(_cleanup())


async def _world(user, *, code="TGW101", quizzes=2, cards=0):
    """A committed course with one processed artifact (pages 1-3) and its first items."""
    async with async_session_factory() as s:
        world = await seed_course(
            s, user.id, code=code, week=1, flashcards=cards, quizzes=quizzes, with_chunks=False
        )
        await s.commit()
    return world


async def _request(user, world, kind="quiz") -> str:
    async with async_session_factory() as s:
        row = TargetedGeneration(
            user_id=user.id,
            course_id=world.course.id,
            week=1,
            kind=kind,
            status="queued",
            requested_count=5,
            topics=[],
        )
        s.add(row)
        await s.commit()
        return row.id


def _generate(gid: str, agent: TargetedFake) -> dict:
    with patch("app.pipeline.targeted_task.get_agent", return_value=agent):
        return targeted_task.generate_targeted_items(gid)


async def _row(gid: str) -> TargetedGeneration:
    async with async_session_factory() as s:
        return await s.get(TargetedGeneration, gid)


async def _items(model, gid: str) -> list:
    async with async_session_factory() as s:
        rows = await s.execute(select(model).where(model.targeted_generation_id == gid))
        return list(rows.scalars())


async def _usage(user) -> UsageRecord | None:
    async with async_session_factory() as s:
        return (
            await s.execute(select(UsageRecord).where(UsageRecord.user_id == user.id))
        ).scalar_one_or_none()


# ── completed ──────────────────────────────────────────────────────────


class TestCompleted:
    def test_items_are_inserted_with_provenance_and_cited_pages(self, users):
        alice = users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))
        agent = TargetedFake(quiz=[_q("Explain the three way handshake", 2), _q("Why UDP?", 3)])

        result = _generate(gid, agent)

        assert result["status"] == "completed" and result["user_id"] == alice.id
        row = _run(_row(gid))
        assert (row.status, row.created_count, row.error_code) == ("completed", 2, None)
        items = _run(_items(QuizQuestion, gid))
        assert {q.question: q.source_page_ref for q in items} == {
            "Explain the three way handshake": 2,
            "Why UDP?": 3,
        }
        for q in items:
            assert q.origin == "targeted" and q.targeted_generation_id == gid
            assert q.focus_topic and q.course_id == world.course.id and q.week == 1
            assert q.source_artifact_id == world.artifact.id
            assert 1 <= q.source_page_ref <= 3  # a page of the target extraction
        # Insert-only: the unit's earlier items are untouched.
        assert _run(_count_active(QuizQuestion, world.course.id)) == 4

    def test_missed_questions_reach_the_model_as_focus(self, users):
        alice = users()
        world = _run(_world(alice))

        async def miss():
            async with async_session_factory() as s:
                s.add(
                    QuizAttempt(
                        quiz_question_id=world.questions[0].id,
                        selected_answer="x",
                        is_correct=False,
                    )
                )
                await s.commit()

        _run(miss())
        gid = _run(_request(alice, world))
        agent = TargetedFake(quiz=[_q("Fresh stem about congestion", 1)])

        _generate(gid, agent)

        assert agent.focus.missed_questions == [world.questions[0].question]
        assert agent.focus.page_refs == [1]
        assert agent.focus.topics

    def test_flashcards_kind_inserts_cards(self, users):
        alice = users()
        world = _run(_world(alice, cards=1))
        gid = _run(_request(alice, world, kind="flashcards"))

        _generate(gid, TargetedFake(cards=[_c("Define congestion window", 2)]))

        (card,) = _run(_items(Flashcard, gid))
        assert (card.origin, card.targeted_generation_id) == ("targeted", gid)
        assert card.source_page_ref == 2 and card.focus_topic

    def test_usage_is_recorded_for_the_owner_only(self, users):
        alice, bob = users(), users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))

        _generate(gid, TargetedFake(quiz=[_q("Usage stem one", 1)]))

        record = _run(_usage(alice))
        assert (record.ai_calls_count, record.ai_tokens_input, record.ai_tokens_output) == (
            1,
            7,
            11,
        )
        assert _run(_usage(bob)) is None


async def _count_active(model, course_id: str) -> int:
    async with async_session_factory() as s:
        return await s.scalar(
            select(func.count())
            .select_from(model)
            .where(model.course_id == course_id, model.archived_at.is_(None))
        )


# ── drops ──────────────────────────────────────────────────────────────


class TestDrops:
    def test_uncited_items_are_dropped_and_counted(self, users):
        alice = users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))
        agent = TargetedFake(
            quiz=[_q("Cited item", 1), _q("Page nine does not exist", 9), _q("Zero page", 0)]
        )

        _generate(gid, agent)

        row = _run(_row(gid))
        assert (row.status, row.created_count, row.dropped_uncited_count) == ("completed", 1, 2)
        assert [q.question for q in _run(_items(QuizQuestion, gid))] == ["Cited item"]

    def test_duplicates_of_the_owners_items_are_dropped_not_other_users(self, users):
        alice, bob = users(), users()
        world = _run(_world(alice))
        existing = world.questions[0].question
        # Bob holds the very stem Alice is about to be generated: it must not count.
        bob_world = _run(_world(bob, code="TGB101", quizzes=0))
        shared = "Compare TCP and UDP congestion behaviour"

        async def bobs() -> None:
            async with async_session_factory() as s:
                s.add(
                    QuizQuestion(
                        course_id=bob_world.course.id,
                        week=1,
                        question_type="short_answer",
                        question=shared,
                        correct_answer="a",
                        explanation="e",
                        source_artifact_id=bob_world.artifact.id,
                        source_page_ref=1,
                    )
                )
                await s.commit()

        _run(bobs())
        gid = _run(_request(alice, world))

        _generate(gid, TargetedFake(quiz=[_q(existing, 1), _q(shared, 1)]))

        row = _run(_row(gid))
        assert (row.created_count, row.dropped_duplicate_count) == (1, 1)
        assert [q.question for q in _run(_items(QuizQuestion, gid))] == [shared]
        assert _run(_count_active(QuizQuestion, bob_world.course.id)) == 1  # untouched


# ── failure ────────────────────────────────────────────────────────────


class TestFailure:
    def test_provider_error_fails_with_a_short_code_and_no_items(self, users):
        alice = users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))

        result = _generate(gid, TargetedFake(error=AgentError(SECRET)))

        assert result["status"] == "failed"
        row = _run(_row(gid))
        assert (row.status, row.error_code, row.created_count) == ("failed", "ai_error", 0)
        assert len(row.error_code) <= 20 and SECRET not in repr(vars(row))
        assert _run(_items(QuizQuestion, gid)) == []
        # The call ran (and may have been billed), so it is metered.
        assert _run(_usage(alice)).ai_calls_count == 1

    def test_empty_model_output_fails_without_items(self, users):
        alice = users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))

        _generate(gid, TargetedFake(quiz=[]))

        row = _run(_row(gid))
        assert (row.status, row.error_code) == ("failed", "empty_output")


# ── recovery ───────────────────────────────────────────────────────────


class TestRecovery:
    def test_rows_past_the_timeout_fail_and_a_late_task_inserts_nothing(self, users):
        alice = users()
        world = _run(_world(alice))
        stuck, fresh = _run(_request(alice, world)), None

        async def age(gid: str, seconds: int, status: str) -> None:
            async with async_session_factory() as s:
                await s.execute(
                    update(TargetedGeneration)
                    .where(TargetedGeneration.id == gid)
                    .values(
                        status=status,
                        updated_at=datetime.now(UTC) - timedelta(seconds=seconds),
                    )
                )
                await s.commit()

        _run(age(stuck, targeted_task.STUCK_GENERATION_SECONDS + 60, "running"))

        assert targeted_task.recover_stuck_generations() == {"failed": 1}
        row = _run(_row(stuck))
        assert (row.status, row.error_code) == ("failed", "timeout")

        # The slow worker finally runs: the row is no longer in flight, so it is skipped.
        agent = TargetedFake(quiz=[_q("Late stem", 1)])
        assert _generate(stuck, agent)["status"] == "skipped"
        assert agent.calls == [] and _run(_items(QuizQuestion, stuck)) == []

        # A row inside the window is left alone.
        fresh = _run(_request(alice, world, kind="flashcards"))
        _run(age(fresh, 60, "running"))
        assert targeted_task.recover_stuck_generations() == {"failed": 0}
        assert _run(_row(fresh)).status == "running"

    def test_recovered_while_the_model_was_running_inserts_nothing(self, users):
        alice = users()
        world = _run(_world(alice))
        gid = _run(_request(alice, world))

        async def recovered_meanwhile() -> None:
            later = datetime.now(UTC) + timedelta(
                seconds=targeted_task.STUCK_GENERATION_SECONDS + 60
            )
            assert await targeted_task._recover_stuck(now=later) == [gid]

        agent = TargetedFake(quiz=[_q("Too late stem", 1)], during=recovered_meanwhile)

        result = _generate(gid, agent)

        assert result["status"] == "failed"
        row = _run(_row(gid))
        assert (row.status, row.error_code, row.created_count) == ("failed", "timeout", 0)
        assert _run(_items(QuizQuestion, gid)) == []


# ── the whole chain, over HTTP ─────────────────────────────────────────


def test_chain_attempts_scores_plan_request_task_poll_study_items(users):
    alice = users()
    world = _run(_world(alice, code="CHN101", quizzes=5))
    token = create_access_token(alice.id, alice.role, alice.tier)
    enqueued: list[str] = []

    async def api(method: str, url: str, **kw) -> httpx.Response:
        from app.main import app

        limiter.reset()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(ACCESS_TOKEN_COOKIE, token)
            return await client.request(method, url, **kw)

    async def answer_wrong() -> None:
        async with async_session_factory() as s:
            for q in world.questions:
                s.add(QuizAttempt(quiz_question_id=q.id, selected_answer="x", is_correct=False))
            await s.commit()

    _run(answer_wrong())

    scores = _run(api("GET", "/api/weak-spots")).json()
    (course,) = scores["courses"]
    assert course["course_id"] == world.course.id
    assert (course["weeks"][0]["week"], course["weeks"][0]["status"]) == (1, "weak")

    plan = _run(api("GET", "/api/study-plan/tonight")).json()
    assert [(f["course_id"], f["week"]) for f in plan["focus"]] == [(world.course.id, 1)]

    with patch("app.api.weakspots._enqueue_targeted", side_effect=enqueued.append):
        resp = _run(
            api(
                "POST",
                "/api/weak-spots/targeted",
                json={"course_id": world.course.id, "week": 1, "kind": "quiz"},
            )
        )
    assert resp.status_code == 202, resp.text
    gid = resp.json()["id"]
    assert enqueued == [gid]
    assert _run(api("GET", f"/api/weak-spots/targeted/{gid}")).json()["item_ids"] == []

    agent = TargetedFake(quiz=[_q("Chain stem one", 2), _q("Chain stem two", 3)])
    assert _generate(gid, agent)["status"] == "completed"

    polled = _run(api("GET", f"/api/weak-spots/targeted/{gid}")).json()
    assert polled["status"] == "completed" and polled["created_count"] == 2
    assert len(polled["item_ids"]) == 2

    fetched = _run(
        api("GET", "/api/study/items", params={"quiz_question_ids": polled["item_ids"]})
    ).json()
    assert sorted(q["id"] for q in fetched["quiz_questions"]) == sorted(polled["item_ids"])
    assert {q["origin"] for q in fetched["quiz_questions"]} == {"targeted"}
    assert all(q["focus_topic"] for q in fetched["quiz_questions"])
