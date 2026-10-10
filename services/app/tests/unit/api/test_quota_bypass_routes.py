"""QUOTA-01: every route that spends AI or storage checks the caller's quota.

Each test asserts the check was awaited with the caller's id (the wiring, not
just the status) and that a refusal stops the spend.
"""

import io
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import QuotaExceededError

CHECK_AI = "app.services.quota_service.check_ai_quota"
CHECK_UPLOAD = "app.services.quota_service.check_upload_quota"
PDF = b"%PDF-1.4 test"


def _refuse():
    return AsyncMock(side_effect=QuotaExceededError("ai_calls", 100, "day"))


def _files(n: int):
    return [
        ("files", (f"l{i}.pdf", io.BytesIO(PDF + bytes([i])), "application/pdf")) for i in range(n)
    ]


def _doc():
    d = MagicMock()
    d.id = "doc-1"
    d.course_id = "course-1"
    d.assessment_id = None
    d.document_type = "outline"
    d.title = "o.pdf"
    d.original_filename = "o.pdf"
    d.file_type = "pdf"
    d.sha256 = "abc"
    d.file_size_bytes = 10
    d.status = "uploaded"
    d.created_at = datetime(2026, 3, 1)
    d.updated_at = datetime(2026, 3, 1)
    return d


@pytest.mark.asyncio
class TestBatchUploadQuota:
    async def test_each_new_file_is_checked_for_the_caller(self, async_client, default_test_user):
        with (
            patch(CHECK_UPLOAD, new_callable=AsyncMock) as upload_check,
            patch(CHECK_AI, new_callable=AsyncMock) as ai_check,
            patch("app.api.uploads.run_pipeline"),
            patch("app.api.uploads.billing_service.record_usage", new_callable=AsyncMock) as record,
        ):
            response = await async_client.post("/api/uploads/batch", files=_files(3))

        assert response.status_code == 201
        assert upload_check.await_count == 3
        assert ai_check.await_count == 3
        assert upload_check.await_args.args[1] == default_test_user.id
        assert ai_check.await_args.args[1] == default_test_user.id
        assert ai_check.await_args.kwargs["calls"] == 4
        # each accepted file is counted so the next one in the request sees it
        assert record.await_count == 3
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.kwargs == {"uploads": 1}

    async def test_file_over_quota_fails_alone_and_stores_nothing(self, async_client):
        refused = QuotaExceededError("uploads", 5, "month")
        with (
            patch(CHECK_UPLOAD, AsyncMock(side_effect=[None, refused, refused])),
            patch(CHECK_AI, new_callable=AsyncMock),
            patch("app.api.uploads.run_pipeline") as pipeline,
            patch("app.api.uploads.billing_service.record_usage", new_callable=AsyncMock),
            patch(
                "app.api.uploads.artifact_service.create_upload_artifact",
                new_callable=AsyncMock,
                return_value=MagicMock(id="a1", file_path="p"),
            ) as create,
        ):
            response = await async_client.post("/api/uploads/batch", files=_files(3))

        data = response.json()
        assert response.status_code == 201
        assert data["succeeded"] == 1
        assert data["failed"] == 2
        assert create.await_count == 1
        assert pipeline.call_count == 1
        assert "Quota exceeded" in data["results"][1]["error"]


@pytest.mark.asyncio
class TestRetryQuota:
    @staticmethod
    def _patches(artifact):
        run = MagicMock(status="failed", stage="summarize")
        return (
            patch(
                "app.api.uploads.artifact_service.get_artifact",
                new_callable=AsyncMock,
                return_value=artifact,
            ),
            patch(
                "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
                new_callable=AsyncMock,
                return_value=[run],
            ),
        )

    async def test_retry_checks_ai_quota_for_the_caller(self, async_client, default_test_user):
        get_art, get_runs = self._patches(MagicMock(status="failed"))
        with (
            patch(CHECK_AI, new_callable=AsyncMock) as check,
            get_art,
            get_runs,
            patch("app.api.uploads.resume_pipeline"),
        ):
            response = await async_client.post("/api/uploads/art-1/retry")

        assert response.status_code == 200
        assert check.await_args.args[1] == default_test_user.id

    async def test_retry_refused_does_not_resume_or_reset_status(self, async_client):
        artifact = MagicMock(status="failed")
        get_art, get_runs = self._patches(artifact)
        with (
            patch(CHECK_AI, _refuse()),
            get_art,
            get_runs,
            patch("app.api.uploads.resume_pipeline") as resume,
        ):
            response = await async_client.post("/api/uploads/art-1/retry")

        assert response.status_code == 402
        resume.assert_not_called()
        assert artifact.status == "failed"


@pytest.mark.asyncio
class TestReclassifyQuota:
    async def test_checks_before_moving_anything(self, async_client, default_test_user):
        with (
            patch(CHECK_AI, _refuse()) as check,
            patch(
                "app.api.artifacts.artifact_service.reclassify", new_callable=AsyncMock
            ) as reclassify,
            patch("app.api.artifacts.summarize_artifact") as summarize,
        ):
            response = await async_client.post(
                "/api/artifacts/a1/reclassify", json={"course_code": "C1", "week": 2}
            )

        assert response.status_code == 402
        assert check.await_args.args[1] == default_test_user.id
        reclassify.assert_not_awaited()
        summarize.apply_async.assert_not_called()


