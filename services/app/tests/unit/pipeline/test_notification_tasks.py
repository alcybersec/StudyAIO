"""Tests for scheduled notification tasks (deadline reminders)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _session_factory_for(session: AsyncMock) -> MagicMock:
    """Build an async_session_factory mock yielding `session`."""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _deadline_row(deadline_id: str, days_ahead: int) -> MagicMock:
    row = MagicMock()
    row.deadline_id = deadline_id
    row.title = "Assignment 1"
    row.due_date = date.today() + timedelta(days=days_ahead)
    row.course_code = "CSIT302"
    row.user_id = "user-001"
    return row


@pytest.mark.asyncio
class TestSendDeadlineReminders:
    """Tests for _send_deadline_reminders idempotent daily scan."""

    async def test_emits_notification_for_upcoming_deadline(self):
        """A deadline due within the window creates one inbox notification."""
        from app.pipeline.notification_tasks import _send_deadline_reminders

        session = AsyncMock()
        session.add = MagicMock()

        deadlines_result = MagicMock()
        deadlines_result.all.return_value = [_deadline_row("dl-001", days_ahead=3)]
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[deadlines_result, existing_result])

        with patch(
            "app.pipeline.notification_tasks.async_session_factory",
            _session_factory_for(session),
        ):
            notified = await _send_deadline_reminders()

        assert notified == 1
        from app.models.notification import Notification

        added = [c.args[0] for c in session.add.call_args_list]
        notifications = [n for n in added if isinstance(n, Notification)]
        assert len(notifications) == 1
        assert notifications[0].kind == "deadline"
        assert notifications[0].user_id == "user-001"

    async def test_emits_at_most_once_per_deadline_per_day(self):
        """A deadline already notified today is skipped (idempotent)."""
        from app.pipeline.notification_tasks import _send_deadline_reminders

        session = AsyncMock()
        session.add = MagicMock()

        deadlines_result = MagicMock()
        deadlines_result.all.return_value = [_deadline_row("dl-001", days_ahead=3)]
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = "notif-already-sent"
        session.execute = AsyncMock(side_effect=[deadlines_result, existing_result])

        with patch(
            "app.pipeline.notification_tasks.async_session_factory",
            _session_factory_for(session),
        ):
            notified = await _send_deadline_reminders()

        assert notified == 0
        from app.models.notification import Notification

        added = [c.args[0] for c in session.add.call_args_list]
        assert not [n for n in added if isinstance(n, Notification)]

    async def test_no_deadlines_is_noop(self):
        """No upcoming deadlines → nothing emitted."""
        from app.pipeline.notification_tasks import _send_deadline_reminders

        session = AsyncMock()
        session.add = MagicMock()
        deadlines_result = MagicMock()
        deadlines_result.all.return_value = []
        session.execute = AsyncMock(return_value=deadlines_result)

        with patch(
            "app.pipeline.notification_tasks.async_session_factory",
            _session_factory_for(session),
        ):
            notified = await _send_deadline_reminders()

        assert notified == 0


@pytest.mark.asyncio
class TestDeadlineReminderUtcWindow:
    """The dedup window and due-date range use the UTC date, not the host's."""

    async def test_window_uses_utc_date_when_local_date_differs(self):
        """At 22:00 UTC on Oct 9 a UTC+4 host reads Oct 10; the window must stay Oct 9."""
        import datetime as real_dt

        from app.pipeline import notification_tasks

        utc_now = real_dt.datetime(2026, 10, 9, 22, 0, tzinfo=real_dt.UTC)
        local_today = real_dt.date(2026, 10, 10)  # what date.today() says on UTC+4

        class FakeDatetime(real_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_now.astimezone(tz) if tz else utc_now.replace(tzinfo=None)

        class FakeDate(real_dt.date):
            @classmethod
            def today(cls):
                return local_today

        session = AsyncMock()
        session.add = MagicMock()
        deadlines_result = MagicMock()
        deadlines_result.all.return_value = [_deadline_row("dl-001", days_ahead=3)]
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = "already"
        session.execute = AsyncMock(side_effect=[deadlines_result, existing_result])

        with (
            patch.object(notification_tasks, "datetime", FakeDatetime),
            patch.object(notification_tasks, "date", FakeDate),
            patch.object(
                notification_tasks,
                "async_session_factory",
                _session_factory_for(session),
            ),
        ):
            await notification_tasks._send_deadline_reminders()

        range_params = session.execute.call_args_list[0].args[0].compile().params
        assert real_dt.date(2026, 10, 9) in range_params.values()
        dedup_params = session.execute.call_args_list[1].args[0].compile().params
        assert real_dt.datetime(2026, 10, 9, tzinfo=real_dt.UTC) in dedup_params.values()
