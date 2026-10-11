"""The AI-processing consent gate (GL#38) on the real auth path.

Unit tests prove the dependency is attached; these prove what the gate is *for*:
an unconsented caller spends nothing and stores nothing, a consented one
proceeds, and consent can be recorded through the API and then unlocks the
very same request.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.artifact import LectureArtifact
from app.models.usage_event import UsageEvent
from app.models.usage_record import UsageRecord
from app.models.user import User

from ._support import FakeAgent, make_pdf, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def dispatched():
    run = MagicMock(return_value=SimpleNamespace(id="task-1"))
    resume = MagicMock(return_value=SimpleNamespace(id="task-2"))
    with (
        patch("app.api.uploads.run_pipeline", run),
        patch("app.api.uploads.resume_pipeline", resume),
    ):
        yield SimpleNamespace(run=run, resume=resume)


@pytest.fixture
def agent():
    fake = FakeAgent()
    with (
        patch("app.services.chat_service.get_agent", return_value=fake),
        patch("app.agents.factory.get_agent", return_value=fake),
    ):
        yield fake


async def _count(db_session, model, user_id) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    )


def _assert_consent_required(resp) -> None:
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["code"] == "ai_consent_required"
    assert body["consent_version"] == settings.ai_consent_version


class TestUploadGate:
    async def test_consented_upload_succeeds_and_is_dispatched(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("w.pdf", make_pdf(), "application/pdf")}
        )
        assert resp.status_code == 201, resp.text
        dispatched.run.assert_called_once()
        assert await _count(db_session, LectureArtifact, user.id) == 1

    async def test_unconsented_upload_is_403_and_nothing_is_stored_or_enqueued(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user(consented=False)
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("w.pdf", make_pdf(), "application/pdf")}
        )
        _assert_consent_required(resp)
        dispatched.run.assert_not_called()
        assert await _count(db_session, LectureArtifact, user.id) == 0
        assert await _count(db_session, UsageEvent, user.id) == 0
        assert await _count(db_session, UsageRecord, user.id) == 0

    async def test_unconsented_batch_upload_is_403_and_nothing_is_stored(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user(consented=False)
        resp = await client_factory(user).post(
            "/api/uploads/batch",
            files=[("files", ("w.pdf", make_pdf(), "application/pdf"))],
        )
        _assert_consent_required(resp)
        dispatched.run.assert_not_called()
        assert await _count(db_session, LectureArtifact, user.id) == 0
        assert await _count(db_session, UsageEvent, user.id) == 0

    async def test_outdated_consent_version_is_asked_again(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        user.ai_processing_consent_version = settings.ai_consent_version - 1
        await db_session.flush()
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("w.pdf", make_pdf(), "application/pdf")}
        )
        _assert_consent_required(resp)
        dispatched.run.assert_not_called()

    async def test_recording_consent_through_the_api_unlocks_the_same_request(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user(consented=False)
        client = client_factory(user)
        files = {"file": ("w.pdf", make_pdf(), "application/pdf")}

        _assert_consent_required(await client.post("/api/uploads", files=files))

        me = (await client.get("/api/auth/me")).json()
        assert me["ai_consent_required"] is True

        recorded = await client.post("/api/auth/consent")
        assert recorded.status_code == 200, recorded.text
        assert recorded.json()["ai_consent_required"] is False
        stored = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
        assert stored.ai_processing_consent_at is not None
        assert stored.ai_processing_consent_version == settings.ai_consent_version

        assert (await client.get("/api/auth/me")).json()["ai_consent_required"] is False
        resp = await client.post("/api/uploads", files=files)
        assert resp.status_code == 201, resp.text
        dispatched.run.assert_called_once()

    async def test_stale_disclosure_version_cannot_record_consent(
        self, client_factory, make_user, db_session
    ):
        user = await make_user(consented=False)
        resp = await client_factory(user).post(
            "/api/auth/consent", json={"version": settings.ai_consent_version + 1}
        )
        assert resp.status_code == 409
        stored = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
        assert stored.ai_processing_consent_at is None

    async def test_single_user_mode_never_asks(
        self, client_factory, make_user, dispatched, monkeypatch
    ):
        user = await make_user(consented=False)
        monkeypatch.setattr(settings, "single_user_mode", True)
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("w.pdf", make_pdf(), "application/pdf")}
        )
        assert resp.status_code == 201, resp.text


class TestOtherGatedRoutes:
    """Every AI-spending route refuses before it resolves anything or calls out."""

    @pytest.mark.parametrize(
        ("path", "kwargs"),
        [
            ("/api/settings/test-ai", {}),
            ("/api/chat/sessions/nope/messages", {"json": {"content": "hi"}}),
            ("/api/chat/sessions/nope/messages/stream", {"json": {"content": "hi"}}),
            ("/api/qa/ask", {"json": {"question": "what is tcp?"}}),
            ("/api/concepts/extract/nope", {}),
            ("/api/uploads/capture", {"json": {"text": "some notes"}}),
            ("/api/uploads/nope/retry", {}),
            ("/api/artifacts/nope/reclassify", {"json": {}}),
            ("/api/review-items/nope/resolve", {"json": {}}),
            ("/api/courses/NET101/merge", {"json": {"into": "NET102"}}),
            (
                "/api/courseops/documents",
                {"files": {"file": ("syllabus.pdf", b"%PDF-1.4", "application/pdf")}},
            ),
        ],
    )
    async def test_unconsented_caller_gets_403_before_any_lookup_or_ai_call(
        self, client_factory, make_user, db_session, dispatched, agent, path, kwargs
    ):
        user = await make_user(consented=False)
        resp = await client_factory(user).post(path, **kwargs)
        _assert_consent_required(resp)
        assert agent.calls == []
        dispatched.run.assert_not_called()
        dispatched.resume.assert_not_called()
        assert await _count(db_session, UsageEvent, user.id) == 0

    async def test_consented_chat_message_reaches_the_agent(
        self, client_factory, make_user, db_session, agent
    ):
        user = await make_user()
        await seed_course(db_session, user.id, code="CNS101")
        client = client_factory(user)
        sid = (await client.post("/api/chat/sessions", json={})).json()["id"]
        resp = await client.post(
            f"/api/chat/sessions/{sid}/messages", json={"content": "Explain TCP"}
        )
        assert resp.status_code == 200, resp.text
        assert agent.calls != []

    async def test_non_ai_routes_stay_open_without_consent(self, client_factory, make_user):
        client = client_factory(await make_user(consented=False))
        assert (await client.get("/api/courses")).status_code == 200
        assert (await client.get("/api/auth/me")).status_code == 200