@pytest.mark.asyncio
class TestReviewResolveQuota:
    async def test_refused_leaves_the_item_pending(self, async_client, default_test_user):
        item = MagicMock(entity_type="lecture_artifact", entity_id="a1", status="pending")
        with (
            patch(
                "app.api.review_items.review_service.get_review_item",
                new=AsyncMock(return_value=item),
            ),
            patch(CHECK_AI, _refuse()) as check,
            patch(
                "app.api.review_items.artifact_service.apply_classification",
                new_callable=AsyncMock,
            ) as apply,
            patch("app.api.review_items.resume_pipeline") as resume,
        ):
            response = await async_client.post(
                "/api/review-items/r1/resolve",
                json={"resolution": {"course_code": "C1", "week": 1}},
            )

        assert response.status_code == 402
        assert check.await_args.args[1] == default_test_user.id
        apply.assert_not_awaited()
        resume.assert_not_called()


@pytest.mark.asyncio
class TestMergeQuota:
    @staticmethod
    def _merge_result(ids):
        return {
            "moved_summaries": 1,
            "conflict_weeks": [],
            "conflict_resolution": "regenerate",
            "regenerated_weeks": [],
            "summarize_artifact_ids": ids,
        }

    async def test_regeneration_is_checked_for_the_caller(self, async_client, default_test_user):
        with (
            patch(
                "app.api.courses.course_service.merge_courses",
                new_callable=AsyncMock,
                return_value=self._merge_result(["a1", "a2"]),
            ),
            patch(CHECK_AI, new_callable=AsyncMock) as check,
            patch("app.api.courses.resume_pipeline") as resume,
        ):
            response = await async_client.post("/api/courses/C1/merge", json={"into": "C2"})

        assert response.status_code == 200
        assert check.await_args.args[1] == default_test_user.id
        assert check.await_args.kwargs["calls"] == 2
        assert resume.call_count == 2

    async def test_refusal_keeps_the_merge_and_skips_only_regeneration(self, async_client):
        with (
            patch(
                "app.api.courses.course_service.merge_courses",
                new_callable=AsyncMock,
                return_value=self._merge_result(["a1"]),
            ),
            patch(CHECK_AI, _refuse()),
            patch("app.api.courses.resume_pipeline") as resume,
        ):
            response = await async_client.post("/api/courses/C1/merge", json={"into": "C2"})

        assert response.status_code == 200
        resume.assert_not_called()


@pytest.mark.asyncio
class TestCourseOpsQuota:
    async def test_outline_upload_checks_and_meters_the_caller(
        self, async_client, default_test_user
    ):
        with (
            patch(CHECK_UPLOAD, new_callable=AsyncMock) as upload_check,
            patch(CHECK_AI, new_callable=AsyncMock) as ai_check,
            patch(
                "app.api.courseops.courseops_service.upload_course_document",
                new_callable=AsyncMock,
                return_value=_doc(),
            ),
            patch("app.pipeline.courseops_task.process_course_document"),
            patch(
                "app.api.courseops.billing_service.record_usage", new_callable=AsyncMock
            ) as record,
        ):
            response = await async_client.post(
                "/api/courseops/documents?course_code=C1&document_type=outline",
                files={"file": ("o.pdf", io.BytesIO(PDF), "application/pdf")},
            )

        assert response.status_code == 201
        assert upload_check.await_args.args[1] == default_test_user.id
        assert ai_check.await_args.args[1] == default_test_user.id
        assert record.await_args.args[1] == default_test_user.id
        assert record.await_args.kwargs == {"uploads": 1}

    async def test_outline_refused_stores_and_queues_nothing(self, async_client):
        with (
            patch(CHECK_UPLOAD, new_callable=AsyncMock),
            patch(CHECK_AI, _refuse()),
            patch(
                "app.api.courseops.courseops_service.upload_course_document",
                new_callable=AsyncMock,
            ) as upload,
            patch("app.pipeline.courseops_task.process_course_document") as task,
        ):
            response = await async_client.post(
                "/api/courseops/documents?course_code=C1&document_type=outline",
                files={"file": ("o.pdf", io.BytesIO(PDF), "application/pdf")},
            )

        assert response.status_code == 402
        upload.assert_not_awaited()
        task.delay.assert_not_called()

    async def test_assessment_attachment_checks_upload_quota(self, async_client, default_test_user):
        with (
            patch(CHECK_UPLOAD, _refuse()) as check,
            patch(
                "app.api.courseops.courseops_service.attach_assessment_document",
                new_callable=AsyncMock,
            ) as attach,
        ):
            response = await async_client.post(
                "/api/courseops/assessments/as1/documents?document_type=brief",
                files={"file": ("g.pdf", io.BytesIO(PDF), "application/pdf")},
            )

        assert response.status_code == 402
        assert check.await_args.args[1] == default_test_user.id
        attach.assert_not_awaited()
