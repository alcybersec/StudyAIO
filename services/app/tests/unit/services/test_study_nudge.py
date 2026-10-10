"""PROD-03 (GL#15): reminders opt-out by default and the day-2 study nudge."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services import email_service, notification_service, nudge_service
from app.services.notification_service import (
    CHANNELS,
    DEFAULT_ENABLED,
    EVENT_TYPES,
    seed_default_preferences,
)


def _session(prefs: list | None = None) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = prefs or []
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    return session


def test_global_flag_defaults_on() -> None:
    assert Settings.model_fields["notifications_enabled"].default is True


def test_study_nudge_is_an_event_type() -> None:
    assert "study_nudge" in EVENT_TYPES


@pytest.mark.asyncio
async def test_seed_enables_useful_email_reminders_only() -> None:
    session = _session()
    prefs = await seed_default_preferences(session, "u1")
    on = {(p.channel, p.event_type) for p in prefs if p.enabled}
    assert on == DEFAULT_ENABLED
    assert on == {
        ("email", "cards_due"),
        ("email", "exam_reminder"),
        ("email", "weekly_digest"),
        ("email", "study_nudge"),
    }
    assert len(prefs) == len(CHANNELS) * len(EVENT_TYPES)
    assert all(p.user_id == "u1" for p in prefs)


@pytest.mark.asyncio
async def test_register_user_seeds_preferences() -> None:
    from app.services import user_service

    session = _session()
    with patch.object(notification_service, "seed_default_preferences", new=AsyncMock()) as seed:
        user = await user_service.register_user(session, "A@b.co", "alex", "pw-123456789")
    assert seed.await_args.args[1] == user.id


def test_stmt_is_window_scoped_and_requires_opt_in() -> None:
    now = datetime(2026, 10, 10, 12, tzinfo=UTC)
    sql = str(nudge_service.candidates_stmt(now)).lower()
    assert "notification_preferences.event_type" in sql
    assert "notification_preferences.enabled" in sql
    assert "users.is_active" in sql
    assert "not (exists" in sql or "not exists" in sql
    # activity checks are correlated to the same user, not global
    assert "study_sessions.user_id = users.id" in sql
    assert "flashcard_reviews.user_id = users.id" in sql
    assert "lecture_artifacts.user_id = users.id" in sql


@pytest.mark.asyncio
async def test_find_candidates_maps_rows() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [("u1", "Europe/Oslo", True), ("u2", None, False)]
    session.execute.return_value = result
    cands = await nudge_service.find_nudge_candidates(session)
    assert [(c.user_id, c.timezone, c.has_uploads) for c in cands] == [
        ("u1", "Europe/Oslo", True),
        ("u2", None, False),
    ]


def test_content_differs_by_progress() -> None:
    no_upload = nudge_service.nudge_content(False)
    uploaded = nudge_service.nudge_content(True)
    assert "upload" in no_upload.body.lower()
    assert "flashcard" in uploaded.body.lower()
    assert no_upload.href != uploaded.href


@pytest.mark.asyncio
async def test_send_nudge_goes_to_inbox_and_notify() -> None:
    session = AsyncMock()
    with (
        patch.object(notification_service, "notify_inbox", new=AsyncMock()) as inbox,
        patch.object(notification_service, "notify", new=AsyncMock(return_value={})) as notify,
    ):
        await nudge_service.send_study_nudge(session, "u1", has_uploads=True)
    assert inbox.await_args.args[1] == "u1"
    assert notify.await_args.args[1] == "u1"
    assert notify.await_args.args[2] == "study_nudge"


def test_email_has_unsubscribe_link_to_notification_settings() -> None:
    html = email_service.render_template("study_nudge.html", body="Hi", cta_url="http://x/y")
    assert "/settings/notifications" in html
    footer = email_service.render_template("cards_due.html", due_count=2)
    assert "/settings/notifications" in footer


@pytest.mark.asyncio
async def test_email_sender_exists_for_nudge() -> None:
    with patch.object(email_service, "send_email", new=AsyncMock(return_value=True)) as send:
        assert await email_service.send_study_nudge("a@b.co", body="Hi", cta_url="http://x")
    assert send.await_args.args[0] == "a@b.co"
