"""Owner-scoped create/edit/archive of flashcards and quiz questions (GL#48, floor 4)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.services import asset_service
from app.services.asset_service import ItemNotFoundError, NoSourceArtifactError

USER = "user-1"


def _result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.first.return_value = value
    return r


def _sql(session, n: int) -> str:
    return str(session.execute.await_args_list[n].args[0].compile())


def _card() -> Flashcard:
    return Flashcard(
        id="fc-1",
        course_id="c-1",
        week=3,
        front="old front",
        back="old back",
        tags=["t"],
        source_artifact_id="a-1",
        source_page_ref=4,
        generation_version=2,
        origin="pipeline",
        archived_at=None,
    )


def _question() -> QuizQuestion:
    return QuizQuestion(
        id="q-1",
        course_id="c-1",
        week=3,
        question_type="multiple_choice",
        question="old?",
        options_json=["A. x", "B. y"],
        correct_answer="A",
        explanation="because",
        source_artifact_id="a-1",
        source_page_ref=4,
        generation_version=2,
        origin="pipeline",
        archived_at=None,
    )


@pytest.mark.asyncio
class TestArchive:
    async def test_archive_flashcard_sets_archived_at_and_never_deletes(self, mock_session):
        card = _card()
        mock_session.execute.side_effect = [_result(card)]
        await asset_service.archive_flashcard(mock_session, "fc-1", user_id=USER)
        assert card.archived_at is not None
        mock_session.delete.assert_not_called()
        assert "courses.user_id" in _sql(mock_session, 0)
        assert "archived_at IS NULL" in _sql(mock_session, 0)

    async def test_archive_flashcard_missing_raises_not_found(self, mock_session):
        mock_session.execute.side_effect = [_result(None)]
        with pytest.raises(ItemNotFoundError):
            await asset_service.archive_flashcard(mock_session, "nope", user_id=USER)

    async def test_archive_quiz_question_soft_deletes_scoped(self, mock_session):
        q = _question()
        mock_session.execute.side_effect = [_result(q)]
        await asset_service.archive_quiz_question(mock_session, "q-1", user_id=USER)
        assert q.archived_at is not None
        mock_session.delete.assert_not_called()
        assert "courses.user_id" in _sql(mock_session, 0)

    async def test_archive_quiz_question_missing_raises(self, mock_session):
        mock_session.execute.side_effect = [_result(None)]
        with pytest.raises(ItemNotFoundError):
            await asset_service.archive_quiz_question(mock_session, "x", user_id=USER)


@pytest.mark.asyncio
class TestEdit:
    async def test_update_flashcard_archives_original_and_inserts_user_copy(self, mock_session):
        card = _card()
        review = FlashcardReview(
            id="r-1",
            user_id=USER,
            flashcard_id="fc-1",
            ease_factor=2.1,
            interval_days=6,
            repetition_count=3,
            next_review_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        mock_session.execute.side_effect = [_result(card), _result(review)]
        new = await asset_service.update_flashcard(mock_session, "fc-1", user_id=USER, front="new")
        assert card.archived_at is not None
        assert card.front == "old front"  # the AI original is untouched
        assert new.id != "fc-1"
        assert new.origin == "user"
        assert new.front == "new"
        assert new.back == "old back"  # unchanged field carried over
        assert new.source_artifact_id == "a-1"
        assert new.generation_version == 2
        added = [c.args[0] for c in mock_session.add.call_args_list]
        assert new in added
        copied = [a for a in added if isinstance(a, FlashcardReview)]
        assert len(copied) == 1
        assert copied[0].flashcard_id == new.id
        assert copied[0].interval_days == 6
        assert copied[0].user_id == USER
        mock_session.delete.assert_not_called()
        assert "courses.user_id" in _sql(mock_session, 0)

    async def test_update_flashcard_foreign_id_raises_not_found(self, mock_session):
        mock_session.execute.side_effect = [_result(None)]
        with pytest.raises(ItemNotFoundError):
            await asset_service.update_flashcard(mock_session, "fc-9", user_id=USER, front="x")
        mock_session.add.assert_not_called()

    async def test_update_quiz_question_archives_original_and_copies(self, mock_session):
        q = _question()
        mock_session.execute.side_effect = [_result(q)]
        new = await asset_service.update_quiz_question(
            mock_session, "q-1", user_id=USER, correct_answer="B"
        )
        assert q.archived_at is not None
        assert q.correct_answer == "A"
        assert new.origin == "user"
        assert new.correct_answer == "B"
        assert new.question == "old?"
        assert new.options_json == ["A. x", "B. y"]
        assert new.id != "q-1"
        mock_session.delete.assert_not_called()

    async def test_update_quiz_rejects_answer_outside_options(self, mock_session):
        mock_session.execute.side_effect = [_result(_question())]
        with pytest.raises(ValueError):
            await asset_service.update_quiz_question(
                mock_session, "q-1", user_id=USER, correct_answer="Z"
            )
        mock_session.add.assert_not_called()


@pytest.mark.asyncio
class TestCreate:
    async def test_create_flashcard_uses_newest_artifact_of_the_week(self, mock_session):
        course = MagicMock(id="c-1")
        with patch(
            "app.services.asset_service.course_service.get_course_by_code_ci",
            new_callable=AsyncMock,
            return_value=course,
        ) as get_course:
            mock_session.execute.side_effect = [_result("a-9")]
            card = await asset_service.create_flashcard(
                mock_session,
                user_id=USER,
                course_code="CSIT302",
                week=3,
                front="f",
                back="b",
                tags=["x"],
            )
        assert get_course.await_args.kwargs.get("user_id") == USER
        assert card.origin == "user"
        assert card.course_id == "c-1"
        assert card.source_artifact_id == "a-9"
        assert card.source_page_ref == 0
        assert "lecture_artifacts.user_id" in _sql(mock_session, 0)

    async def test_create_flashcard_unknown_course_raises_not_found(self, mock_session):
        with patch(
            "app.services.asset_service.course_service.get_course_by_code_ci",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(ItemNotFoundError):
                await asset_service.create_flashcard(
                    mock_session,
                    user_id=USER,
                    course_code="NOPE",
                    week=1,
                    front="f",
                    back="b",
                )

    async def test_create_without_any_artifact_raises_no_source(self, mock_session):
        with patch(
            "app.services.asset_service.course_service.get_course_by_code_ci",
            new_callable=AsyncMock,
            return_value=MagicMock(id="c-1"),
        ):
            mock_session.execute.side_effect = [_result(None)]
            with pytest.raises(NoSourceArtifactError):
                await asset_service.create_quiz_question(
                    mock_session,
                    user_id=USER,
                    course_code="CSIT302",
                    week=1,
                    question_type="short_answer",
                    question="q?",
                    options=None,
                    correct_answer="a",
                    explanation="",
                )

    async def test_explicit_source_artifact_is_owner_and_course_scoped(self, mock_session):
        with patch(
            "app.services.asset_service.course_service.get_course_by_code_ci",
            new_callable=AsyncMock,
            return_value=MagicMock(id="c-1"),
        ):
            mock_session.execute.side_effect = [_result(None)]
            with pytest.raises(ItemNotFoundError):
                await asset_service.create_flashcard(
                    mock_session,
                    user_id=USER,
                    course_code="CSIT302",
                    week=1,
                    front="f",
                    back="b",
                    source_artifact_id="foreign",
                )
        sql = _sql(mock_session, 0)
        assert "lecture_artifacts.user_id" in sql
        assert "lecture_artifacts.course_id" in sql


@pytest.mark.asyncio
class TestRegenerationNeverTouchesUserItems:
    async def test_save_flashcards_archive_is_limited_to_pipeline_origin(self, mock_session):
        mock_session.execute.return_value.scalar.return_value = 0
        await asset_service.save_flashcards(mock_session, "c-1", 1, "a-1", [])
        params = mock_session.execute.await_args_list[0].args[0].compile().params
        assert "pipeline" in params.values()
        assert "user" not in params.values()

    async def test_save_quiz_archive_is_limited_to_pipeline_origin(self, mock_session):
        mock_session.execute.return_value.scalar.return_value = 0
        await asset_service.save_quiz_questions(mock_session, "c-1", 1, "a-1", [])
        params = mock_session.execute.await_args_list[0].args[0].compile().params
        assert "pipeline" in params.values()
        assert "user" not in params.values()
