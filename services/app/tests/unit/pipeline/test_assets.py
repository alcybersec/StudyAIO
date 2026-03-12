"""Tests for assets pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import FlashcardData, QuizQuestionData
from app.core.exceptions import AssetGenerationError


class TestAssetsInput:
    """Tests for chain-compatible input handling."""

    def test_assets_skips_duplicate(self):
        """Dict with duplicate status is passed through."""
        from app.pipeline.assets import generate_assets

        input_value = {"artifact_id": "art-001", "status": "duplicate"}
        result = generate_assets.run(input_value)

        assert result["status"] == "duplicate"

    def test_assets_skips_waiting_review(self):
        """Dict with waiting_review status is passed through."""
        from app.pipeline.assets import generate_assets

        input_value = {"artifact_id": "art-001", "status": "waiting_review"}
        result = generate_assets.run(input_value)

        assert result["status"] == "waiting_review"

    def test_assets_skips_failed(self):
        """Dict with failed status is passed through."""
        from app.pipeline.assets import generate_assets

        input_value = {"artifact_id": "art-001", "status": "failed"}
        result = generate_assets.run(input_value)

        assert result["status"] == "failed"

    def test_assets_accepts_string(self):
        """String input is treated as artifact_id (will fail without DB)."""
        from app.pipeline.assets import generate_assets

        with pytest.raises((Exception, SystemExit)):
            generate_assets.run("art-001")

    def test_assets_empty_artifact_id_raises(self):
        """Empty artifact_id raises AssetGenerationError."""
        from app.pipeline.assets import generate_assets

        with pytest.raises(AssetGenerationError, match="No artifact_id"):
            generate_assets.run("")


class TestAssetsStage:
    """Tests for _generate_assets async function."""

    @patch("app.pipeline.assets.asset_service")
    @patch("app.pipeline.assets.get_agent")
    @patch(
        "app.services.settings_service.get_user_agent_config",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("app.pipeline.assets.async_session_factory")
    @pytest.mark.asyncio
    async def test_generate_assets_success(
        self, mock_session_factory, _mock_user_config, mock_get_agent, mock_asset_svc
    ):
        """Successful asset generation creates flashcards and quizzes."""
        from app.pipeline.assets import _generate_assets

        # Mock course
        course = MagicMock()
        course.code = "CSIT302"

        # Mock artifact
        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.course_id = "course-001"
        artifact.week = 5
        artifact.course = course

        # Mock extraction
        extraction = MagicMock()
        extraction.manifest_json = {
            "pages": [{"page_number": 1, "text": "Content", "images": []}],
        }
        extraction.artifact_id = "art-001"

        # Mock summary
        summary = MagicMock()
        summary.content_md = "# Summary content"

        session = AsyncMock()
        session.add = MagicMock()

        # Execute calls: artifact, extraction, summary
        mock_result_artifact = MagicMock()
        mock_result_artifact.unique.return_value.scalar_one_or_none.return_value = artifact

        mock_result_extraction = MagicMock()
        mock_result_extraction.scalar_one_or_none.return_value = extraction

        mock_result_summary = MagicMock()
        mock_result_summary.scalar_one_or_none.return_value = summary

        session.execute = AsyncMock(
            side_effect=[mock_result_artifact, mock_result_extraction, mock_result_summary]
        )

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock agent
        agent = AsyncMock()
        agent.generate_flashcards.return_value = [
            FlashcardData(front="Q1", back="A1", tags=["t1"], source_page_ref=1),
        ]
        agent.generate_quiz.return_value = [
            QuizQuestionData(
                question_type="multiple_choice",
                question="Q?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
                explanation="Because.",
                source_page_ref=1,
            ),
        ]
        mock_get_agent.return_value = agent

        # Mock asset service
        mock_fc_record = MagicMock()
        mock_quiz_record = MagicMock()
        mock_asset_svc.save_flashcards = AsyncMock(return_value=[mock_fc_record])
        mock_asset_svc.save_quiz_questions = AsyncMock(return_value=[mock_quiz_record])

        result = await _generate_assets("art-001")

        assert result["status"] == "processed"
        assert result["artifact_id"] == "art-001"
        assert result["flashcard_count"] == 1
        assert result["quiz_count"] == 1
        assert artifact.status == "processed"

    @patch("app.pipeline.assets.async_session_factory")
    @pytest.mark.asyncio
    async def test_generate_assets_artifact_not_found(self, mock_session_factory):
        """Missing artifact raises AssetGenerationError."""
        from app.pipeline.assets import _generate_assets

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(AssetGenerationError, match="not found"):
            await _generate_assets("art-001")

    @patch("app.pipeline.assets.async_session_factory")
    @pytest.mark.asyncio
    async def test_generate_assets_not_classified(self, mock_session_factory):
        """Unclassified artifact raises AssetGenerationError."""
        from app.pipeline.assets import _generate_assets

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.course_id = None
        artifact.week = None

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(AssetGenerationError, match="not classified"):
            await _generate_assets("art-001")
