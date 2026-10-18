"""AI-processing consent gate on every AI-spending / pipeline-enqueueing route.

M33-S1-BACKEND-017 (GL#38, SEC-08). The structural test reads the live route
table, so a new route in GATED_ROUTES that loses the dependency fails here.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import get_current_user_or_default, require_ai_consent
from tests._routes import route_contexts

#: (method, path under /api) of every route that spends AI or enqueues AI work.
GATED_ROUTES = [
    ("POST", "/api/settings/test-ai"),
    ("POST", "/api/chat/sessions/{session_id}/messages"),
    ("POST", "/api/chat/sessions/{session_id}/messages/stream"),
    ("POST", "/api/qa/ask"),
    ("POST", "/api/concepts/extract/{artifact_id}"),
    ("POST", "/api/uploads"),
    ("POST", "/api/uploads/batch"),
    ("POST", "/api/uploads/capture"),
    ("POST", "/api/uploads/{artifact_id}/retry"),
    ("POST", "/api/artifacts/{artifact_id}/reclassify"),
    ("POST", "/api/review-items/{review_id}/resolve"),
    ("POST", "/api/courses/{course_code}/merge"),
    ("POST", "/api/courseops/documents"),
]


def _dep_calls(route) -> set:
    found: set = set()

    def walk(dependant):
        for d in dependant.dependencies:
            found.add(d.call)
            walk(d)

    walk(route.dependant)
    return found


def test_every_listed_route_carries_the_consent_dependency():
    from app.main import app

    index = {(m, r.path): r for r in route_contexts(app) if r.methods for m in r.methods}
    missing = []
    unmatched = []
    for method, path in GATED_ROUTES:
        route = index.get((method, path))
        if route is None:
            unmatched.append((method, path))
        elif require_ai_consent not in _dep_calls(route):
            missing.append((method, path))
    assert not unmatched, f"route not found (renamed?): {unmatched}"
    assert not missing, f"missing require_ai_consent: {missing}"


@pytest.mark.asyncio
class TestGateBehaviour:
    async def test_unconsented_caller_gets_403_with_code(self, async_client, default_test_user):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            resp = await async_client.post("/api/qa/ask", json={"question": "what is x?"})
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == "ai_consent_required"

    async def test_gate_runs_before_any_ai_spend(self, async_client, default_test_user):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with (
            patch("app.services.consent_service.settings") as s,
            patch("app.agents.factory.get_agent") as get_agent,
        ):
            s.single_user_mode = False
            s.ai_consent_version = 1
            resp = await async_client.post("/api/settings/test-ai")
        assert resp.status_code == 403
        assert resp.json()["code"] == "ai_consent_required"
        get_agent.assert_not_called()

    async def test_gate_does_not_enqueue(self, async_client, default_test_user):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with (
            patch("app.services.consent_service.settings") as s,
            patch("app.api.artifacts.summarize_artifact") as task,
        ):
            s.single_user_mode = False
            s.ai_consent_version = 1
            resp = await async_client.post(
                "/api/artifacts/a1/reclassify", json={"course_code": "X", "week": 1}
            )
        assert resp.status_code == 403
        task.apply_async.assert_not_called()

    async def test_consented_caller_passes_the_gate(self, async_client, default_test_user):
        from datetime import UTC, datetime

        default_test_user.ai_processing_consent_at = datetime.now(UTC)
        default_test_user.ai_processing_consent_version = 1
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            resp = await async_client.post("/api/qa/ask", json={"question": "what is x?"})
        assert not (resp.status_code == 403 and resp.json().get("code") == "ai_consent_required")

    async def test_single_user_mode_is_never_prompted(self, async_client, default_test_user):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = True
            s.ai_consent_version = 1
            resp = await async_client.post("/api/qa/ask", json={"question": "what is x?"})
        assert not (resp.status_code == 403 and resp.json().get("code") == "ai_consent_required")


@pytest.mark.asyncio
class TestConsentEndpoint:
    async def test_post_consent_records_for_the_caller(
        self, async_client, default_test_user, mock_session
    ):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with (
            patch("app.config.settings.single_user_mode", False),
            patch("app.config.settings.ai_consent_version", 3),
        ):
            resp = await async_client.post("/api/auth/consent")
        assert resp.status_code == 200
        assert default_test_user.ai_processing_consent_version == 3
        assert default_test_user.ai_processing_consent_at is not None
        assert resp.json() == {"ai_consent_required": False, "ai_consent_version": 3}
        mock_session.commit.assert_awaited()

    async def test_stale_version_in_body_is_refused(self, async_client, default_test_user):
        default_test_user.ai_processing_consent_at = None
        default_test_user.ai_processing_consent_version = None
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 3
            resp = await async_client.post("/api/auth/consent", json={"version": 2})
        assert resp.status_code == 409
        assert default_test_user.ai_processing_consent_at is None

    def test_route_requires_a_caller(self):
        from app.main import app

        route = next(r for r in route_contexts(app) if r.path == "/api/auth/consent")
        assert get_current_user_or_default in _dep_calls(route)


class TestProfilePayload:
    def _profile(self, user):
        from app.api.auth_schemas import UserProfileResponse

        return UserProfileResponse.model_validate(user).model_dump()

    def test_me_flags_missing_consent(self, make_user):
        user = make_user(ai_processing_consent_at=None, ai_processing_consent_version=None)
        user.avatar_url = None
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            assert self._profile_safe(user)["ai_consent_required"] is True

    def test_me_clears_flag_when_current(self, make_user):
        from datetime import UTC, datetime

        user = make_user(
            ai_processing_consent_at=datetime.now(UTC), ai_processing_consent_version=1
        )
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            assert self._profile_safe(user)["ai_consent_required"] is False

    def test_me_flags_outdated_version(self, make_user):
        from datetime import UTC, datetime

        user = make_user(
            ai_processing_consent_at=datetime.now(UTC), ai_processing_consent_version=1
        )
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 2
            assert self._profile_safe(user)["ai_consent_required"] is True

    def test_profile_exposes_current_required_version(self, make_user):
        from datetime import UTC, datetime

        user = make_user(
            ai_processing_consent_at=datetime.now(UTC), ai_processing_consent_version=1
        )
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 4
            payload = self._profile_safe(user)
        assert payload["ai_consent_version"] == 4

    def test_profile_version_tracks_setting_not_stored(self, make_user):
        user = make_user(ai_processing_consent_at=None, ai_processing_consent_version=None)
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 2
            first = self._profile_safe(user)["ai_consent_version"]
            s.ai_consent_version = 7
            second = self._profile_safe(user)["ai_consent_version"]
        assert (first, second) == (2, 7)

    def test_profile_still_hides_raw_consent_record(self, make_user):
        from datetime import UTC, datetime

        user = make_user(
            ai_processing_consent_at=datetime.now(UTC), ai_processing_consent_version=1
        )
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            payload = self._profile_safe(user)
        assert "ai_processing_consent_at" not in payload
        assert "ai_processing_consent_version" not in payload

    def _profile_safe(self, user):
        from datetime import UTC, datetime

        user.created_at = datetime.now(UTC)
        user.hashed_password = "x"
        return self._profile(user)


def test_config_default_version_is_one():
    from app.config import Settings

    assert Settings.model_fields["ai_consent_version"].default == 1


# keep imports used
_ = (AsyncMock, MagicMock)
