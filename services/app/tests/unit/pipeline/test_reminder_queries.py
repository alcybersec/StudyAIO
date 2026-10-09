"""R-016: reminder/digest queries must use real columns and scope via the owning course."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

# Reminders fire at local 08:00; the digest only on a local Sunday.
_SUNDAY_0800_UTC = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)


def _factory_for(session: AsyncMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def _capturing_session(users: list[str]) -> tuple[AsyncMock, list]:
    session = AsyncMock()
    seen: list = []
    first = MagicMock()
    first.all.return_value = [(u, "UTC") for u in users]
    rest = MagicMock()
    rest.scalar.return_value = 0

    async def _execute(stmt, *a, **k):
        seen.append(stmt)
        return first if len(seen) == 1 else rest

    session.execute = _execute
    return session, seen


@pytest.mark.asyncio
class TestReminderQueriesUseRealColumns:
    async def test_daily_due_count_scoped_via_course_and_skips_archived(self):
        from app.pipeline.notification_tasks import _send_daily_reminders

        session, seen = _capturing_session(["user-001"])
        with (
            patch("app.core.clock.utc_now", return_value=_SUNDAY_0800_UTC),
            patch("app.pipeline.notification_tasks.async_session_factory", _factory_for(session)),
        ):
            await _send_daily_reminders()

        sql = _sql(seen[1])
        assert "flashcards.user_id" not in sql
        assert "courses.user_id" in sql
        assert "flashcards.archived_at is null" in sql
        assert "user-001" in seen[1].compile().params.values()

    async def test_weekly_quiz_count_scoped_via_course(self):
        from app.pipeline.notification_tasks import _send_weekly_digest

        session, seen = _capturing_session(["user-001"])
        with (
            patch("app.core.clock.utc_now", return_value=_SUNDAY_0800_UTC),
            patch("app.pipeline.notification_tasks.async_session_factory", _factory_for(session)),
            patch("app.services.notification_service.notify", AsyncMock(return_value={})),
        ):
            await _send_weekly_digest()

        quiz_sql = [(s, _sql(s)) for s in seen if "from quiz_attempts" in _sql(s)]
        assert quiz_sql, "weekly digest must query quiz attempts"
        stmt, sql = quiz_sql[0]
        assert "quiz_attempts.user_id" not in sql
        assert "courses.user_id" in sql
        assert "user-001" in stmt.compile().params.values()
