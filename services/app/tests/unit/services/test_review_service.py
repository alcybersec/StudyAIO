"""Tests for review_service."""

from app.services import review_service


class TestCreateReviewItem:
    """Tests for create_review_item()."""

    async def test_create_review_item(self, mock_session):
        """Creates a review item with correct fields."""
        result = await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={"context": "some text", "filename": "test.pdf"},
            suggested_values={"course_code": "CSIT302", "week": 5},
        )

        assert result.review_type == "classification_course"
        assert result.entity_type == "lecture_artifact"
        assert result.entity_id == "artifact-001"
        assert result.status == "pending"
        assert result.payload_json["filename"] == "test.pdf"
        assert result.suggested_values["course_code"] == "CSIT302"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestReviewCreationEmitsInbox:
    """Review-item creation emits a kind='review' inbox notification."""

    async def test_create_review_item_emits_notification(self, mock_session):
        """When the artifact owner is resolvable, an inbox row is added."""
        from unittest.mock import MagicMock

        from app.models.notification import Notification

        artifact = MagicMock()
        artifact.user_id = "user-001"
        artifact.original_filename = "lecture.pdf"
        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = artifact
        mock_session.execute.return_value = artifact_result

        await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={"filename": "lecture.pdf"},
            suggested_values={"course_code": "CSIT302"},
        )

        added = [c.args[0] for c in mock_session.add.call_args_list]
        notifications = [n for n in added if isinstance(n, Notification)]
        assert len(notifications) == 1
        assert notifications[0].kind == "review"
        assert notifications[0].user_id == "user-001"

    async def test_create_review_item_survives_emit_failure(self, mock_session):
        """Notification emit failure never breaks review creation."""
        mock_session.execute.side_effect = RuntimeError("lookup failed")

        item = await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={},
            suggested_values={},
        )
        assert item.status == "pending"
