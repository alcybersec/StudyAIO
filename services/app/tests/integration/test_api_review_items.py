"""Integration tests for review items API endpoints."""

import pytest

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.review_item import ReviewItem
from app.models.summary import Summary


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


async def _owned_summary_review_item(db_session, user_id):
    """A legacy `merge_week_conflict` item, owner-reachable and unresolvable.

    Nothing creates these any more -- `course_service.merge_courses` settles
    week conflicts during the merge (#63) -- but rows written before that
    change can still be in the table, so the endpoints have to answer for them
    honestly. Ownership runs Summary -> Course.user_id, so the row has to be
    anchored to a real course the caller owns or it 404s for reasons unrelated
    to what is being tested.
    """
    course = Course(id=generate_id(), user_id=user_id, code="LEGACY1", name="Legacy")
    db_session.add(course)
    await db_session.flush()

    summary = Summary(
        id=generate_id(),
        course_id=course.id,
        week=2,
        content_md="# week 2\n",
        file_path=f"summaries/{course.id}/Week2.md",
        version=1,
        source_artifacts=[],
    )
    db_session.add(summary)
    await db_session.flush()

    item = ReviewItem(
        id=generate_id(),
        review_type="merge_week_conflict",
        entity_type="summary",
        entity_id=summary.id,
        payload_json={"reason": "Week 2 already has a summary in TGT202"},
        suggested_values={"action": "regenerate_week_summary"},
        status="pending",
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio(loop_scope="session")
class TestUnresolvableEntityTypes:
    """#63: resolve must not report success for a type it cannot apply.

    The bug was not that resolving a `summary` item did nothing -- it was that
    it did nothing and returned 200, so the UI showed "Review item resolved."
    and the item left the pending count with its conflict untouched. A silent
    no-op would have been better than a confirmed one.
    """

    async def test_resolving_a_summary_item_is_a_400(
        self, integration_client, db_session, test_user_id
    ):
        item = await _owned_summary_review_item(db_session, test_user_id)

        resp = await integration_client.post(
            f"/api/review-items/{item.id}/resolve",
            json={"resolution": {"course_code": "TGT202"}},
        )

        assert resp.status_code == 400
        assert "summary" in resp.json()["detail"]

    async def test_a_refused_resolve_leaves_the_item_pending(
        self, integration_client, db_session, test_user_id
    ):
        item = await _owned_summary_review_item(db_session, test_user_id)

        await integration_client.post(
            f"/api/review-items/{item.id}/resolve",
            json={"resolution": {"course_code": "TGT202"}},
        )
        await db_session.refresh(item)

        # The distinction that matters: the old behaviour marked it resolved.
        # It must stay pending so the count keeps telling the truth, and so the
        # owner can still dismiss it.
        assert item.status == "pending"

    async def test_the_item_can_still_be_dismissed(
        self, integration_client, db_session, test_user_id
    ):
        """Refusing to resolve must not trap the item in the inbox forever."""
        item = await _owned_summary_review_item(db_session, test_user_id)

        resp = await integration_client.post(f"/api/review-items/{item.id}/dismiss")
        await db_session.refresh(item)

        assert resp.status_code == 200
        assert item.status == "dismissed"
