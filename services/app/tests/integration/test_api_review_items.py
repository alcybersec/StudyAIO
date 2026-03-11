"""Integration tests for review items API endpoints."""

import pytest

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.review_item import ReviewItem


@pytest.mark.asyncio(loop_scope="session")
class TestReviewItemsEndpoints:
    """Test /api/review-items endpoints against a real database."""

    async def test_list_pending_empty(self, integration_client, db_session):
        """GET /api/review-items returns empty list initially."""
        resp = await integration_client.get("/api/review-items")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_list(self, integration_client, db_session, test_user_id):
        """Review items created in DB appear in GET /api/review-items."""
        # Create a real artifact so the user_id JOIN in list_pending_reviews works
        artifact = LectureArtifact(
            id=generate_id(),
            user_id=test_user_id,
            original_filename="review_test.pdf",
            file_path="/data/uploads/review_test.pdf",
            file_type="pdf",
            sha256="aa" * 32,
            file_size_bytes=512,
            status="ingested",
        )
        db_session.add(artifact)
        await db_session.flush()

        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=artifact.id,
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
