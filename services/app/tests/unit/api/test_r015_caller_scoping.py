"""R-015 floor-1 wiring pins: owner-supplied ids must be resolved for the caller.

Each test asserts the lookup mock received the caller's id -- a bare status
code passes on an unscoped endpoint because the mock answers either way (see
`.claude/rules/tests.md`, "Owner-Scoped Endpoints").
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.services import (
    achievement_service,
    exam_service,
    srs_service,
    summary_service,
    timed_session_service,
)

CALLER = "user-caller"


def _sql(stmt) -> str:
    """Render a statement with literal values so ownership filters are visible."""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _session_capturing() -> tuple[AsyncMock, list]:
    """A session whose execute() records each statement and returns an empty result."""
    statements: list = []
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None

    async def execute(stmt, *a, **k):
        statements.append(stmt)
        return result

    session = AsyncMock()
    session.execute = execute
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session, statements


# ── API wiring ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestReviewEndpointWiring:
    async def test_review_looks_flashcard_up_as_caller_and_404s_foreign(
        self, async_client, default_test_user
    ):
        with (
            patch(
                "app.api.study.srs_service.get_owned_flashcard",
                new_callable=AsyncMock,
                return_value=None,
            ) as lookup,
            patch("app.api.study.srs_service.record_review", new_callable=AsyncMock) as record,
        ):
            resp = await async_client.post(
                "/api/study/review", json={"flashcard_id": "fc-foreign", "quality": 3}
            )
        assert resp.status_code == 404
        assert lookup.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing
        record.assert_not_awaited()


@pytest.mark.asyncio
class TestQuizAttemptEndpointWiring:
    async def test_question_lookup_is_caller_scoped_and_foreign_404s(
        self, async_client, default_test_user
    ):
        with (
            patch(
                "app.api.study.exam_service.get_owned_quiz_question",
                new_callable=AsyncMock,
                return_value=None,
            ) as lookup,
            patch(
                "app.api.study.exam_service.record_quiz_attempt", new_callable=AsyncMock
            ) as record,
        ):
            resp = await async_client.post(
                "/api/study/quiz-attempt",
                json={"quiz_question_id": "qq-foreign", "selected_answer": "A", "is_correct": True},
            )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Quiz question not found"
        assert lookup.await_args.kwargs.get("user_id") == default_test_user.id
        record.assert_not_awaited()

    async def test_foreign_exam_id_404s_with_exam_cause(self, async_client, default_test_user):
        with (
            patch(
                "app.api.study.exam_service.get_owned_quiz_question",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "app.api.study.exam_service.get_exam", new_callable=AsyncMock, return_value=None
            ) as exam_lookup,
            patch(
                "app.api.study.exam_service.record_quiz_attempt", new_callable=AsyncMock
            ) as record,
        ):
            resp = await async_client.post(
                "/api/study/quiz-attempt",
                json={
                    "quiz_question_id": "qq-mine",
                    "exam_id": "exam-foreign",
                    "selected_answer": "A",
                    "is_correct": True,
                },
            )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Exam not found"
        assert exam_lookup.await_args.kwargs.get("user_id") == default_test_user.id
        record.assert_not_awaited()


@pytest.mark.asyncio
class TestTimedPlanEndpointWiring:
    async def test_timed_plan_receives_caller_id(self, async_client, default_test_user):
        plan = timed_session_service.TimedSessionPlan(30, [], [], 0, 0, None, None)
        with patch(
            "app.api.study.timed_session_service.generate_timed_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ) as gen:
            resp = await async_client.post("/api/study/timed-plan", json={"minutes": 30})
        assert resp.status_code == 200
        assert gen.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestQaAskCourseWiring:
    async def test_course_code_resolved_for_caller(self, async_client, default_test_user):
        with (
            patch(
                "app.api.qa.course_service.get_course_by_code",
                new_callable=AsyncMock,
                return_value=None,
            ) as lookup,
            patch("app.api.qa.quota_service.check_ai_quota", new_callable=AsyncMock),
        ):
            resp = await async_client.post(
                "/api/qa/ask", json={"question": "q", "course_code": "PRIVATE77"}
            )
        assert resp.status_code == 404
        assert lookup.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestWeekDetailSummaryWiring:
    async def test_summary_lookup_carries_caller(self, async_client, default_test_user):
        course = MagicMock()
        course.id = "c1"
        course.code = "NET101"
        course.name = "Net"
        course.created_at = datetime(2024, 1, 1)
        course.updated_at = datetime(2024, 1, 1)
        with (
            patch(
                "app.api.courses.course_service.get_course_by_code",
                new_callable=AsyncMock,
                return_value=course,
            ),
            patch(
                "app.api.courses.artifact_service.list_artifacts",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.courses.summary_service.get_summary_for_week",
                new_callable=AsyncMock,
                return_value=None,
            ) as lookup,
        ):
            await async_client.get("/api/courses/NET101/weeks/1")
        assert lookup.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestMarkNotifiedWiring:
    async def test_mark_notified_receives_caller_id(self, async_client, default_test_user):
        with patch(
            "app.api.gamification.achievement_service.mark_notified", new_callable=AsyncMock
        ) as mark:
            resp = await async_client.post(
                "/api/gamification/achievements/mark-notified",
                json={"user_achievement_ids": ["ua-foreign"]},
            )
        assert resp.status_code == 204
        assert mark.await_args.kwargs.get("user_id") == default_test_user.id


# ── Service-level: the statement itself must filter on the caller ──────


@pytest.mark.asyncio
class TestServiceQueriesFilterOnCaller:
    async def test_get_owned_flashcard_filters_on_course_owner(self):
        session, stmts = _session_capturing()
        assert await srs_service.get_owned_flashcard(session, "fc-1", user_id=CALLER) is None
        sql = _sql(stmts[0])
        assert "courses.user_id = 'user-caller'" in sql
        assert "flashcards.id = 'fc-1'" in sql

    async def test_record_review_schedule_row_lookup_is_scoped(self):
        session, stmts = _session_capturing()
        await srs_service.record_review(session, "fc-1", 4, user_id=CALLER)
        assert "flashcard_reviews.user_id = 'user-caller'" in _sql(stmts[0])

    async def test_get_owned_quiz_question_filters_on_course_owner(self):
        session, stmts = _session_capturing()
        assert await exam_service.get_owned_quiz_question(session, "qq-1", user_id=CALLER) is None
        sql = _sql(stmts[0])
        assert "courses.user_id = 'user-caller'" in sql
        assert "quiz_questions.id = 'qq-1'" in sql

    async def test_timed_plan_quiz_query_is_scoped_and_cards_get_user_id(self):
        session, stmts = _session_capturing()
        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ) as due:
            await timed_session_service.generate_timed_plan(
                session, 30, course_code="NET101", user_id=CALLER
            )
        assert due.await_args.kwargs.get("user_id") == CALLER
        assert "courses.user_id = 'user-caller'" in _sql(stmts[-1])

    async def test_timed_plan_exam_lookup_is_scoped(self):
        session, stmts = _session_capturing()
        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await timed_session_service.generate_timed_plan(
                session, 30, exam_id="exam-x", user_id=CALLER
            )
        assert "exams.user_id = 'user-caller'" in _sql(stmts[0])

    async def test_get_summary_for_week_joins_on_course_owner(self):
        session, stmts = _session_capturing()
        await summary_service.get_summary_for_week(session, "NET101", 1, user_id=CALLER)
        assert "courses.user_id = 'user-caller'" in _sql(stmts[0])

    async def test_mark_notified_filters_on_owner(self):
        session, stmts = _session_capturing()
        await achievement_service.mark_notified(session, ["ua-1"], user_id=CALLER)
        assert "user_achievements.user_id = 'user-caller'" in _sql(stmts[0])
