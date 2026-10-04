"""Uploads, quick capture, retry, reclassify and the event stream, on the real auth path.

The pipeline dispatch (`run_pipeline` / `resume_pipeline`) is the one thing
replaced: a broker is not part of this tier. Everything before it (validation,
dedup, storage, quota, usage metering, artifact rows) is real.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.api.uploads import pipeline_event_stream
from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.pipeline_run import PipelineRun
from app.models.usage_record import UsageRecord
from app.services import event_service

from ._support import make_docx, make_pdf

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def dispatched():
    """Replace pipeline dispatch; yields the mocks so tests can assert on them."""
    run = MagicMock(return_value=SimpleNamespace(id="task-1"))
    resume = MagicMock(return_value=SimpleNamespace(id="task-2"))
    with (
        patch("app.api.uploads.run_pipeline", run),
        patch("app.api.uploads.resume_pipeline", resume),
    ):
        yield SimpleNamespace(run=run, resume=resume)


async def _artifact(db_session, user, **overrides) -> LectureArtifact:
    values = {
        "id": generate_id(),
        "user_id": user.id,
        "original_filename": "x.pdf",
        "file_path": "uploads/x.pdf",
        "file_type": "pdf",
        "sha256": generate_id().replace("-", "") * 2,
        "file_size_bytes": 10,
        "status": "ingested",
    }
    values.update(overrides)
    artifact = LectureArtifact(**values)
    db_session.add(artifact)
    await db_session.flush()
    return artifact


class TestSingleUpload:
    async def test_upload_stores_bytes_creates_row_and_meters_usage(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        content = make_pdf()
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("week3.pdf", content, "application/pdf")}
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "processing" and body["pipeline_task_id"] == "task-1"

        artifact = (
            await db_session.execute(
                select(LectureArtifact).where(LectureArtifact.id == body["artifact_id"])
            )
        ).scalar_one()
        assert artifact.user_id == user.id
        assert artifact.file_type == "pdf" and artifact.file_size_bytes == len(content)
        assert await get_storage().get(artifact.file_path) == content
        dispatched.run.assert_called_once()
        assert dispatched.run.call_args.kwargs["artifact_id"] == artifact.id
        assert dispatched.run.call_args.kwargs["user_id"] == user.id

        usage = (
            await db_session.execute(select(UsageRecord).where(UsageRecord.user_id == user.id))
        ).scalar_one()
        assert usage.uploads_count == 1

    async def test_duplicate_is_per_user_and_stores_nothing_new(
        self, client_factory, make_user, db_session, dispatched
    ):
        a, b = await make_user(), await make_user()
        content = make_pdf()
        first = await client_factory(a).post(
            "/api/uploads", files={"file": ("w.pdf", content, "application/pdf")}
        )
        again = await client_factory(a).post(
            "/api/uploads", files={"file": ("renamed.pdf", content, "application/pdf")}
        )
        assert again.json()["status"] == "duplicate"
        assert again.json()["artifact_id"] == first.json()["artifact_id"]
        assert again.json()["pipeline_task_id"] is None
        assert dispatched.run.call_count == 1

        # The same bytes from another user are not a duplicate of the first user's.
        other = await client_factory(b).post(
            "/api/uploads", files={"file": ("w.pdf", content, "application/pdf")}
        )
        assert other.json()["status"] == "processing"
        assert other.json()["artifact_id"] != first.json()["artifact_id"]

    async def test_rejects_wrong_extension_and_mismatched_bytes(
        self, client_factory, make_user, dispatched
    ):
        client = client_factory(await make_user())
        bad_ext = await client.post("/api/uploads", files={"file": ("a.exe", b"MZ", "x/y")})
        assert bad_ext.status_code == 400
        fake_pdf = await client.post(
            "/api/uploads", files={"file": ("a.pdf", b"plain text, not a pdf", "application/pdf")}
        )
        assert fake_pdf.status_code == 400
        fake_docx = await client.post(
            "/api/uploads", files={"file": ("a.docx", b"plain text", "application/octet-stream")}
        )
        assert fake_docx.status_code == 400
        dispatched.run.assert_not_called()

    async def test_oversized_upload_rejected(self, client_factory, make_user, dispatched):
        client = client_factory(await make_user())
        with patch("app.config.settings.max_upload_size_mb", 0):
            resp = await client.post(
                "/api/uploads", files={"file": ("big.pdf", make_pdf(), "application/pdf")}
            )
        assert resp.status_code == 413
        dispatched.run.assert_not_called()

    async def test_upload_quota_blocks_free_tier_before_storing(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user(tier="free")
        db_session.add(
            UsageRecord(
                id=generate_id(),
                user_id=user.id,
                record_date=__import__("datetime").date.today(),
                uploads_count=10_000,
            )
        )
        await db_session.flush()
        with (
            patch("app.config.settings.self_hosted", False),
            patch("app.config.settings.free_max_uploads_per_month", 5),
        ):
            resp = await client_factory(user).post(
                "/api/uploads", files={"file": ("q.pdf", make_pdf(), "application/pdf")}
            )
        assert resp.status_code == 402
        dispatched.run.assert_not_called()
        assert (
            await db_session.execute(
                select(LectureArtifact).where(LectureArtifact.user_id == user.id)
            )
        ).first() is None

    async def test_anonymous_upload_in_saas_mode_rejected(self, client_factory):
        with patch("app.config.settings.self_hosted", False):
            resp = await client_factory().post(
                "/api/uploads", files={"file": ("a.pdf", make_pdf(), "application/pdf")}
            )
        assert resp.status_code == 401


class TestBatchUpload:
    async def test_mixed_batch_reports_each_file(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        pdf, docx = make_pdf(), make_docx()
        client = client_factory(user)
        await client.post("/api/uploads", files={"file": ("seen.pdf", pdf, "application/pdf")})

        resp = await client.post(
            "/api/uploads/batch",
            files=[
                ("files", ("seen-again.pdf", pdf, "application/pdf")),
                ("files", ("fresh.docx", docx, "application/octet-stream")),
                ("files", ("notes.txt", b"x", "text/plain")),
                ("files", ("fake.pdf", b"not a pdf", "application/pdf")),
            ],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert (body["total"], body["succeeded"], body["duplicates"], body["failed"]) == (
            4,
            1,
            1,
            2,
        )
        by_name = {r["filename"]: r for r in body["results"]}
        assert by_name["seen-again.pdf"]["status"] == "duplicate"
        assert by_name["fresh.docx"]["status"] == "processing"
        assert by_name["notes.txt"]["status"] == "error"
        assert by_name["fake.pdf"]["status"] == "error"

    async def test_batch_pipeline_dispatch_failure_is_reported_per_file(
        self, client_factory, make_user
    ):
        client = client_factory(await make_user())
        with patch("app.api.uploads.run_pipeline", side_effect=RuntimeError("broker down")):
            resp = await client.post(
                "/api/uploads/batch",
                files=[("files", ("a.pdf", make_pdf(), "application/pdf"))],
            )
        assert resp.json()["results"][0] == {
            "filename": "a.pdf",
            "status": "error",
            "artifact_id": None,
            "error": "Pipeline dispatch failed",
        }

    async def test_empty_batch_rejected(self, client_factory, make_user):
        resp = await client_factory(await make_user()).post("/api/uploads/batch", files=[])
        assert resp.status_code in (400, 422)


class TestQuickCapture:
    async def test_capture_text_creates_capture_artifact_and_resumes_at_classify(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/uploads/capture",
            json={"text": "Dijkstra finds shortest paths.", "title": "Graphs"},
        )
        assert resp.status_code == 201, resp.text
        artifact = (
            await db_session.execute(
                select(LectureArtifact).where(LectureArtifact.id == resp.json()["artifact_id"])
            )
        ).scalar_one()
        assert artifact.source_type == "capture" and artifact.title == "Graphs"
        assert artifact.user_id == user.id
        assert (await get_storage().get(artifact.file_path)).decode().startswith("Dijkstra")
        dispatched.resume.assert_called_once()
        assert dispatched.resume.call_args.kwargs["from_stage"] == "classify"

        again = await client_factory(user).post(
            "/api/uploads/capture", json={"text": "Dijkstra finds shortest paths."}
        )
        assert again.status_code == 409

    async def test_capture_validation(self, client_factory, make_user, dispatched):
        client = client_factory(await make_user())
        assert (await client.post("/api/uploads/capture", json={"text": "   "})).status_code in (
            400,
            422,
        )
        with patch("app.api.uploads.MAX_CAPTURE_BYTES", 10):
            assert (
                await client.post("/api/uploads/capture", json={"text": "x" * 50})
            ).status_code == 413
        dispatched.resume.assert_not_called()

    async def test_capture_url_fetches_text(
        self, client_factory, make_user, db_session, dispatched
    ):
        class FakeResponse:
            text = "Fetched lecture notes about hashing."

            def raise_for_status(self):
                return None

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url):
                assert url == "https://example.com/notes"
                return FakeResponse()

        client = client_factory(await make_user())
        with patch(
            "app.api.uploads.httpx", SimpleNamespace(AsyncClient=FakeClient, HTTPError=Exception)
        ):
            resp = await client.post(
                "/api/uploads/capture", json={"url": "https://example.com/notes"}
            )
        assert resp.status_code == 201, resp.text
        artifact = (
            await db_session.execute(
                select(LectureArtifact).where(LectureArtifact.id == resp.json()["artifact_id"])
            )
        ).scalar_one()
        assert artifact.title == "https://example.com/notes"

    async def test_capture_url_failure_is_502(self, client_factory, make_user):
        import httpx

        class Boom:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url):
                raise httpx.ConnectError("nope")

        client = client_factory(await make_user())
        with patch(
            "app.api.uploads.httpx", SimpleNamespace(AsyncClient=Boom, HTTPError=httpx.HTTPError)
        ):
            resp = await client.post(
                "/api/uploads/capture", json={"url": "https://example.invalid/x"}
            )
        assert resp.status_code == 502

    async def test_captured_text_can_be_classified(self, make_user, db_session):
        from app.core.database import async_session_factory
        from app.pipeline.classify import _classify
        from app.services import account_service, artifact_service

        from ._support import FakeAgent

        uid = generate_id()
        async with async_session_factory() as session:
            from app.models.user import User

            session.add(
                User(
                    id=uid,
                    email=f"cap-{uid[-10:]}@example.com",
                    username=f"cap_{uid[-10:]}",
                    role="user",
                    tier="free",
                    is_active=True,
                    email_verified=True,
                    mfa_enabled=False,
                )
            )
            await session.commit()
        try:
            async with async_session_factory() as session:
                artifact = await artifact_service.ingest_text_capture(
                    session, text="Packets are routed hop by hop.", title="Routing", user_id=uid
                )
                artifact_id = artifact.id
            with patch("app.pipeline.classify.get_agent", return_value=FakeAgent()):
                result = await _classify(artifact_id, user_id=uid)
            assert result["status"] == "classified"
        finally:
            async with async_session_factory() as session:
                await account_service.delete_user_account(session, uid)
                await session.commit()


class TestStatusRetryReclassify:
    async def test_status_is_owner_scoped(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        artifact = await _artifact(db_session, owner)
        db_session.add(
            PipelineRun(
                id=generate_id(), artifact_id=artifact.id, stage="ingest", status="completed"
            )
        )
        await db_session.flush()
        ok = await client_factory(owner).get(f"/api/uploads/{artifact.id}/status")
        assert [r["stage"] for r in ok.json()] == ["ingest"]
        denied = await client_factory(stranger).get(f"/api/uploads/{artifact.id}/status")
        assert denied.status_code == 404

    async def test_retry_resets_status_and_resumes_from_failed_stage(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        artifact = await _artifact(db_session, user, status="failed")
        db_session.add(
            PipelineRun(
                id=generate_id(),
                artifact_id=artifact.id,
                stage="summarize",
                status="failed",
                error_message="boom",
            )
        )
        await db_session.flush()
        with patch("app.api.uploads.resume_pipeline", dispatched.resume):
            resp = await client_factory(user).post(f"/api/uploads/{artifact.id}/retry")
        assert resp.status_code == 200
        assert resp.json()["retrying_from_stage"] == "summarize"
        assert resp.json()["status"] == "extracted"
        await db_session.refresh(artifact)
        assert artifact.status == "extracted"
        assert dispatched.resume.call_args.kwargs["from_stage"] == "summarize"

    async def test_retry_refusals(self, client_factory, make_user, db_session, dispatched):
        owner, stranger = await make_user(), await make_user()
        healthy = await _artifact(db_session, owner, status="processed")
        failed_no_run = await _artifact(db_session, owner, status="failed")
        client = client_factory(owner)
        assert (await client.post(f"/api/uploads/{healthy.id}/retry")).status_code == 400
        assert (await client.post(f"/api/uploads/{failed_no_run.id}/retry")).status_code == 400
        assert (
            await client_factory(stranger).post(f"/api/uploads/{healthy.id}/retry")
        ).status_code == 404
        assert (await client.post("/api/uploads/nope/retry")).status_code == 404
        dispatched.resume.assert_not_called()

    async def test_reclassify_moves_artifact_and_enqueues_summaries(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        course = Course(id=generate_id(), code="OLD100", name="Old", user_id=user.id)
        db_session.add(course)
        await db_session.flush()
        db_session.add(Course(id=generate_id(), code="NEW200", name="New", user_id=user.id))
        artifact = await _artifact(
            db_session, user, course_id=course.id, week=1, status="processed"
        )
        # A sibling that stays behind, so the vacated week also needs a fresh summary.
        sibling = await _artifact(db_session, user, course_id=course.id, week=1, status="processed")
        with patch("app.api.artifacts.summarize_artifact") as task:
            resp = await client_factory(user).post(
                f"/api/artifacts/{artifact.id}/reclassify",
                json={"course_code": "NEW200", "week": 4},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["summaries_enqueued"] == 2
        assert task.apply_async.call_count == 2
        enqueued_ids = {c.kwargs["args"][0]["artifact_id"] for c in task.apply_async.call_args_list}
        assert enqueued_ids == {artifact.id, sibling.id}
        await db_session.refresh(artifact)
        assert artifact.week == 4
        moved = await db_session.get(Course, artifact.course_id)
        assert moved.code == "NEW200" and moved.user_id == user.id

    async def test_reclassify_is_owner_scoped_busy_and_validated(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        db_session.add(Course(id=generate_id(), code="ZZZ100", name="Z", user_id=owner.id))
        artifact = await _artifact(db_session, owner, status="processed")
        busy = await _artifact(db_session, owner, status="summarizing")
        body = {"course_code": "ZZZ100", "week": 2}
        with patch("app.api.artifacts.summarize_artifact"):
            assert (
                await client_factory(stranger).post(
                    f"/api/artifacts/{artifact.id}/reclassify", json=body
                )
            ).status_code == 404
            assert (
                await client_factory(owner).post(f"/api/artifacts/{busy.id}/reclassify", json=body)
            ).status_code == 409
        assert (
            await client_factory(owner).post(
                f"/api/artifacts/{artifact.id}/reclassify", json={"course_code": "", "week": 99}
            )
        ).status_code == 422
        await db_session.refresh(artifact)
        assert artifact.week != 2  # the stranger's attempt changed nothing


class _FakeRequest:
    """Disconnects after a fixed number of polls."""

    def __init__(self, polls: int):
        self.polls = polls
        self.cookies: dict[str, str] = {}

    async def is_disconnected(self) -> bool:
        self.polls -= 1
        return self.polls < 0


class TestPipelineEventStream:
    async def test_stream_delivers_only_own_events_and_honours_artifact_filter(self, make_user):
        me = SimpleNamespace(id=generate_id())
        stranger_id = generate_id()
        stream = pipeline_event_stream(_FakeRequest(polls=12), "art-1", me)

        first = await anext(stream)
        assert first == {"comment": "connected"}

        async def publish():
            await asyncio.sleep(0.3)
            await event_service.publish_pipeline_event(
                "art-1", "classify", "started", user_id=me.id
            )
            await event_service.publish_pipeline_event(
                "art-2", "classify", "started", user_id=me.id
            )
            await event_service.publish_pipeline_event(
                "art-1", "classify", "started", user_id=stranger_id
            )
            await event_service.publish_pipeline_event(
                "art-1", "extract", "completed", user_id=me.id
            )

        task = asyncio.create_task(publish())
        events = []
        async for item in stream:
            if "event" in item:
                events.append(item["data"])
            if len(events) == 2:
                break
        await task
        await stream.aclose()
        import json

        parsed = [json.loads(e) for e in events]
        assert [e["stage"] for e in parsed] == ["classify", "extract"]
        assert {e["artifact_id"] for e in parsed} == {"art-1"}
        assert all("user_id" not in e for e in parsed)

    async def test_unowned_events_are_dropped(self, caplog):
        await event_service.publish_pipeline_event("a", "ingest", "started", user_id=None)
