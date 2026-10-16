"""AI feedback endpoints (GL#36): owner scoping, validation mapping, admin gate."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User
from app.services import ai_feedback_service as svc


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


def _vote(**kw):
    vote = MagicMock()
    vote.target_type = kw.get("target_type", "summary")
    vote.target_id = kw.get("target_id", "s-1")
    vote.rating = kw.get("rating", -1)
    vote.reason = kw.get("reason", "inaccurate")
    vote.comment = kw.get("comment", "off")
    vote.course_id = kw.get("course_id", "c-1")
    vote.updated_at = datetime(2026, 10, 11, tzinfo=UTC)
    return vote


BODY = {"target_type": "summary", "target_id": "s-1", "rating": -1, "reason": "inaccurate"}


class TestPutFeedback:
    async def test_upserts_and_returns_the_vote(self, client_as, mock_session):
        client, user = client_as()
        upsert = AsyncMock(return_value=_vote())
        with (
            patch("app.api.ai_feedback.ai_feedback_service.upsert_vote", upsert),
            patch("app.api.ai_feedback.usage_service.record", AsyncMock()),
        ):
            response = await client.put("/api/feedback", json=BODY)
        assert response.status_code == 200
        assert response.json()["rating"] == -1
        assert response.json()["course_id"] == "c-1"
        assert upsert.await_args.kwargs.get("user_id") == user.id  # load-bearing
        mock_session.commit.assert_awaited()

    async def test_not_owned_target_is_404(self, client_as):
        client, user = client_as()
        upsert = AsyncMock(side_effect=svc.FeedbackTargetNotFoundError("nope"))
        with patch("app.api.ai_feedback.ai_feedback_service.upsert_vote", upsert):
            response = await client.put("/api/feedback", json=BODY)
        assert response.status_code == 404
        assert upsert.await_args.kwargs.get("user_id") == user.id
        # Same body for "missing" and "not yours": no existence probe.
        assert response.json()["detail"] == "Target not found"

    async def test_validation_error_is_422(self, client_as):
        client, _ = client_as()
        upsert = AsyncMock(side_effect=ValueError("rating must be 1 or -1"))
        with patch("app.api.ai_feedback.ai_feedback_service.upsert_vote", upsert):
            response = await client.put("/api/feedback", json={**BODY, "rating": 3})
        assert response.status_code == 422

    async def test_comment_too_long_rejected_by_schema(self, client_as):
        client, _ = client_as()
        upsert = AsyncMock()
        with patch("app.api.ai_feedback.ai_feedback_service.upsert_vote", upsert):
            response = await client.put("/api/feedback", json={**BODY, "comment": "x" * 1001})
        assert response.status_code == 422
        upsert.assert_not_awaited()

    async def test_emits_feedback_usage_event_without_comment(self, client_as):
        client, user = client_as()
        record = AsyncMock()
        with (
            patch(
                "app.api.ai_feedback.ai_feedback_service.upsert_vote",
                AsyncMock(return_value=_vote()),
            ),
            patch("app.api.ai_feedback.usage_service.record", record),
        ):
            await client.put("/api/feedback", json={**BODY, "comment": "private words"})
        assert record.await_args.args[1] == user.id
        assert record.await_args.args[2] == "feedback_given"
        assert "private words" not in str(record.await_args)


class TestDeleteFeedback:
    async def test_removes_own_vote(self, client_as):
        client, user = client_as()
        delete = AsyncMock(return_value=True)
        with patch("app.api.ai_feedback.ai_feedback_service.delete_vote", delete):
            response = await client.delete("/api/feedback/summary/s-1")
        assert response.status_code == 204
        assert delete.await_args.kwargs.get("user_id") == user.id
        assert delete.await_args.kwargs.get("target_id") == "s-1"

    async def test_nothing_to_delete_is_404(self, client_as):
        client, user = client_as()
        delete = AsyncMock(return_value=False)
        with patch("app.api.ai_feedback.ai_feedback_service.delete_vote", delete):
            response = await client.delete("/api/feedback/summary/someone-elses")
        assert response.status_code == 404
        assert delete.await_args.kwargs.get("user_id") == user.id

    async def test_unknown_type_is_422(self, client_as):
        client, _ = client_as()
        delete = AsyncMock(side_effect=ValueError("bad target_type"))
        with patch("app.api.ai_feedback.ai_feedback_service.delete_vote", delete):
            response = await client.delete("/api/feedback/course/x")
        assert response.status_code == 422


class TestListMine:
    async def test_lists_only_own_votes(self, client_as):
        client, user = client_as()
        listing = AsyncMock(return_value=[_vote()])
        with patch("app.api.ai_feedback.ai_feedback_service.list_votes", listing):
            response = await client.get(
                "/api/feedback/mine?target_type=summary&target_ids=s-1&target_ids=s-2"
            )
        assert response.status_code == 200
        assert response.json()["items"][0]["target_id"] == "s-1"
        assert listing.await_args.kwargs.get("user_id") == user.id
        assert listing.await_args.kwargs.get("target_ids") == ["s-1", "s-2"]

    async def test_more_than_100_ids_rejected(self, client_as):
        client, _ = client_as()
        qs = "&".join(f"target_ids=t{i}" for i in range(101))
        response = await client.get(f"/api/feedback/mine?target_type=summary&{qs}")
        assert response.status_code == 422


class TestAdminAggregate:
    async def test_non_admin_forbidden(self, client_as):
        client, _ = client_as("user")
        with patch("app.api.ai_feedback.ai_feedback_service.admin_summary", AsyncMock()) as m:
            response = await client.get("/api/admin/ai-feedback")
        assert response.status_code == 403
        m.assert_not_awaited()

    async def test_admin_gets_aggregates(self, client_as):
        client, _ = client_as("admin")
        payload = {
            "total": 2,
            "by_target_type": {"summary": {"up": 1, "down": 1}},
            "by_reason": {"inaccurate": 1},
            "by_rating": {"up": 1, "down": 1},
            "recent_negative": [],
        }
        with patch(
            "app.api.ai_feedback.ai_feedback_service.admin_summary",
            AsyncMock(return_value=payload),
        ) as m:
            response = await client.get("/api/admin/ai-feedback?days=7")
        assert response.status_code == 200
        assert response.json()["by_rating"] == {"up": 1, "down": 1}
        assert m.await_args.kwargs.get("days") == 7
def test_admin_response_model_types_recent_negative():
    """SEC-009 N-3: the recent_negative rows are a typed model, not list[dict]."""
    from app.api.ai_feedback import AdminAIFeedbackResponse, RecentNegativeItem

    assert set(RecentNegativeItem.model_fields) == {
        "target_type",
        "reason",
        "comment",
        "course_id",
        "created_at",
    }
    ann = AdminAIFeedbackResponse.model_fields["recent_negative"].annotation
    assert ann == list[RecentNegativeItem]
    row = {
        "target_type": "summary",
        "reason": None,
        "comment": "c",
        "course_id": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "user_id": "must-not-leak",
    }
    out = AdminAIFeedbackResponse(
        total=1, by_target_type={}, by_reason={}, by_rating={}, recent_negative=[row]
    ).model_dump()
    assert "user_id" not in out["recent_negative"][0]
