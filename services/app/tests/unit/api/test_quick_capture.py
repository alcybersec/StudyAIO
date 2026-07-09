"""Tests for POST /api/uploads/capture — quick text/URL capture."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import DuplicateFileError


def _mock_artifact(artifact_id: str = "art-cap-001") -> MagicMock:
    artifact = MagicMock()
    artifact.id = artifact_id
    artifact.original_filename = "Quick capture.txt"
    artifact.status = "ingested"
    return artifact


@pytest.mark.asyncio
class TestQuickCaptureText:
    """Text capture behavior."""

    async def test_capture_text_creates_artifact_and_enqueues_classify(self, async_client):
        """Text capture returns 201 and resumes the pipeline from classify."""
        artifact = _mock_artifact()
        with (
            patch(
                "app.api.uploads.artifact_service.ingest_text_capture",
                new_callable=AsyncMock,
                return_value=artifact,
            ) as mock_ingest,
            patch("app.api.uploads.resume_pipeline") as mock_resume,
        ):
            response = await async_client.post(
                "/api/uploads/capture",
                json={"text": "Notes about firewalls", "title": "Firewall notes"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["artifact_id"] == "art-cap-001"
        assert data["status"] == "processing"

        _, ingest_kwargs = mock_ingest.call_args
        assert ingest_kwargs.get("text") == "Notes about firewalls"
        assert ingest_kwargs.get("title") == "Firewall notes"

        mock_resume.assert_called_once()
        _, resume_kwargs = mock_resume.call_args
        assert mock_resume.call_args.args[0] == "art-cap-001"
        assert resume_kwargs.get("from_stage") == "classify"

    async def test_capture_oversized_text_returns_413(self, async_client):
        """Text bigger than 1 MB is rejected with 413."""
        big_text = "x" * (1024 * 1024 + 1)
        with patch(
            "app.api.uploads.artifact_service.ingest_text_capture",
            new_callable=AsyncMock,
        ) as mock_ingest:
            response = await async_client.post("/api/uploads/capture", json={"text": big_text})

        assert response.status_code == 413
        mock_ingest.assert_not_called()

    async def test_capture_duplicate_returns_409(self, async_client):
        """Duplicate capture (same SHA-256) returns 409."""
        with (
            patch(
                "app.api.uploads.artifact_service.ingest_text_capture",
                new_callable=AsyncMock,
                side_effect=DuplicateFileError(sha256="a" * 64, existing_artifact_id="art-000"),
            ),
            patch("app.api.uploads.resume_pipeline") as mock_resume,
        ):
            response = await async_client.post("/api/uploads/capture", json={"text": "same text"})

        assert response.status_code == 409
        mock_resume.assert_not_called()

    async def test_capture_checks_upload_quota(self, async_client):
        """Quick capture counts as an upload — quota is checked."""
        artifact = _mock_artifact()
        with (
            patch(
                "app.api.uploads.quota_service.check_upload_quota",
                new_callable=AsyncMock,
            ) as mock_quota,
            patch(
                "app.api.uploads.artifact_service.ingest_text_capture",
                new_callable=AsyncMock,
                return_value=artifact,
            ),
            patch("app.api.uploads.resume_pipeline"),
        ):
            response = await async_client.post("/api/uploads/capture", json={"text": "quota check"})

        assert response.status_code == 201
        mock_quota.assert_awaited_once()


@pytest.mark.asyncio
class TestQuickCaptureUrl:
    """URL capture behavior."""

    async def test_capture_url_fetches_and_stores_text(self, async_client):
        """URL capture fetches the page (mocked) and stores it as text."""
        artifact = _mock_artifact("art-cap-url")

        mock_response = MagicMock()
        mock_response.text = "Fetched page content"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.uploads.httpx.AsyncClient", return_value=mock_client),
            patch(
                "app.api.uploads.artifact_service.ingest_text_capture",
                new_callable=AsyncMock,
                return_value=artifact,
            ) as mock_ingest,
            patch("app.api.uploads.resume_pipeline") as mock_resume,
        ):
            response = await async_client.post(
                "/api/uploads/capture", json={"url": "https://example.com/article"}
            )

        assert response.status_code == 201
        _, kwargs = mock_ingest.call_args
        assert kwargs.get("text") == "Fetched page content"
        mock_resume.assert_called_once()

    async def test_capture_url_fetch_failure_returns_502(self, async_client):
        """Unreachable URL returns 502."""
        import httpx as _httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("boom"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.uploads.httpx.AsyncClient", return_value=mock_client):
            response = await async_client.post(
                "/api/uploads/capture", json={"url": "https://down.example.com"}
            )

        assert response.status_code == 502


@pytest.mark.asyncio
class TestQuickCaptureValidation:
    """Request validation."""

    async def test_both_text_and_url_returns_422(self, async_client):
        """Providing both text and url fails validation."""
        response = await async_client.post(
            "/api/uploads/capture",
            json={"text": "notes", "url": "https://example.com"},
        )
        assert response.status_code == 422

    async def test_neither_text_nor_url_returns_422(self, async_client):
        """Providing neither text nor url fails validation."""
        response = await async_client.post("/api/uploads/capture", json={})
        assert response.status_code == 422
