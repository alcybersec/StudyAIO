"""Integration tests for review items API endpoints."""

from app.core.utils import generate_id
from app.models.review_item import ReviewItem


class TestReviewItemsEndpoints:
    """Test /api/review-items endpoints against a real database."""

    async def test_list_pending_empty(self, integration_client, db_session):
        """GET /api/review-items returns empty list initially."""
        resp = await integration_client.get("/api/review-items")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_list(self, integration_client, db_session):
        """Review items created in DB appear in GET /api/review-items."""
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload_json={"filename": "test.pdf"},
            suggested_values={"course_code": "CSIT302"},
            status="pending",
        )
        db_session.add(item)
        await db_session.flush()

        resp = await integration_client.get("/api/review-items")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == item.id
        assert data[0]["status"] == "pending"

    async def test_dismiss_review_item(self, integration_client, db_session):
        """POST /api/review-items/{id}/dismiss marks item as dismissed."""
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload_json={},
            suggested_values={},
            status="pending",
        )
        db_session.add(item)
        await db_session.flush()

        resp = await integration_client.post(f"/api/review-items/{item.id}/dismiss")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"

    async def test_dismiss_already_resolved_returns_400(self, integration_client, db_session):
        """POST /api/review-items/{id}/dismiss on resolved item returns 400."""
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload_json={},
            suggested_values={},
            status="resolved",
        )
        db_session.add(item)
        await db_session.flush()

        resp = await integration_client.post(f"/api/review-items/{item.id}/dismiss")
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"]
