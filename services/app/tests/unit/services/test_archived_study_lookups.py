"""Archived flashcards / quiz questions are not reviewable or answerable.

The by-id lookups behind POST /study/review and /study/quiz-attempt must treat
an archived row as absent (the endpoint then 404s). History stays readable
because list/stat queries do not go through these lookups.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services import exam_service, srs_service


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _session() -> tuple[AsyncMock, list]:
    stmts: list = []
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    async def execute(stmt, *a, **k):
        stmts.append(stmt)
        return result

    session = AsyncMock()
    session.execute = execute
    return session, stmts


@pytest.mark.asyncio
async def test_get_owned_flashcard_excludes_archived_but_keeps_owner_scope():
    session, stmts = _session()
    await srs_service.get_owned_flashcard(session, "fc-1", user_id="u1")
    sql = _sql(stmts[0])
    assert "flashcards.archived_at IS NULL" in sql
    assert "courses.user_id = 'u1'" in sql


@pytest.mark.asyncio
async def test_get_owned_quiz_question_excludes_archived_but_keeps_owner_scope():
    session, stmts = _session()
    await exam_service.get_owned_quiz_question(session, "qq-1", user_id="u1")
    sql = _sql(stmts[0])
    assert "quiz_questions.archived_at IS NULL" in sql
    assert "courses.user_id = 'u1'" in sql
