"""R-010: review_items and quiz_attempts carry their own user_id.

Ownership used to be derived by joining to a parent (artifact/summary/course for
review items, question -> course for quiz attempts). Both tables now have a
``user_id`` column, so every read filters on it directly and every write sets it.

These assert the *wiring*: the caller's id reaches the row on write, and appears
as a bound predicate on the table itself on read. A join to a parent that merely
mentions ``user_id`` does not satisfy them.

Orphaned legacy review items may keep a NULL ``user_id``; a direct equality
filter never matches NULL, so they are invisible rather than public (fail-closed).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.services import (
    course_service,
    exam_service,
    onboarding_service,
    review_service,
    weakspot_service,
)

OWNER = "owner-r010"


def _sql(query) -> str:
    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _recording_session():
    """AsyncMock session recording the SQL of every executed statement."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    result.first.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    result.rowcount = 0
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=None)
    return session


def _executed(session) -> list[str]:
    return [_sql(c.args[0]) for c in session.execute.await_args_list] + [
        _sql(c.args[0]) for c in session.scalar.await_args_list
    ]


def _assert_attempts_scoped(statements: list[str]) -> None:
    touching = [s for s in statements if "quiz_attempts" in s]
    assert touching, "expected at least one statement on quiz_attempts"
    for sql in touching:
        assert f"quiz_attempts.user_id = '{OWNER}'" in sql, f"not filtered directly:\n{sql}"


class TestReviewItemWrites:
    async def test_create_review_item_sets_user_id(self, mock_session):
        item = await review_service.create_review_item(
            mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="art-1",
            payload={},
            suggested_values={},
            user_id=OWNER,
        )
        assert item.user_id == OWNER
        assert mock_session.add.call_args_list[0].args[0].user_id == OWNER

    async def test_create_review_item_requires_user_id(self, mock_session):
        with pytest.raises(TypeError):
            await review_service.create_review_item(  # type: ignore[call-arg]
                mock_session,
                review_type="x",
                entity_type="lecture_artifact",
                entity_id="art-1",
                payload={},
                suggested_values={},
            )

    async def test_notification_lookup_is_scoped_to_the_owner(self, mock_session):
        await review_service.create_review_item(
            mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="art-1",
            payload={},
            suggested_values={},
            user_id=OWNER,
        )
        lookup = _sql(mock_session.execute.await_args.args[0])
        assert f"lecture_artifacts.user_id = '{OWNER}'" in lookup


class TestReviewItemReads:
    @pytest.mark.parametrize(
        "call",
        [
            lambda s: review_service.list_pending_reviews(s, user_id=OWNER),
            lambda s: review_service.list_reviews_by_status(s, "resolved", user_id=OWNER),
            lambda s: review_service.get_review_item(s, "rid", user_id=OWNER),
            lambda s: review_service.count_pending_reviews(s, user_id=OWNER),
        ],
        ids=["pending", "by_status", "get", "count"],
    )
    async def test_filters_on_the_row_s_own_user_id(self, call):
        session = _recording_session()
        await call(session)
        sql = _sql(session.execute.await_args.args[0])
        assert f"review_items.user_id = '{OWNER}'" in sql
        # No ownership join / EXISTS onto a parent table any more.
        assert "EXISTS" not in sql
        assert "lecture_artifacts" not in sql
        assert "summaries" not in sql

    async def test_resolve_and_dismiss_stay_scoped(self):
        for fn in (
            lambda s: review_service.resolve_review_item(s, "rid", {}, user_id=OWNER),
            lambda s: review_service.dismiss_review_item(s, "rid", user_id=OWNER),
        ):
            session = _recording_session()
            with pytest.raises(ValueError, match="not found"):
                await fn(session)
            assert f"review_items.user_id = '{OWNER}'" in _sql(session.execute.await_args.args[0])


