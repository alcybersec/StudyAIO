"""Integration tests for review items API endpoints."""

import pytest

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.review_item import ReviewItem


async def _owned_artifact(db_session, user_id, filename="review_test.pdf"):
    """Create a LectureArtifact owned by user_id and return it.

    ReviewItem has no user_id column of its own -- ownership is resolved
    through the entity it references. An item pointing at a bare
    generate_id() therefore belongs to nobody, and every owner-scoped
    endpoint correctly 404s on it. Any test that expects an item to be
    *reachable* has to anchor it to a real artifact owned by the caller.
    """
    artifact = LectureArtifact(
        id=generate_id(),
        user_id=user_id,
        original_filename=filename,
        file_path=f"/data/uploads/{filename}",
        file_type="pdf",
        sha256="aa" * 32,
        file_size_bytes=512,
        status="ingested",
    )
    db_session.add(artifact)
    await db_session.flush()
    return artifact


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
        # Anchor to a real artifact so ownership resolves to the caller.
        artifact = await _owned_artifact(db_session, test_user_id)

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

    async def test_dismiss_review_item(self, integration_client, db_session, test_user_id):
        """POST /api/review-items/{id}/dismiss marks item as dismissed."""
        artifact = await _owned_artifact(db_session, test_user_id, "dismiss_test.pdf")
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=artifact.id,
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

    async def test_dismiss_already_resolved_returns_400(
        self, integration_client, db_session, test_user_id
    ):
        """POST /api/review-items/{id}/dismiss on resolved item returns 400.

        The item has to be owned by the caller, or the 400 would come from
        the ownership miss rather than from the already-resolved check this
        test is actually about.
        """
        artifact = await _owned_artifact(db_session, test_user_id, "resolved_test.pdf")
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=artifact.id,
            payload_json={},
            suggested_values={},
            status="resolved",
        )
        db_session.add(item)
        await db_session.flush()

        resp = await integration_client.post(f"/api/review-items/{item.id}/dismiss")
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"]
