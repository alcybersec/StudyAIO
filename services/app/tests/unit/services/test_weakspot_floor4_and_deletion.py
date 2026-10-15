"""Floor 4 and account deletion for the weak-spot columns and tables (ADR 0007 Decision 8)."""

from unittest.mock import AsyncMock, MagicMock

from app.agents.base import FlashcardData, QuizQuestionData
from app.services import account_service, asset_service


def _session():
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar.return_value = 2
    session.execute.return_value = result
    return session


def _update_sql(session) -> str:
    stmt = session.execute.await_args_list[0].args[0]
    compiled = stmt.compile()
    return f"{compiled} {compiled.params}"


def _card() -> FlashcardData:
    return FlashcardData(front="f", back="b", tags=[], source_page_ref=1)


class TestRegenerationKeepsTargetedItems:
    async def test_flashcard_regeneration_archives_only_pipeline_items(self):
        session = _session()
        await asset_service.save_flashcards(session, "c-1", 1, "a-1", [_card()])
        sql = _update_sql(session)
        assert "flashcards.origin" in sql and "pipeline" in sql

    async def test_quiz_regeneration_archives_only_pipeline_items(self):
        session = _session()
        q = QuizQuestionData(
            question_type="mcq",
            question="q",
            options=None,
            correct_answer="a",
            explanation="e",
            source_page_ref=1,
        )
        await asset_service.save_quiz_questions(session, "c-1", 1, "a-1", [q])
        sql = _update_sql(session)
        assert "quiz_questions.origin" in sql and "pipeline" in sql

    async def test_new_pipeline_items_are_not_marked_targeted(self):
        session = _session()
        await asset_service.save_flashcards(session, "c-1", 1, "a-1", [_card()])
        assert session.add.call_args.args[0].origin in (None, "pipeline")


class TestAccountDeletion:
    def _positions(self):
        return {t.name: i for i, t in enumerate(reversed(account_service._ordered_tables()))}

    def test_items_are_deleted_before_the_generation_that_made_them(self):
        pos = self._positions()
        assert pos["quiz_questions"] < pos["targeted_generations"]
        assert pos["flashcards"] < pos["targeted_generations"]

    def test_generations_and_plans_are_deleted_before_their_parents(self):
        pos = self._positions()
        assert pos["targeted_generations"] < pos["courses"]
        assert pos["targeted_generations"] < pos["users"]
        assert pos["study_plans"] < pos["users"]

    def test_new_tables_are_user_scoped_not_global(self):
        scoped, global_ = account_service.classify_tables()
        assert {"study_plans", "targeted_generations"} <= set(scoped)
        assert not {"study_plans", "targeted_generations"} & set(global_)
