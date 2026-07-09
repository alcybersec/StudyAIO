"""Tests for POST /api/artifacts/{artifact_id}/reclassify."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ArtifactBusyError


def _reclassify_result(artifact_id: str = "art-001", source_artifact_id: str | None = "art-002"):
    artifact = MagicMock()
    artifact.id = artifact_id
    artifact.course_id = "course-target"
    artifact.week = 4
    artifact.status = "processed"
    return {
        "artifact": artifact,
        "old_course_id": "course-src",
        "old_week": 2,
        "source_artifact_id": source_artifact_id,
    }


@pytest.mark.asyncio
class TestReclassify:
    """Tests for the reclassify endpoint."""

    async def test_reclassify_moves_and_enqueues_both_weeks(self, async_client):
        """Successful reclassify enqueues summarize for target AND source weeks."""
        with (
            patch(
                "app.api.artifacts.artifact_service.reclassify",
                new_callable=AsyncMock,
                return_value=_reclassify_result(),
            ) as mock_reclassify,
            patch("app.api.artifacts.summarize_artifact") as mock_summarize,
        ):
            response = await async_client.post(
                "/api/artifacts/art-001/reclassify",
                json={"course_code": "CSIT302", "week": 4},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["artifact_id"] == "art-001"
        assert data["course_code"] == "CSIT302"
        assert data["week"] == 4

        # Service called with the target classification
        _, kwargs = mock_reclassify.call_args
        assert kwargs.get("course_code") == "CSIT302"
        assert kwargs.get("week") == 4

        # Summarize enqueued for both affected weeks (target + source)
        assert mock_summarize.apply_async.call_count == 2
        enqueued_ids = [
            c.kwargs["args"][0]["artifact_id"] for c in mock_summarize.apply_async.call_args_list
        ]
        assert set(enqueued_ids) == {"art-001", "art-002"}

    async def test_reclassify_no_source_week_artifacts_enqueues_once(self, async_client):
        """If the source week has no remaining artifacts, only target is summarized."""
        with (
            patch(
                "app.api.artifacts.artifact_service.reclassify",
                new_callable=AsyncMock,
                return_value=_reclassify_result(source_artifact_id=None),
            ),
            patch("app.api.artifacts.summarize_artifact") as mock_summarize,
        ):
            response = await async_client.post(
                "/api/artifacts/art-001/reclassify",
                json={"course_code": "CSIT302", "week": 4},
            )

        assert response.status_code == 200
        assert mock_summarize.apply_async.call_count == 1

    async def test_reclassify_artifact_not_found_404(self, async_client):
        """Unknown or foreign artifact → 404."""
        with patch(
            "app.api.artifacts.artifact_service.reclassify",
            new_callable=AsyncMock,
            side_effect=LookupError("Artifact not found"),
        ):
            response = await async_client.post(
                "/api/artifacts/art-x/reclassify",
                json={"course_code": "CSIT302", "week": 4},
            )
        assert response.status_code == 404

    async def test_reclassify_unknown_course_404(self, async_client):
        """Unknown target course → 404."""
        with patch(
            "app.api.artifacts.artifact_service.reclassify",
            new_callable=AsyncMock,
            side_effect=ValueError("Course 'NOPE' not found"),
        ):
            response = await async_client.post(
                "/api/artifacts/art-001/reclassify",
                json={"course_code": "NOPE", "week": 4},
            )
        assert response.status_code == 404

    async def test_reclassify_processing_artifact_409(self, async_client):
        """Artifact still in the pipeline → 409."""
        with (
            patch(
                "app.api.artifacts.artifact_service.reclassify",
                new_callable=AsyncMock,
                side_effect=ArtifactBusyError("Artifact art-001 is still processing"),
            ),
            patch("app.api.artifacts.summarize_artifact") as mock_summarize,
        ):
            response = await async_client.post(
                "/api/artifacts/art-001/reclassify",
                json={"course_code": "CSIT302", "week": 4},
            )
        assert response.status_code == 409
        mock_summarize.apply_async.assert_not_called()

    async def test_reclassify_validates_body(self, async_client):
        """Missing course_code/week fails validation."""
        response = await async_client.post("/api/artifacts/art-001/reclassify", json={"week": 4})
        assert response.status_code == 422
