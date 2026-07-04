"""Tests for the global search API endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestGlobalSearch:
    """Tests for GET /api/search."""

    async def test_search_returns_grouped_results(self, async_client):
        """Search returns results with kind, title, snippet, href_meta."""
        from app.services.search_service import GlobalSearchResult

        with patch(
            "app.api.search.search_service.search_all",
            new_callable=AsyncMock,
            return_value=[
                GlobalSearchResult(
                    kind="course_week",
                    title="CSIT302 — Week 3",
                    snippet="…forensics and evidence…",
                    href_meta={"course_code": "CSIT302", "week": 3},
                    user_id="00000000-0000-0000-0000-000000000001",
                ),
                GlobalSearchResult(
                    kind="flashcard",
                    title="What is digital forensics?",
                    snippet="What is digital forensics?",
                    href_meta={"course_code": "CSIT302", "week": 3, "flashcard_id": "fc-1"},
                    user_id="00000000-0000-0000-0000-000000000001",
                ),
            ],
        ) as mock_search:
            response = await async_client.get("/api/search", params={"q": "forensics"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["kind"] == "course_week"
        assert data["results"][0]["href_meta"]["week"] == 3
        # user_id is internal — not exposed in the response
        assert "user_id" not in data["results"][0]
        mock_search.assert_awaited_once()

    async def test_search_empty_query_returns_400(self, async_client):
        """Blank query string is rejected with 400."""
        response = await async_client.get("/api/search", params={"q": "   "})
        assert response.status_code == 400

    async def test_search_missing_query_returns_422(self, async_client):
        """Missing q param fails validation."""
        response = await async_client.get("/api/search")
        assert response.status_code == 422

    async def test_search_passes_user_and_limit(self, async_client):
        """The current user's id and the limit are forwarded to the service."""
        with patch(
            "app.api.search.search_service.search_all",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            response = await async_client.get(
                "/api/search", params={"q": "foo", "limit": 5}
            )

        assert response.status_code == 200
        assert response.json()["results"] == []
        _, kwargs = mock_search.call_args
        call_args = mock_search.call_args
        args = call_args.args
        user_id = args[1] if len(args) > 1 else kwargs.get("user_id")
        limit = kwargs.get("limit", args[3] if len(args) > 3 else None)
        assert user_id == "00000000-0000-0000-0000-000000000001"
        assert limit == 5
