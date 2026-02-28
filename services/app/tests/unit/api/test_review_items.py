"""Tests for the review items API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


def _mock_review_item(
    review_id="review-001",
    status="pending",
    entity_type="lecture_artifact",
):
    """Create a mock ReviewItem."""
    item = AsyncMock()
    item.id = review_id
    item.review_type = "classification_course"
    item.entity_type = entity_type
    item.entity_id = "art-001"
    item.payload_json = {"context": "some text"}
    item.suggested_values = {"course_code": "CSIT302", "week": 5}
    item.status = status
    item.resolution_json = None
    item.created_at = datetime(2024, 1, 1)
    item.resolved_at = None
    return item


@pytest.mark.asyncio
class TestListReviewItems:
    """Tests for GET /api/review-items."""

    async def test_list_pending_reviews(self, async_client):
        """List review items returns pending items by default."""
        mock_item = _mock_review_item()

        with patch(
            "app.api.review_items.review_service.list_pending_reviews",
            new_callable=AsyncMock,
            return_value=[mock_item],
        ):
            response = await async_client.get("/api/review-items")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "review-001"
        assert data[0]["status"] == "pending"

    async def test_list_pending_reviews_empty(self, async_client):
        """List review items returns empty when nothing pending."""
        with patch(
            "app.api.review_items.review_service.list_pending_reviews",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/review-items")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestGetReviewItem:
    """Tests for GET /api/review-items/{review_id}."""

    async def test_get_review_item_found(self, async_client):
        """Get review item returns the item when found."""
        mock_item = _mock_review_item()

        with patch(
            "app.api.review_items.review_service.get_review_item",
            new_callable=AsyncMock,
            return_value=mock_item,
        ):
            response = await async_client.get("/api/review-items/review-001")

        assert response.status_code == 200
        assert response.json()["id"] == "review-001"

    async def test_get_review_item_not_found(self, async_client):
        """Get review item returns 404 when not found."""
        with patch(
            "app.api.review_items.review_service.get_review_item",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/review-items/unknown")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDismissReviewItem:
    """Tests for POST /api/review-items/{review_id}/dismiss."""

    async def test_dismiss_success(self, async_client):
        """Dismissing a pending review returns the dismissed item."""
        dismissed = _mock_review_item(status="dismissed")

        with patch(
            "app.api.review_items.review_service.dismiss_review_item",
            new_callable=AsyncMock,
            return_value=dismissed,
        ):
            response = await async_client.post("/api/review-items/review-001/dismiss")

        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"

    async def test_dismiss_not_found(self, async_client):
        """Dismissing a non-existent review returns 400."""
        with patch(
            "app.api.review_items.review_service.dismiss_review_item",
            new_callable=AsyncMock,
            side_effect=ValueError("ReviewItem unknown not found"),
        ):
            response = await async_client.post("/api/review-items/unknown/dismiss")

        assert response.status_code == 400
