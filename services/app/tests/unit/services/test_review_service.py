"""Tests for review_service."""

from unittest.mock import MagicMock

import pytest

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
