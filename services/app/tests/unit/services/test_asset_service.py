"""Tests for asset_service (flashcards and quiz questions)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import FlashcardData, QuizQuestionData


@pytest.fixture
def sample_flashcard_data():
    """Sample FlashcardData list."""
    return [
        FlashcardData(
            front="What is a firewall?",
            back="A network security system that monitors traffic.",
            tags=["firewalls", "network-security"],
            source_page_ref=1,
        ),
        FlashcardData(
            front="Define IDS.",
            back="Intrusion Detection System — monitors for suspicious activity.",
            tags=["ids"],
            source_page_ref=3,
        ),
    ]


@pytest.fixture
def sample_quiz_data():
    """Sample QuizQuestionData list."""
    return [
        QuizQuestionData(
            question_type="multiple_choice",
            question="Which firewall type tracks connections?",
            options=["A. Packet filter", "B. Stateful", "C. Proxy", "D. NAT"],
            correct_answer="B",
            explanation="Stateful firewalls track active connections.",
            source_page_ref=2,
        ),
        QuizQuestionData(
            question_type="short_answer",
            question="Explain the purpose of an IPS.",
            options=None,
            correct_answer="IPS actively blocks threats in real-time.",
            explanation="Unlike IDS, IPS takes action.",
            source_page_ref=5,
        ),
    ]


@pytest.mark.asyncio
class TestSaveFlashcards:
    """Tests for save_flashcards()."""

    async def test_save_flashcards_creates_records(
        self, mock_session, sample_flashcard_data
    ):
        """Saving flashcards creates new Flashcard records."""
        from app.services.asset_service import save_flashcards

        # Mock delete execute
        # Mock max version query
        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None  # No existing version
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_flashcards(
            mock_session, "course-001", 5, "artifact-001", sample_flashcard_data
        )

        assert len(result) == 2
        assert mock_session.add.call_count == 2
        mock_session.flush.assert_awaited_once()

    async def test_save_flashcards_increments_version(
        self, mock_session, sample_flashcard_data
    ):
        """Saving flashcards uses next generation version."""
        from app.services.asset_service import save_flashcards

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = 3  # Existing version is 3
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_flashcards(
            mock_session, "course-001", 5, "artifact-001", sample_flashcard_data
        )

        # All records should have version 4
        assert all(fc.generation_version == 4 for fc in result)

    async def test_save_flashcards_deletes_existing(
        self, mock_session, sample_flashcard_data
    ):
        """Saving flashcards deletes existing ones for the artifact."""
        from app.services.asset_service import save_flashcards

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        await save_flashcards(
            mock_session, "course-001", 5, "artifact-001", sample_flashcard_data
        )

        # First execute call is the delete
        assert mock_session.execute.call_count == 2

    async def test_save_empty_flashcards(self, mock_session):
        """Saving empty list creates no records."""
        from app.services.asset_service import save_flashcards

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_flashcards(
            mock_session, "course-001", 5, "artifact-001", []
        )

        assert len(result) == 0
        assert mock_session.add.call_count == 0


@pytest.mark.asyncio
class TestSaveQuizQuestions:
    """Tests for save_quiz_questions()."""

    async def test_save_quiz_questions_creates_records(
        self, mock_session, sample_quiz_data
    ):
        """Saving quiz questions creates new QuizQuestion records."""
        from app.services.asset_service import save_quiz_questions

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_quiz_questions(
            mock_session, "course-001", 5, "artifact-001", sample_quiz_data
        )

        assert len(result) == 2
        assert mock_session.add.call_count == 2

    async def test_save_quiz_questions_increments_version(
        self, mock_session, sample_quiz_data
    ):
        """Saving quiz questions uses next generation version."""
        from app.services.asset_service import save_quiz_questions

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = 2
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_quiz_questions(
            mock_session, "course-001", 5, "artifact-001", sample_quiz_data
        )

        assert all(q.generation_version == 3 for q in result)

    async def test_save_quiz_preserves_question_types(
        self, mock_session, sample_quiz_data
    ):
        """Saved records preserve question type and options."""
        from app.services.asset_service import save_quiz_questions

        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None
        mock_session.execute = AsyncMock(
            side_effect=[MagicMock(), mock_max_result]
        )

        result = await save_quiz_questions(
            mock_session, "course-001", 5, "artifact-001", sample_quiz_data
        )

        mcq = result[0]
        sa = result[1]
        assert mcq.question_type == "multiple_choice"
        assert mcq.options_json is not None
        assert sa.question_type == "short_answer"
        assert sa.options_json is None


@pytest.mark.asyncio
class TestGetFlashcards:
    """Tests for flashcard query functions."""

    async def test_get_flashcards_for_week(self, mock_session):
        """Returns flashcards for a specific week."""
        from app.services.asset_service import get_flashcards_for_week

        mock_fc = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_fc]
        mock_session.execute.return_value = mock_result

        result = await get_flashcards_for_week(mock_session, "CSIT302", 5)

        assert len(result) == 1
        mock_session.execute.assert_awaited_once()

    async def test_get_flashcards_for_course(self, mock_session):
        """Returns all flashcards for a course."""
        from app.services.asset_service import get_flashcards_for_course

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await get_flashcards_for_course(mock_session, "CSIT302")

        assert result == []


@pytest.mark.asyncio
class TestGetQuizQuestions:
    """Tests for quiz question query functions."""

    async def test_get_quiz_questions_for_week(self, mock_session):
        """Returns quiz questions for a specific week."""
        from app.services.asset_service import get_quiz_questions_for_week

        mock_q = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_q]
        mock_session.execute.return_value = mock_result

        result = await get_quiz_questions_for_week(mock_session, "CSIT302", 5)

        assert len(result) == 1

    async def test_get_quiz_questions_for_course(self, mock_session):
        """Returns all quiz questions for a course."""
        from app.services.asset_service import get_quiz_questions_for_course

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await get_quiz_questions_for_course(mock_session, "CSIT302")

        assert result == []