class TestQuizAttemptWrites:
    async def test_record_quiz_attempt_sets_user_id(self, mock_session):
        attempt = await exam_service.record_quiz_attempt(
            mock_session,
            quiz_question_id="qq",
            selected_answer="A",
            is_correct=True,
            user_id=OWNER,
        )
        assert attempt.user_id == OWNER

    async def test_record_quiz_attempt_requires_user_id(self, mock_session):
        with pytest.raises(TypeError):
            await exam_service.record_quiz_attempt(  # type: ignore[call-arg]
                mock_session, quiz_question_id="qq", selected_answer="A", is_correct=True
            )

    async def test_endpoint_passes_the_caller_to_record_quiz_attempt(
        self, async_client, default_test_user
    ):
        question = MagicMock()
        question.course_id = "c1"
        attempt = MagicMock(
            id="a1",
            quiz_question_id="qq",
            exam_id=None,
            selected_answer="A",
            is_correct=False,
            time_spent_ms=None,
            created_at=datetime.now(UTC),
        )
        record = AsyncMock(return_value=attempt)
        with (
            patch(
                "app.api.study.exam_service.get_owned_quiz_question",
                new=AsyncMock(return_value=question),
            ),
            patch("app.api.study.exam_service.record_quiz_attempt", new=record),
            patch("app.api.study.usage_service.record", new=AsyncMock()),
        ):
            response = await async_client.post(
                "/api/study/quiz-attempt",
                json={"quiz_question_id": "qq", "selected_answer": "A", "is_correct": False},
            )
        assert response.status_code == 201, response.text
        assert record.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing


class TestQuizAttemptReads:
    async def test_exam_progress_filters_attempts_directly(self):
        session = _recording_session()
        exam = MagicMock(course_id="c1", weeks_scope=[1], exam_date=datetime.now(UTC))
        with patch.object(exam_service, "get_exam", new=AsyncMock(return_value=exam)):
            await exam_service.get_exam_progress(session, "e1", user_id=OWNER)
        attempts = [s for s in _executed(session) if "quiz_attempts" in s]
        _assert_attempts_scoped(attempts)
        assert all("JOIN quiz_questions" not in s for s in attempts)

    async def test_onboarding_attempt_check_filters_directly(self):
        session = _recording_session()
        await onboarding_service.get_status(session, user_id=OWNER)
        attempts = [s for s in _executed(session) if "quiz_attempts" in s]
        _assert_attempts_scoped(attempts)
        assert all("JOIN" not in s for s in attempts), attempts

    async def test_weakspot_inputs_filter_attempts_directly(self):
        session = _recording_session()
        await weakspot_service._load_inputs(
            session, user_id=OWNER, course_id=None, now=datetime.now(UTC)
        )
        _assert_attempts_scoped(_executed(session))

    async def test_weakspot_diagnostic_filters_attempts_directly(self):
        session = _recording_session()
        await weakspot_service.get_diagnostic_questions(
            session, user_id=OWNER, course_id="c1", week=1
        )
        _assert_attempts_scoped(_executed(session))

    async def test_weakspot_practice_candidates_filter_attempts_directly(self):
        session = _recording_session()
        spot = MagicMock(course_id="c1", week=1)
        await weakspot_service._practice_candidates(
            session, user_id=OWNER, focus=[MagicMock(spot=spot)], courses={"c1": "X"}
        )
        _assert_attempts_scoped(_executed(session))

    async def test_weakspot_plan_items_filter_attempts_directly(self):
        session = _recording_session()
        plan = MagicMock(
            built_at=datetime.now(UTC),
            items=[{"item_type": "quiz", "item_id": "q1"}],
        )
        await weakspot_service.resolve_plan_items(session, plan, user_id=OWNER)
        _assert_attempts_scoped(_executed(session))


class TestCourseDeleteScoping:
    async def test_course_delete_scopes_attempts_and_review_items(self):
        session = _recording_session()
        course = MagicMock(id="course-1")
        storage = MagicMock(put=AsyncMock())
        session.execute.return_value.scalars.return_value.all.return_value = ["art-1"]
        with patch.object(course_service, "_get_owned_course", new=AsyncMock(return_value=course)):
            await course_service.delete_course(session, OWNER, "X", storage=storage)
        deletes = [s for s in _executed(session) if s.startswith("DELETE FROM")]
        attempts = [s for s in deletes if s.startswith("DELETE FROM quiz_attempts")]
        reviews = [s for s in deletes if s.startswith("DELETE FROM review_items")]
        assert len(attempts) == 1 and f"quiz_attempts.user_id = '{OWNER}'" in attempts[0]
        assert len(reviews) == 1 and f"review_items.user_id = '{OWNER}'" in reviews[0]
