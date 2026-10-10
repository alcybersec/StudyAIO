"""Tests for scheduled notification tasks (deadline reminders)."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _session_factory_for(session: AsyncMock) -> MagicMock:
    """Build an async_session_factory mock yielding `session`."""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


# 2026-10-09 is a Friday; 08:00 UTC.
NOON_UTC = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)


def freeze(at: datetime):
    """Freeze the single clock source (app.core.clock.utc_now)."""
    return patch("app.core.clock.utc_now", return_value=at)


def _deadline_row(deadline_id: str, days_ahead: int, tz: str | None = "UTC") -> MagicMock:
    row = MagicMock()
    row.timezone = tz
    row.deadline_id = deadline_id
    row.title = "Assignment 1"
    row.due_date = date(2026, 10, 9) + timedelta(days=days_ahead)
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

        with (
            freeze(NOON_UTC),
            patch(
                "app.pipeline.notification_tasks.async_session_factory",
                _session_factory_for(session),
            ),
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

        with (
            freeze(NOON_UTC),
            patch(
                "app.pipeline.notification_tasks.async_session_factory",
                _session_factory_for(session),
            ),
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

        with (
            freeze(NOON_UTC),
            patch(
                "app.pipeline.notification_tasks.async_session_factory",
                _session_factory_for(session),
            ),
        ):
            notified = await _send_deadline_reminders()

        assert notified == 0


def _recipient_session(rows: list[tuple[str, str | None]]) -> AsyncMock:
    """A session whose first query returns (user_id, timezone) pref rows."""
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    result.scalar.return_value = 2
    session.execute = AsyncMock(return_value=result)
    return session


def _hours_of_day(start: datetime):
    return [start + timedelta(hours=h) for h in range(24)]


USERS = [("tokyo", "Asia/Tokyo"), ("la", "America/Los_Angeles"), ("utc", None)]


@pytest.mark.asyncio
class TestHourlyLocalSend:
    """Beat fires hourly; each user is served once, at their own 08:00."""

    async def _run_day(self, runner: str, start: datetime, notify_attr: str):
        from app.pipeline import notification_tasks
        from app.services import notification_service

        sent: list[tuple[str, datetime]] = []
        current = {"t": start}

        async def record(session, user_id, *a, **k):
            sent.append((user_id, current["t"]))
            return {}

        with (
            patch.object(notification_service, notify_attr, side_effect=record),
            patch.object(
                notification_tasks,
                "async_session_factory",
                lambda: _session_factory_for(_recipient_session(USERS))(),
            ),
        ):
            for t in _hours_of_day(start):
                current["t"] = t
                with freeze(t):
                    await getattr(notification_tasks, runner)()
        return sent

    async def test_daily_each_user_gets_exactly_one_at_local_0800(self):
        start = datetime(2026, 10, 9, 0, 0, tzinfo=UTC)
        sent = await self._run_day("_send_daily_reminders", start, "notify_cards_due")
        by_user = {u: t for u, t in sent}
        assert sorted(u for u, _ in sent) == ["la", "tokyo", "utc"]
        assert by_user["tokyo"].hour == 23  # 08:00 JST the previous UTC evening
        assert by_user["la"].hour == 15  # 08:00 PDT
        assert by_user["utc"].hour == 8

    async def test_rerun_in_same_hour_sends_nothing(self):
        from app.pipeline import notification_tasks
        from app.services import notification_service

        with (
            freeze(datetime(2026, 10, 9, 23, 30, tzinfo=UTC)),  # 08:30 Sat JST
            patch.object(notification_service, "notify_cards_due", AsyncMock()) as notify,
            patch.object(
                notification_tasks,
                "async_session_factory",
                lambda: _session_factory_for(_recipient_session([("tokyo", "Asia/Tokyo")]))(),
            ),
        ):
            first = await notification_tasks._send_daily_reminders()
            second = await notification_tasks._send_daily_reminders()
        assert (first, second) == (1, 0)
        assert notify.await_count == 1

    async def test_failed_send_releases_claim_for_retry(self):
        from app.pipeline import notification_tasks
        from app.services import notification_service

        notify = AsyncMock(side_effect=[RuntimeError("smtp"), {}])
        with (
            freeze(NOON_UTC),
            patch.object(notification_service, "notify_cards_due", notify),
            patch.object(
                notification_tasks,
                "async_session_factory",
                lambda: _session_factory_for(_recipient_session([("utc", "UTC")]))(),
            ),
        ):
            assert await notification_tasks._send_daily_reminders() == 0
            assert await notification_tasks._send_daily_reminders() == 1

    async def test_digest_only_on_local_sunday_at_0800(self):
        from app.pipeline import notification_tasks
        from app.services import notification_service

        sent = []

        async def record(session, user_id, *a, **k):
            sent.append(user_id)
            return {}

        # Sat 2026-10-10 23:00 UTC = Sun 08:00 Tokyo; Sun 15:00 UTC = Sun 08:00 LA.
        # Sun 08:00 UTC is Sunday for the UTC user.
        stamps = {
            "tokyo": datetime(2026, 10, 10, 23, 0, tzinfo=UTC),
            "la": datetime(2026, 10, 11, 15, 0, tzinfo=UTC),
            "utc": datetime(2026, 10, 11, 8, 0, tzinfo=UTC),
        }
        weekday_misses = [  # same local hour, but Saturday / Monday locally
            datetime(2026, 10, 9, 23, 0, tzinfo=UTC),  # Sat 08:00 Tokyo
            datetime(2026, 10, 10, 15, 0, tzinfo=UTC),  # Sat 08:00 LA
            datetime(2026, 10, 12, 8, 0, tzinfo=UTC),  # Mon UTC
        ]
        with (
            patch.object(notification_service, "notify", side_effect=record),
            patch.object(
                notification_tasks,
                "async_session_factory",
                lambda: _session_factory_for(_recipient_session(USERS))(),
            ),
        ):
            for t in weekday_misses:
                with freeze(t):
                    assert await notification_tasks._send_weekly_digest() == 0
            for t in stamps.values():
                with freeze(t):
                    await notification_tasks._send_weekly_digest()
                    await notification_tasks._send_weekly_digest()  # re-run: no-op
        assert sorted(sent) == ["la", "tokyo", "utc"]

    async def test_invalid_timezone_falls_back_to_utc(self):
        from app.pipeline import notification_tasks

        # Invalid tz -> UTC. 12:00 UTC is not a send hour; 08:00 UTC is.
        with freeze(datetime(2026, 10, 9, 12, 0, tzinfo=UTC)):
            assert notification_tasks._is_send_time("Not/AZone") is False
        with freeze(NOON_UTC):
            assert notification_tasks._is_send_time("Not/AZone") is True

    async def test_deadline_reminder_only_at_owner_local_0800(self):
        from app.pipeline import notification_tasks

        async def run(at: datetime, tz: str) -> int:
            session = AsyncMock()
            session.add = MagicMock()
            rows = MagicMock()
            rows.all.return_value = [_deadline_row("dl", days_ahead=0, tz=tz)]
            none = MagicMock()
            none.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(side_effect=[rows, none])
            with (
                freeze(at),
                patch.object(
                    notification_tasks,
                    "async_session_factory",
                    _session_factory_for(session),
                ),
            ):
                return await notification_tasks._send_deadline_reminders()

        # Tokyo: 08:00 JST on Oct 9 is Oct 8 23:00 UTC; the deadline due Oct 9 is "today".
        assert await run(datetime(2026, 10, 8, 23, 0, tzinfo=UTC), "Asia/Tokyo") == 1
        assert await run(datetime(2026, 10, 9, 8, 0, tzinfo=UTC), "Asia/Tokyo") == 0  # 17:00 JST
