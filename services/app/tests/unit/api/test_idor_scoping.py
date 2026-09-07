"""IDOR regressions (#53): id-addressed endpoints must scope to the owner.

Each test asserts two things, and both are load-bearing:

1. User B gets 404 (or an empty result) for user A's object.
2. The endpoint actually threads ``user.id`` into the scoped service call.

The second is not redundant. On #47/PR #50 a revert of the endpoint call
sites left the plain 404 assertion still passing -- the service mock
returned None either way -- and only the wiring assertion failed. A test
that exercised the service alone would have missed the bug entirely. This
has now bitten three times in this repo; do not drop the wiring assertion.
"""

import io
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

OWNER_A = "owner-a-user-id"


@pytest.mark.asyncio
class TestExamsIdorScoping:
    """#53 clusters 3 and 4: exam endpoints. Two of these are writes."""

    async def test_get_exam_progress_404_for_other_user(self, async_client, default_test_user):
        """GET /api/exams/{id} must not return user A's progress to user B."""

        async def scoped(session, exam_id, user_id=None):
            return {"id": exam_id} if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.exam_service.get_exam_progress", new=mock):
            response = await async_client.get("/api/exams/exam-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_update_exam_404_for_other_user(self, async_client, default_test_user):
        """WRITE: PUT /api/exams/{id} must not mutate user A's exam."""

        async def scoped(session, exam_id, user_id=None, **kwargs):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.exam_service.update_exam", new=mock):
            response = await async_client.put(
                "/api/exams/exam-owned-by-a", json={"title": "hijacked"}
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_delete_exam_404_for_other_user(self, async_client, default_test_user):
        """WRITE: DELETE /api/exams/{id} must not archive user A's exam."""

        async def scoped(session, exam_id, user_id=None):
            return user_id == OWNER_A

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.exam_service.delete_exam", new=mock):
            response = await async_client.delete("/api/exams/exam-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_weak_topics_404_for_other_user(self, async_client, default_test_user):
        """GET /api/exams/{id}/weak-topics must not analyse user A's exam."""

        async def scoped(session, exam_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.exam_service.get_exam", new=mock):
            response = await async_client.get("/api/exams/exam-owned-by-a/weak-topics")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_schedule_404_for_other_user(self, async_client, default_test_user):
        """GET /api/exams/{id}/schedule must not plan against user A's exam."""

        async def scoped(session, exam_id, days_ahead=7, user_id=None):
            return [] if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.schedule_service.generate_study_schedule", new=mock):
            response = await async_client.get("/api/exams/exam-owned-by-a/schedule")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_today_404_for_other_user(self, async_client, default_test_user):
        """GET /api/exams/{id}/today must not plan against user A's exam."""

        async def scoped(session, exam_id, user_id=None):
            return {} if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.schedule_service.get_daily_study_plan", new=mock):
            response = await async_client.get("/api/exams/exam-owned-by-a/today")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id


class TestReviewItemOwnershipPredicate:
    """ReviewItem is polymorphic, so the ownership join must cover every
    entity_type that is actually created -- otherwise scoping it 404s the
    owner on their own item."""

    def test_covers_every_entity_type_that_is_created(self):
        """Both `lecture_artifact` and `summary` items must be reachable.

        `summary` items come from course_service's merge_week_conflict path.
        A join written only against LectureArtifact -- the shape
        list_pending_reviews uses -- silently hides them from their owner.
        """
        from app.services.review_service import _owned_by

        sql = str(_owned_by("some-user").compile(compile_kwargs={"literal_binds": True}))

        assert "lecture_artifacts" in sql, "lecture_artifact review items unreachable"
        assert "summaries" in sql, "summary (merge_week_conflict) review items unreachable"
        assert "courses" in sql, "summary ownership must resolve through Course.user_id"


@pytest.mark.asyncio
class TestReviewItemsIdorScoping:
    """#53 cluster 1. Resolve is a write that also resumes the pipeline on
    the referenced artifact, so it is an integrity issue, not disclosure."""

    async def test_get_review_item_404_for_other_user(self, async_client, default_test_user):
        """GET /api/review-items/{id} must not return user A's item."""

        async def scoped(session, review_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.review_items.review_service.get_review_item", new=mock):
            response = await async_client.get("/api/review-items/review-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_resolve_review_item_404_for_other_user(self, async_client, default_test_user):
        """WRITE: POST .../resolve must not resolve user A's review item, and
        must not restart the pipeline on user A's artifact."""

        async def scoped(session, review_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with (
            patch("app.api.review_items.review_service.get_review_item", new=mock),
            patch("app.api.review_items.resume_pipeline") as mock_resume,
            patch(
                "app.api.review_items.review_service.resolve_review_item",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            response = await async_client.post(
                "/api/review-items/review-owned-by-a/resolve",
                json={"resolution": {"course_code": "CSIT302", "week": 5}},
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        # The state change and the pipeline restart must not have happened.
        mock_resolve.assert_not_awaited()
        mock_resume.assert_not_called()

    async def test_dismiss_review_item_scopes_by_user(self, async_client, default_test_user):
        """WRITE: POST .../dismiss must thread user.id so a foreign item is
        rejected.

        Dismiss reports both a missing and a foreign item as 400 "not found",
        so the status code alone is not an existence oracle and is left as
        it was; the wiring assertion is what proves the scoping.
        """

        async def scoped(session, review_id, user_id=None):
            if user_id != OWNER_A:
                raise ValueError(f"ReviewItem {review_id} not found")
            return MagicMock()

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.review_items.review_service.dismiss_review_item", new=mock):
            response = await async_client.post("/api/review-items/review-owned-by-a/dismiss")

        assert response.status_code == 400
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestSummariesIdorScoping:
    """#53 cluster 2: GET /api/summaries/{id} returned any user's markdown."""

    async def test_get_summary_404_for_other_user(self, async_client, default_test_user):
        async def scoped(session, summary_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.summaries.summary_service.get_summary_by_id", new=mock):
            response = await async_client.get("/api/summaries/summary-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestAssetsIdorScoping:
    """#53 cluster 5: course codes are unique per user (uq_courses_code_user),
    so filtering on the code alone crosses users who share a code."""

    async def test_flashcards_for_course_scoped_to_user(self, async_client, default_test_user):
        async def scoped(session, course_code, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.assets.asset_service.get_flashcards_for_course", new=mock):
            response = await async_client.get("/api/assets/flashcards?course_code=CSIT302")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_flashcards_for_week_scoped_to_user(self, async_client, default_test_user):
        async def scoped(session, course_code, week, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.assets.asset_service.get_flashcards_for_week", new=mock):
            response = await async_client.get("/api/assets/flashcards?course_code=CSIT302&week=5")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_quiz_for_course_scoped_to_user(self, async_client, default_test_user):
        async def scoped(session, course_code, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.assets.asset_service.get_quiz_questions_for_course", new=mock):
            response = await async_client.get("/api/assets/quiz?course_code=CSIT302")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_quiz_for_week_scoped_to_user(self, async_client, default_test_user):
        async def scoped(session, course_code, week, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.assets.asset_service.get_quiz_questions_for_week", new=mock):
            response = await async_client.get("/api/assets/quiz?course_code=CSIT302&week=5")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestUploadStatusIdorScoping:
    """#53 cluster 6: the ownership check sat inside `if not runs:`, so it
    only fired when there was nothing left to protect."""

    async def test_status_404_for_other_user_even_when_runs_exist(
        self, async_client, default_test_user
    ):
        """The regression that matters: an artifact that HAS pipeline runs.

        Under the old ordering this returned 200 and leaked the run history,
        because the guard lived in the empty branch. A test using an artifact
        with no runs would have passed against the buggy code.
        """

        async def scoped_artifact(session, artifact_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        # A fully-valid run, so that reverting the guard order yields a clean
        # 200 with the leaked history rather than a serialization error.
        owner_a_run = MagicMock()
        owner_a_run.id = "run-owned-by-a"
        owner_a_run.artifact_id = "art-owned-by-a"
        owner_a_run.stage = "ingest"
        owner_a_run.status = "completed"
        owner_a_run.error_message = None
        owner_a_run.started_at = datetime(2026, 1, 1)
        owner_a_run.completed_at = datetime(2026, 1, 1, 0, 0, 5)
        owner_a_run.duration_ms = 5000

        mock_artifact = AsyncMock(side_effect=scoped_artifact)
        mock_runs = AsyncMock(return_value=[owner_a_run])
        with (
            patch("app.api.uploads.artifact_service.get_artifact", new=mock_artifact),
            patch("app.api.uploads.pipeline_service.get_artifact_pipeline_runs", new=mock_runs),
        ):
            response = await async_client.get("/api/uploads/art-owned-by-a/status")

        assert response.status_code == 404
        assert mock_artifact.await_args.kwargs.get("user_id") == default_test_user.id
        # And the unscoped query must not even have run.
        mock_runs.assert_not_awaited()


@pytest.mark.asyncio
class TestCourseOpsIdorScoping:
    """#55: every id- or code-addressed lookup in the courseops router ran
    without an owner. Eleven endpoints, six of them writes.

    The ``course_code`` ones are the #53 cluster-5 shape: codes are unique
    *per user* (uq_courses_code_user), so two users who both have CSIT302
    reached each other's assessments, deadlines and exports.
    """

    # ------------------------------------------------------------------ writes

    async def test_delete_document_404_for_other_user(self, async_client, default_test_user):
        """WRITE, and the one that matters most.

        #50 scoped ``get_course_document`` so *reading* another user's
        document 404s, but left the delete beside it unscoped -- so until #55
        one user could still destroy another's document by id.
        """

        async def scoped(session, document_id, user_id=None):
            return user_id == OWNER_A

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.delete_course_document", new=mock):
            response = await async_client.delete("/api/courseops/documents/doc-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_update_assessment_404_for_other_user(self, async_client, default_test_user):
        """WRITE: PATCH /assessments/{id} must not edit user A's assessment."""

        async def scoped(session, assessment_id, user_id=None, **kwargs):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.update_assessment", new=mock):
            response = await async_client.patch(
                "/api/courseops/assessments/assess-owned-by-a",
                json={"title": "hijacked"},
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_update_deadline_404_for_other_user(self, async_client, default_test_user):
        """WRITE: PUT /deadlines/{id} must not move or confirm user A's deadline."""

        async def scoped(session, deadline_id, user_id=None, **kwargs):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.update_deadline", new=mock):
            response = await async_client.put(
                "/api/courseops/deadlines/dl-owned-by-a",
                json={"title": "hijacked", "is_confirmed": True},
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_delete_deadline_404_for_other_user(self, async_client, default_test_user):
        """WRITE: DELETE /deadlines/{id} must not delete user A's deadline."""

        async def scoped(session, deadline_id, user_id=None):
            return user_id == OWNER_A

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.delete_deadline", new=mock):
            response = await async_client.delete("/api/courseops/deadlines/dl-owned-by-a")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_create_assessment_404_for_other_users_course(
        self, async_client, default_test_user
    ):
        """WRITE: POST /assessments?course_code= must not add to user A's course."""

        async def scoped(session, *, course_code, user_id=None, **kwargs):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.create_assessment", new=mock):
            response = await async_client.post(
                "/api/courseops/assessments?course_code=CSIT302",
                json={"title": "planted", "assessment_type": "exam"},
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_create_deadline_404_for_other_users_course(
        self, async_client, default_test_user
    ):
        """WRITE: POST /deadlines?course_code= must not add to user A's course."""

        async def scoped(session, *, course_code, user_id=None, **kwargs):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.create_deadline", new=mock):
            response = await async_client.post(
                "/api/courseops/deadlines?course_code=CSIT302",
                json={"title": "planted", "due_date": "2026-05-01"},
            )

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    # ------------------------------------------------------------------- reads

    async def test_list_assessment_documents_scoped_to_user(self, async_client, default_test_user):
        """A guessed assessment id must not list user A's attachments.

        A list endpoint's non-oracle answer is an empty 200, not a 404 -- the
        same shape #53 cluster 5 settled on for the asset lists.
        """

        async def scoped(session, assessment_id, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.list_assessment_documents", new=mock):
            response = await async_client.get(
                "/api/courseops/assessments/assess-owned-by-a/documents"
            )

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_list_assessments_scoped_to_user(self, async_client, default_test_user):
        """Sharing a course code with user A must not list their assessments."""

        async def scoped(session, course_code, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.list_assessments", new=mock):
            response = await async_client.get("/api/courseops/assessments?course_code=CSIT302")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_list_deadlines_scoped_to_user(self, async_client, default_test_user):
        """Sharing a course code with user A must not list their deadlines."""

        async def scoped(session, course_code, upcoming_only=False, user_id=None):
            return [MagicMock()] if user_id == OWNER_A else []

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.courseops_service.list_deadlines", new=mock):
            response = await async_client.get("/api/courseops/deadlines?course_code=CSIT302")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_export_calendar_404_for_other_users_course(
        self, async_client, default_test_user
    ):
        """The .ics export carries every deadline of the course it resolves."""

        async def scoped(session, course_code, user_id=None):
            return (io.BytesIO(b"BEGIN:VCALENDAR"), "x.ics") if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.generate_ics", new=mock):
            response = await async_client.get("/api/courseops/export/calendar/CSIT302")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_export_task_plan_404_for_other_users_course(
        self, async_client, default_test_user
    ):
        """Same for the markdown plan: assessments, weights and deadlines."""

        async def scoped(session, course_code, user_id=None):
            return (io.BytesIO(b"# plan"), "x.md") if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.courseops.generate_task_plan_md", new=mock):
            response = await async_client.get("/api/courseops/export/task-plan/CSIT302")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A


@pytest.mark.asyncio
class TestExamHistoryIdorScoping:
    """The study-history aggregate has no ownership check above it.

    Unlike the other ``/exams/{id}/...`` routes, ``get_history`` does not
    resolve the exam first -- ``get_study_history`` is the only call in the
    handler, so the ``user_id`` it is handed *is* the whole authorization.
    Nothing else in the request would 404 a foreign exam id.
    """

    async def test_history_scoped_to_the_caller(self, async_client, default_test_user):
        """GET /api/exams/{id}/history must not report user A's study days."""

        async def scoped(session, exam_id=None, days=30, user_id=None):
            return (
                [{"date": "2026-03-01", "minutes": 45.0, "cards": 20, "sessions": 2}]
                if user_id == OWNER_A
                else []
            )

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exams.streak_service.get_study_history", new=mock):
            response = await async_client.get("/api/exams/exam-owned-by-a/history")

        assert response.status_code == 200
        assert response.json() == []
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A


@pytest.mark.asyncio
class TestExportsIdorScoping:
    """The Obsidian export packages a whole course into a downloadable zip.

    Its only lookup is the generator itself, so an unscoped call would hand a
    stranger every summary, flashcard and quiz of a course they do not own --
    in one request, as a file.
    """

    async def test_obsidian_vault_404_for_other_users_course(self, async_client, default_test_user):
        """GET /api/exports/obsidian/{code} must not export user A's course."""

        async def scoped(session, course_code, week_list, user_id=None):
            return (io.BytesIO(b"PK\x03\x04"), "vault.zip") if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.exports.export_service.generate_obsidian_vault", new=mock):
            response = await async_client.get("/api/exports/obsidian/CSIT302")

        assert response.status_code == 404
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A
