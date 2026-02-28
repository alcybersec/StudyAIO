"""Tests for classify pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ClassificationResult
from app.core.exceptions import ClassificationError


class TestClassifyInput:
    """Tests for chain-compatible input handling."""

    def test_classify_skips_duplicate(self):
        """Dict with duplicate status is passed through."""
        from app.pipeline.classify import classify_artifact

        input_value = {"artifact_id": "art-001", "status": "duplicate", "sha256": "abc"}

        # Call the function directly (bypass Celery binding)
        result = classify_artifact.run(input_value)

        assert result["status"] == "duplicate"
        assert result["artifact_id"] == "art-001"

    def test_classify_skips_waiting_review(self):
        """Dict with waiting_review status is passed through."""
        from app.pipeline.classify import classify_artifact

        input_value = {"artifact_id": "art-001", "status": "waiting_review"}
        result = classify_artifact.run(input_value)

        assert result["status"] == "waiting_review"

    def test_classify_skips_failed(self):
        """Dict with failed status is passed through."""
        from app.pipeline.classify import classify_artifact

        input_value = {"artifact_id": "art-001", "status": "failed"}
        result = classify_artifact.run(input_value)

        assert result["status"] == "failed"


class TestClassifyStage:
    """Tests for _classify async function."""

    @patch("app.pipeline.classify.get_agent")
    @patch("app.pipeline.classify._extract_text_preview")
    @patch("app.pipeline.classify.async_session_factory")
    async def test_high_confidence_classifies(
        self, mock_session_factory, mock_preview, mock_get_agent
    ):
        """High confidence classification updates artifact."""
        from app.pipeline.classify import _classify

        # Set up mock artifact
        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.file_path = "/app/data/uploads/test.pdf"
        artifact.file_type = "pdf"
        artifact.original_filename = "CSIT302_Week5.pdf"

        # Mock session
        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock text preview
        mock_preview.return_value = "CSIT302 Week 5 Network Security"

        # Mock agent
        agent = AsyncMock()
        agent.classify_lecture.return_value = ClassificationResult(
            course_code="CSIT302",
            week=5,
            title="Network Security",
            confidence=0.95,
            reasoning="Found in header",
        )
        mock_get_agent.return_value = agent

        # We need to handle the course query too — make execute return different
        # results per call
        call_count = 0
        original_execute = session.execute

        async def multi_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Artifact query
                return mock_result
            elif call_count == 2:
                # Known courses query
                courses_result = MagicMock()
                courses_result.all.return_value = [("CSIT302",)]
                return courses_result
            else:
                # Course get-or-create query
                course = MagicMock()
                course.id = "course-001"
                course_result = MagicMock()
                course_result.scalar_one_or_none.return_value = course
                return course_result

        session.execute = AsyncMock(side_effect=multi_execute)

        result = await _classify("art-001")

        assert result["status"] == "classified"
        assert result["course_code"] == "CSIT302"
        assert result["week"] == 5

    @patch("app.pipeline.classify.get_agent")
    @patch("app.pipeline.classify._extract_text_preview")
    @patch("app.pipeline.classify.review_service")
    @patch("app.pipeline.classify.async_session_factory")
    async def test_low_confidence_creates_review(
        self, mock_session_factory, mock_review_svc, mock_preview, mock_get_agent
    ):
        """Low confidence creates review item."""
        from app.pipeline.classify import _classify

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.file_path = "/app/data/uploads/test.pdf"
        artifact.file_type = "pdf"
        artifact.original_filename = "unknown_lecture.pdf"

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_preview.return_value = "Some lecture content"

        agent = AsyncMock()
        agent.classify_lecture.return_value = ClassificationResult(
            course_code="UNKNOWN",
            week=0,
            title="",
            confidence=0.3,
            reasoning="Very uncertain",
        )
        mock_get_agent.return_value = agent

        # Multi-execute for artifact + known courses
        call_count = 0

        async def multi_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_result
            else:
                courses_result = MagicMock()
                courses_result.all.return_value = []
                return courses_result

        session.execute = AsyncMock(side_effect=multi_execute)

        mock_review_svc.create_review_item = AsyncMock(return_value=MagicMock())

        result = await _classify("art-001")

        assert result["status"] == "waiting_review"
        mock_review_svc.create_review_item.assert_called_once()
