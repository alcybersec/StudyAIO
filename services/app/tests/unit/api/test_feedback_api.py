"""Tests for the feedback endpoints.

The fixtures mirror `test_admin_api.py` so both files authenticate the same way.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User


def _make_user(**overrides) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = overrides.get("id", "u-1")
    user.email = overrides.get("email", "tester@example.com")
    user.username = overrides.get("username", "tester")
    user.role = overrides.get("role", "user")
    user.tier = "free"
    user.is_active = True
    return user


def _entry(**overrides):
    entry = MagicMock()
    entry.id = overrides.get("id", "f-1")
    entry.kind = overrides.get("kind", "bug")
    entry.message = overrides.get("message", "Summary tab renders empty")
    entry.route = overrides.get("route", "/courses/CSIT302/weeks/3")
    entry.app_version = overrides.get("app_version", "8d8841b")
    entry.status = overrides.get("status", "new")
    entry.created_at = None
    entry.user = _make_user()
    return entry


@pytest.fixture
async def client_as(mock_session):
    """Factory: an authenticated client for a user of the given role."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    created = []

    def _build(role="user"):
        user = _make_user(role=role, id=f"{role}-1")

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_user_or_default] = lambda: user
        limiter.reset()
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        created.append(c)
        return c

    yield _build

    for c in created:
        await c.aclose()
    app.dependency_overrides.clear()


class TestSubmitFeedback:
    async def test_accepts_a_report(self, client_as):
        client = client_as("user")
        with (
            patch(
                "app.api.feedback.feedback_service.submit_feedback",
                new_callable=AsyncMock,
                return_value=_entry(),
            ),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            response = await client.post(
                "/api/feedback", json={"kind": "bug", "message": "Summary tab renders empty"}
            )

        assert response.status_code == 201
        assert response.json()["kind"] == "bug"

    async def test_passes_the_route_and_build_through(self, client_as):
        """The client supplies these — the server only ever sees /api/feedback."""
        client = client_as("user")
        submit = AsyncMock(return_value=_entry())
        with (
            patch("app.api.feedback.feedback_service.submit_feedback", submit),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await client.post(
                "/api/feedback",
                json={
                    "kind": "bug",
                    "message": "blank",
                    "route": "/courses/CSIT302/weeks/3",
                    "app_version": "8d8841b",
                },
            )

        assert submit.await_args.kwargs["route"] == "/courses/CSIT302/weeks/3"
        assert submit.await_args.kwargs["app_version"] == "8d8841b"

    async def test_records_the_user_agent_from_the_request(self, client_as):
        client = client_as("user")
        submit = AsyncMock(return_value=_entry())
        with (
            patch("app.api.feedback.feedback_service.submit_feedback", submit),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await client.post(
                "/api/feedback",
                json={"kind": "bug", "message": "x"},
                headers={"user-agent": "Firefox/141.0"},
            )

        assert submit.await_args.kwargs["user_agent"] == "Firefox/141.0"

    async def test_files_it_against_the_caller(self, client_as):
        """Never a client-supplied user id."""
        client = client_as("user")
        submit = AsyncMock(return_value=_entry())
        with (
            patch("app.api.feedback.feedback_service.submit_feedback", submit),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await client.post(
                "/api/feedback",
                json={"kind": "bug", "message": "x", "user_id": "somebody-else"},
            )

        assert submit.await_args.args[1] == "user-1"

    async def test_a_bad_kind_is_a_400(self, client_as):
        client = client_as("user")
        with patch(
            "app.api.feedback.feedback_service.submit_feedback",
            new_callable=AsyncMock,
            side_effect=ValueError("Unknown feedback kind: complaint"),
        ):
            response = await client.post(
                "/api/feedback", json={"kind": "complaint", "message": "x"}
            )

        assert response.status_code == 400

    async def test_an_empty_message_is_rejected_by_the_schema(self, client_as):
        client = client_as("user")
        response = await client.post("/api/feedback", json={"kind": "bug", "message": ""})

        assert response.status_code == 422

    async def test_a_telegram_failure_still_returns_201(self, client_as):
        """The report is stored and committed before the ping is attempted."""
        client = client_as("user")
        with (
            patch(
                "app.api.feedback.feedback_service.submit_feedback",
                new_callable=AsyncMock,
                return_value=_entry(),
            ),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            response = await client.post("/api/feedback", json={"kind": "bug", "message": "x"})

        assert response.status_code == 201

    async def test_the_acknowledgement_does_not_echo_the_reporter(self, client_as):
        """They know who they are; the field is for admin listings."""
        client = client_as("user")
        with (
            patch(
                "app.api.feedback.feedback_service.submit_feedback",
                new_callable=AsyncMock,
                return_value=_entry(),
            ),
            patch(
                "app.api.feedback.feedback_service.notify_admins",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            response = await client.post("/api/feedback", json={"kind": "bug", "message": "x"})

        assert response.json()["user_email"] is None


class TestAdminFeedback:
    async def test_lists_with_the_reporter(self, client_as):
        client = client_as("admin")
        with (
            patch(
                "app.api.feedback.feedback_service.list_feedback",
                new_callable=AsyncMock,
                return_value=([_entry()], 1),
            ),
            patch(
                "app.api.feedback.feedback_service.count_by_status",
                new_callable=AsyncMock,
                return_value={"new": 1, "triaged": 0, "closed": 0},
            ),
        ):
            response = await client.get("/api/admin/feedback")

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["user_email"] == "tester@example.com"
        assert body["counts"]["new"] == 1

    async def test_a_plain_user_cannot_read_everyone_elses_feedback(self, client_as):
        client = client_as("user")
        response = await client.get("/api/admin/feedback")

        assert response.status_code in (401, 403)

    async def test_triage_updates_the_status(self, client_as):
        client = client_as("admin")
        with patch(
            "app.api.feedback.feedback_service.set_status",
            new_callable=AsyncMock,
            return_value=_entry(status="triaged"),
        ):
            response = await client.patch("/api/admin/feedback/f-1", json={"status": "triaged"})

        assert response.status_code == 200
        assert response.json()["status"] == "triaged"

    async def test_a_missing_item_is_a_404(self, client_as):
        client = client_as("admin")
        with patch(
            "app.api.feedback.feedback_service.set_status",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.patch("/api/admin/feedback/nope", json={"status": "closed"})

        assert response.status_code == 404

    async def test_a_bad_status_is_a_400(self, client_as):
        client = client_as("admin")
        with patch(
            "app.api.feedback.feedback_service.set_status",
            new_callable=AsyncMock,
            side_effect=ValueError("Unknown feedback status: wontfix"),
        ):
            response = await client.patch("/api/admin/feedback/f-1", json={"status": "wontfix"})

        assert response.status_code == 400

    async def test_a_plain_user_cannot_triage(self, client_as):
        client = client_as("user")
        response = await client.patch("/api/admin/feedback/f-1", json={"status": "closed"})

        assert response.status_code in (401, 403)
