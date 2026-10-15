"""Usage events API (GL#37): view-event endpoint, admin readout, server-side emission."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User


def _make_user(role="user") -> MagicMock:
    user = MagicMock(spec=User)
    user.id = f"{role}-1"
    user.email = "tester@example.com"
    user.username = "tester"
    user.role = role
    user.tier = "free"
    user.is_active = True
    return user


@pytest.fixture
async def client_as(mock_session):
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    created = []

    def _build(role="user"):
        user = _make_user(role)

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_user_or_default] = lambda: user
        limiter.reset()
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        created.append(c)
        return c, user

    yield _build

    for c in created:
        await c.aclose()
    app.dependency_overrides.clear()


class TestPostUsageEvent:
    async def test_records_a_view_event_for_the_caller(self, client_as, mock_session):
        client, user = client_as()
        record = AsyncMock(return_value=True)
        with patch("app.api.usage.usage_service.record", record):
            response = await client.post("/api/usage-events", json={"event": "summary_viewed"})
        assert response.status_code == 204
        assert record.await_args.args[1] == user.id
        assert record.await_args.args[2] == "summary_viewed"
        mock_session.commit.assert_awaited()

    @pytest.mark.parametrize(
        "event", ["quiz_completed", "chat_message_sent", "upload_completed", "made_up"]
    )
    async def test_non_view_events_rejected(self, client_as, event):
        client, _ = client_as()
        record = AsyncMock()
        with patch("app.api.usage.usage_service.record", record):
            response = await client.post("/api/usage-events", json={"event": event})
        assert response.status_code == 422
        record.assert_not_awaited()

    async def test_properties_cannot_be_supplied(self, client_as):
        client, _ = client_as()
        record = AsyncMock()
        with patch("app.api.usage.usage_service.record", record):
            response = await client.post(
                "/api/usage-events",
                json={"event": "summary_viewed", "properties": {"note": "hi"}},
            )
        assert response.status_code == 422
        record.assert_not_awaited()

    async def test_foreign_course_is_404_and_lookup_is_scoped(self, client_as):
        client, user = client_as()
        lookup = AsyncMock(return_value=None)
        record = AsyncMock()
        with (
            patch("app.api.usage.course_service.get_course_by_id", lookup),
            patch("app.api.usage.usage_service.record", record),
        ):
            response = await client.post(
                "/api/usage-events", json={"event": "summary_viewed", "course_id": "not-mine"}
            )
        assert response.status_code == 404
        assert lookup.await_args.kwargs.get("user_id") == user.id  # load-bearing
        record.assert_not_awaited()

    async def test_rate_limited(self, client_as):
        client, _ = client_as()
        with (
            patch("app.api.usage.usage_service.record", AsyncMock(return_value=True)),
            patch("app.config.settings.rate_limit_usage_events", "2/minute"),
        ):
            codes = [
                (
                    await client.post("/api/usage-events", json={"event": "summary_viewed"})
                ).status_code
                for _ in range(3)
            ]
        assert codes == [204, 204, 429]


class TestAdminRetention:
    async def test_non_admin_forbidden(self, client_as):
        client, _ = client_as("user")
        with patch("app.api.usage.usage_service.retention_readout", AsyncMock()) as m:
            response = await client.get("/api/admin/usage/retention")
        assert response.status_code == 403
        m.assert_not_awaited()

    async def test_admin_gets_readout(self, client_as):
        client, _ = client_as("admin")
        payload = {
            "cohorts": [{"week_start": "2026-09-28", "signups": 4, "d1": 3, "d7": 2, "d30": None}],
            "features": [{"week_start": "2026-10-05", "event": "quiz_answered", "active_users": 2}],
        }
        split = [
            {
                "week_start": "2026-09-28",
                "with_plan": {"signups": 1, "d7": 1, "d30": None},
                "without_plan": {"signups": 3, "d7": 1, "d30": None},
            }
        ]
        with (
            patch(
                "app.api.usage.usage_service.retention_readout", AsyncMock(return_value=payload)
            ) as m,
            patch(
                "app.api.usage.usage_service.plan_split_readout", AsyncMock(return_value=split)
            ) as s,
        ):
            response = await client.get("/api/admin/usage/retention?weeks=4")
        assert response.status_code == 200
        assert response.json() == {**payload, "plan_split": split}
        assert s.await_args.kwargs.get("weeks") == 4
        assert m.await_args.kwargs.get("weeks") == 4

    async def test_weeks_bounded(self, client_as):
        client, _ = client_as("admin")
        assert (await client.get("/api/admin/usage/retention?weeks=27")).status_code == 422
        assert (await client.get("/api/admin/usage/retention?weeks=0")).status_code == 422


class TestServerSideEmission:
    async def test_flashcard_review_emits_event(self, async_client, default_test_user):
        review = MagicMock()
        review.id = "r"
        review.flashcard_id = "fc-1"
        review.ease_factor = 2.5
        review.interval_days = 1
        review.repetition_count = 1
        review.next_review_at = datetime(2026, 10, 12)
        review.last_reviewed_at = datetime(2026, 10, 11)
        record = AsyncMock(return_value=True)
        with (
            patch(
                "app.api.study.srs_service.get_owned_flashcard",
                AsyncMock(return_value=MagicMock(course_id="c-1")),
            ),
            patch("app.api.study.srs_service.record_review", AsyncMock(return_value=review)),
            patch("app.api.study.usage_service.record", record),
        ):
            response = await async_client.post(
                "/api/study/review", json={"flashcard_id": "fc-1", "quality": 4}
            )
        assert response.status_code == 200
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.args[2] == "flashcard_reviewed"
        assert record.await_args.kwargs.get("course_id") == "c-1"

    async def test_review_of_foreign_card_emits_nothing(self, async_client):
        record = AsyncMock()
        with (
            patch("app.api.study.srs_service.get_owned_flashcard", AsyncMock(return_value=None)),
            patch("app.api.study.usage_service.record", record),
        ):
            response = await async_client.post(
                "/api/study/review", json={"flashcard_id": "fc-1", "quality": 4}
            )
        assert response.status_code == 404
        record.assert_not_awaited()

    async def test_quiz_attempt_emits_event_without_answer_text(
        self, async_client, default_test_user
    ):
        attempt = MagicMock()
        attempt.id = "a"
        attempt.quiz_question_id = "q-1"
        attempt.selected_answer = "SECRET ANSWER TEXT"
        attempt.is_correct = True
        attempt.time_spent_ms = 1000
        attempt.exam_id = None
        attempt.attempted_at = None
        attempt.created_at = datetime(2026, 10, 11)
        record = AsyncMock(return_value=True)
        with (
            patch(
                "app.api.study.exam_service.get_owned_quiz_question",
                AsyncMock(return_value=MagicMock(course_id="c-1")),
            ),
            patch(
                "app.api.study.exam_service.record_quiz_attempt", AsyncMock(return_value=attempt)
            ),
            patch("app.api.study.usage_service.record", record),
        ):
            await async_client.post(
                "/api/study/quiz-attempt",
                json={
                    "quiz_question_id": "q-1",
                    "selected_answer": "SECRET ANSWER TEXT",
                    "is_correct": True,
                },
            )
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.args[2] == "quiz_answered"
        assert "SECRET" not in str(record.await_args)
