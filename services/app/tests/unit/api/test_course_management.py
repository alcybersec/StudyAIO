"""Tests for course management endpoints (rename/archive/delete/merge)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

USER_ID = "00000000-0000-0000-0000-000000000001"


def _mock_course(code: str = "CSIT302", name: str = "Cybersecurity") -> MagicMock:
    course = MagicMock()
    course.id = "course-001"
    course.code = code
    course.name = name
    course.term = None
    course.created_at = datetime(2024, 1, 1)
    course.updated_at = datetime(2024, 1, 2)
    return course


@pytest.mark.asyncio
class TestRenameCourse:
    """Tests for PATCH /api/courses/{code}."""

    async def test_rename_course_updates_code_and_children(self, async_client):
        """Rename returns the updated course; children keep FK integrity (by id)."""
        renamed = _mock_course(code="CSIT999", name="Advanced Security")
        with patch(
            "app.api.courses.course_service.rename_course",
            new_callable=AsyncMock,
            return_value=renamed,
        ) as mock_rename:
            response = await async_client.patch(
                "/api/courses/CSIT302",
                json={"new_code": "CSIT999", "name": "Advanced Security"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "CSIT999"
        assert data["name"] == "Advanced Security"
        _, kwargs = mock_rename.call_args
        assert kwargs.get("new_code") == "CSIT999"
        assert mock_rename.call_args.args[1] == USER_ID

    async def test_rename_course_conflict_409(self, async_client):
        """Renaming to an existing code returns 409."""
        with patch(
            "app.api.courses.course_service.rename_course",
            new_callable=AsyncMock,
            side_effect=ValueError("Course 'CSIT999' already exists"),
        ):
            response = await async_client.patch(
                "/api/courses/CSIT302", json={"new_code": "CSIT999"}
            )
        assert response.status_code == 409

    async def test_rename_course_tenant_isolation_404(self, async_client):
        """Another user's course → 404."""
        with patch(
            "app.api.courses.course_service.rename_course",
            new_callable=AsyncMock,
            side_effect=LookupError("Course not found"),
        ):
            response = await async_client.patch("/api/courses/OTHERS101", json={"name": "x"})
        assert response.status_code == 404


@pytest.mark.asyncio
class TestArchiveCourse:
    """Tests for POST /api/courses/{code}/archive."""

    async def test_archive_course_returns_ok(self, async_client):
        """Archiving marks the course archived."""
        archived = _mock_course()
        archived.archived_at = datetime(2026, 7, 4)
        with patch(
            "app.api.courses.course_service.archive_course",
            new_callable=AsyncMock,
            return_value=archived,
        ) as mock_archive:
            response = await async_client.post("/api/courses/CSIT302/archive")

        assert response.status_code == 200
        assert response.json()["archived"] is True
        assert mock_archive.call_args.args[1] == USER_ID

    async def test_archived_hidden_from_default_list(self, async_client):
        """GET /courses defaults to excluding archived courses."""
        with patch(
            "app.api.courses.course_service.list_courses_with_stats",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get("/api/courses")

        assert response.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("include_archived") is False

    async def test_archived_shown_with_flag(self, async_client):
        """GET /courses?include_archived=1 forwards the flag."""
        with patch(
            "app.api.courses.course_service.list_courses_with_stats",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get("/api/courses", params={"include_archived": "1"})

        assert response.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("include_archived") is True

    async def test_archive_unknown_course_404(self, async_client):
        """Unknown course → 404."""
        with patch(
            "app.api.courses.course_service.archive_course",
            new_callable=AsyncMock,
            side_effect=LookupError("Course not found"),
        ):
            response = await async_client.post("/api/courses/NOPE/archive")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteCourse:
    """Tests for DELETE /api/courses/{code}."""

    async def test_delete_without_confirmation_returns_428(self, async_client):
        """Missing X-Confirm header → 428 Precondition Required."""
        with patch(
            "app.api.courses.course_service.delete_course",
            new_callable=AsyncMock,
        ) as mock_delete:
            response = await async_client.delete("/api/courses/CSIT302")

        assert response.status_code == 428
        mock_delete.assert_not_called()

    async def test_delete_with_wrong_confirmation_returns_428(self, async_client):
        """X-Confirm not matching the course code → 428."""
        with patch(
            "app.api.courses.course_service.delete_course",
            new_callable=AsyncMock,
        ) as mock_delete:
            response = await async_client.delete(
                "/api/courses/CSIT302", headers={"X-Confirm": "WRONG"}
            )

        assert response.status_code == 428
        mock_delete.assert_not_called()

    async def test_delete_with_confirmation_cascades(self, async_client):
        """Correct X-Confirm header deletes the course and reports counts."""
        with patch(
            "app.api.courses.course_service.delete_course",
            new_callable=AsyncMock,
            return_value={"artifacts": 3, "flashcards": 12, "summaries": 2},
        ) as mock_delete:
            response = await async_client.delete(
                "/api/courses/CSIT302", headers={"X-Confirm": "CSIT302"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["counts"]["artifacts"] == 3
        assert mock_delete.call_args.args[1] == USER_ID

    async def test_delete_tenant_isolation_404(self, async_client):
        """Another user's course → 404 even with confirmation."""
        with patch(
            "app.api.courses.course_service.delete_course",
            new_callable=AsyncMock,
            side_effect=LookupError("Course not found"),
        ):
            response = await async_client.delete(
                "/api/courses/OTHERS101", headers={"X-Confirm": "OTHERS101"}
            )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMergeCourse:
    """Tests for POST /api/courses/{code}/merge."""

    async def test_merge_reports_moved_weeks_and_the_policy_applied(self, async_client):
        """Merge reports what it moved and how it settled the conflicts."""
        with patch(
            "app.api.courses.course_service.merge_courses",
            new_callable=AsyncMock,
            return_value={
                "moved_summaries": 3,
                "conflict_weeks": [2],
                "conflict_resolution": "regenerate",
                "regenerated_weeks": [2],
                "summarize_artifact_ids": [],
            },
        ) as mock_merge:
            response = await async_client.post(
                "/api/courses/CSIT302/merge", json={"into": "CSIT999"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["moved_summaries"] == 3
        assert data["conflict_weeks"] == [2]
        assert data["conflict_resolution"] == "regenerate"
        assert data["regenerated_weeks"] == [2]
        # Internal work for the endpoint to enqueue, not part of the contract.
        assert "summarize_artifact_ids" not in data
        _, kwargs = mock_merge.call_args
        assert mock_merge.call_args.args[1] == USER_ID
        assert kwargs.get("into_code") == "CSIT999"
        # Omitting on_conflict must reach the service as the documented default
        # rather than as None, which would trip its own validation.
        assert kwargs.get("on_conflict") == "regenerate"

    async def test_merge_forwards_an_explicit_policy(self, async_client):
        """An explicit on_conflict reaches the service verbatim."""
        with patch(
            "app.api.courses.course_service.merge_courses",
            new_callable=AsyncMock,
            return_value={
                "moved_summaries": 0,
                "conflict_weeks": [2],
                "conflict_resolution": "keep_target",
                "regenerated_weeks": [],
                "summarize_artifact_ids": [],
            },
        ) as mock_merge:
            response = await async_client.post(
                "/api/courses/CSIT302/merge",
                json={"into": "CSIT999", "on_conflict": "keep_target"},
            )

        assert response.status_code == 200
        assert mock_merge.call_args.kwargs.get("on_conflict") == "keep_target"

    async def test_merge_rejects_an_unknown_policy_at_the_schema(self, async_client):
        """An unknown policy is a 422, never reaching the service."""
        with patch(
            "app.api.courses.course_service.merge_courses",
            new_callable=AsyncMock,
        ) as mock_merge:
            response = await async_client.post(
                "/api/courses/CSIT302/merge",
                json={"into": "CSIT999", "on_conflict": "delete_everything"},
            )

        assert response.status_code == 422
        mock_merge.assert_not_awaited()

    async def test_merge_enqueues_regeneration_after_the_commit(self, async_client):
        """Returned artifact ids are handed to the pipeline, post-commit."""
        with (
            patch(
                "app.api.courses.course_service.merge_courses",
                new_callable=AsyncMock,
                return_value={
                    "moved_summaries": 0,
                    "conflict_weeks": [2],
                    "conflict_resolution": "regenerate",
                    "regenerated_weeks": [2],
                    "summarize_artifact_ids": ["artifact-42"],
                },
            ),
            patch("app.api.courses.resume_pipeline") as mock_resume,
        ):
            response = await async_client.post(
                "/api/courses/CSIT302/merge", json={"into": "CSIT999"}
            )

        assert response.status_code == 200
        mock_resume.assert_called_once()
        assert mock_resume.call_args.args[0] == "artifact-42"
        assert mock_resume.call_args.kwargs.get("from_stage") == "summarize"

    async def test_merge_survives_a_failed_enqueue(self, async_client):
        """A broker failure must not fail a merge that is already committed."""
        with (
            patch(
                "app.api.courses.course_service.merge_courses",
                new_callable=AsyncMock,
                return_value={
                    "moved_summaries": 0,
                    "conflict_weeks": [2],
                    "conflict_resolution": "regenerate",
                    "regenerated_weeks": [2],
                    "summarize_artifact_ids": ["artifact-42"],
                },
            ),
            patch(
                "app.api.courses.resume_pipeline",
                side_effect=RuntimeError("broker down"),
            ),
        ):
            response = await async_client.post(
                "/api/courses/CSIT302/merge", json={"into": "CSIT999"}
            )

        # The move is durable; the week simply keeps the target's existing
        # summary, which is the keep_target outcome rather than a broken one.
        assert response.status_code == 200
        assert response.json()["conflict_weeks"] == [2]

    async def test_merge_unknown_target_404(self, async_client):
        """Unknown merge target → 404."""
        with patch(
            "app.api.courses.course_service.merge_courses",
            new_callable=AsyncMock,
            side_effect=LookupError("Course 'NOPE' not found"),
        ):
            response = await async_client.post("/api/courses/CSIT302/merge", json={"into": "NOPE"})
        assert response.status_code == 404

    async def test_merge_into_itself_400(self, async_client):
        """Merging a course into itself → 400."""
        with patch(
            "app.api.courses.course_service.merge_courses",
            new_callable=AsyncMock,
            side_effect=ValueError("Cannot merge a course into itself"),
        ):
            response = await async_client.post(
                "/api/courses/CSIT302/merge", json={"into": "CSIT302"}
            )
        assert response.status_code == 400
