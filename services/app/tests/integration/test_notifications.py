"""Notification preferences, inbox, Telegram and Web Push, dispatch, and the scheduled jobs.

HTTP paths run on the real cookie chain. External senders (SMTP, Telegram, the
push gateway) are replaced at the narrowest point so the routing logic (which
channel fires for which preference) is what is under test. The scheduled jobs run
against committed rows, the way Celery beat runs them.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.deadline import Deadline
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.push_subscription import PushSubscription
from app.models.telegram_link import TelegramLink
from app.models.user_settings import UserSettings
from app.pipeline import notification_tasks
from app.services import email_service, notification_service, push_service, telegram_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestPreferences:
    async def test_defaults_are_seeded_then_updated(self, client_factory, make_user, db_session):
        user = await make_user()
        client = client_factory(user)
        seeded = (await client.get("/api/notifications/preferences")).json()["preferences"]
        assert len(seeded) == len(notification_service.CHANNELS) * len(
            notification_service.EVENT_TYPES
        )
        # GL#15: email reminders are on by default, everything else is opt-in.
        on = {(p["channel"], p["event_type"]) for p in seeded if p["enabled"]}
        assert on == set(notification_service.DEFAULT_ENABLED)
        assert ("email", "cards_due") in on

        resp = await client.put(
            "/api/notifications/preferences",
            json={
                "preferences": [
                    {"channel": "push", "event_type": "cards_due", "enabled": True},
                    {"channel": "email", "event_type": "cards_due", "enabled": False},
                    {"channel": "carrier-pigeon", "event_type": "cards_due", "enabled": True},
                    {"channel": "push", "event_type": "made-up", "enabled": True},
                ]
            },
        )
        assert resp.status_code == 200
        enabled = {
            (p["channel"], p["event_type"]) for p in resp.json()["preferences"] if p["enabled"]
        }
        # unknown channel / event ignored; the user's opt-out of a default sticks
        assert enabled == (set(notification_service.DEFAULT_ENABLED) - {("email", "cards_due")}) | {
            ("push", "cards_due")
        }
        again = (await client.get("/api/notifications/preferences")).json()["preferences"]
        email_cards = next(
            p for p in again if (p["channel"], p["event_type"]) == ("email", "cards_due")
        )
        assert email_cards["enabled"] is False  # stays off after re-read
        rows = (
            (
                await db_session.execute(
                    select(NotificationPreference).where(NotificationPreference.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == len(seeded)

    async def test_preferences_are_per_user(self, client_factory, make_user):
        a, b = await make_user(), await make_user()
        await client_factory(a).put(
            "/api/notifications/preferences",
            json={
                "preferences": [{"channel": "push", "event_type": "weekly_digest", "enabled": True}]
            },
        )
        theirs = (await client_factory(b).get("/api/notifications/preferences")).json()[
            "preferences"
        ]
        on = {(p["channel"], p["event_type"]) for p in theirs if p["enabled"]}
        assert on == set(notification_service.DEFAULT_ENABLED)  # a's push opt-in did not leak


class TestInbox:
    async def test_list_unread_and_mark_read_are_owner_scoped(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        mine = [
            await notification_service.create_inbox_notification(
                db_session, alice.id, "pipeline", f"n{i}"
            )
            for i in range(3)
        ]
        theirs = await notification_service.create_inbox_notification(
            db_session, bob.id, "review", "secret"
        )
        client = client_factory(alice)

        assert (await client.get("/api/notifications/unread-count")).json() == {"count": 3}
        listed = (await client.get("/api/notifications")).json()
        assert {n["id"] for n in listed} == {n.id for n in mine}
        assert "secret" not in str(listed)
        assert len((await client.get("/api/notifications", params={"limit": 2})).json()) == 2

        resp = await client.post(
            "/api/notifications/mark-read", json={"ids": [mine[0].id, theirs.id, "nope"]}
        )
        assert resp.json() == {"updated": 1}  # Bob's row is not Alice's to mark
        await db_session.refresh(theirs)
        assert theirs.read_at is None
        again = await client.post("/api/notifications/mark-read", json={"ids": [mine[0].id]})
        assert again.json() == {"updated": 0}  # idempotent
        assert (await client.get("/api/notifications/unread-count")).json() == {"count": 2}
        unread = (await client.get("/api/notifications", params={"unread": "true"})).json()
        assert len(unread) == 2
        assert (await client.post("/api/notifications/mark-read", json={"ids": []})).json() == {
            "updated": 0
        }

    async def test_notify_inbox_swallows_failures(self, db_session):
        assert (
            await notification_service.notify_inbox(db_session, "no-such-user", "pipeline", "t")
            is None
        )


class TestTelegram:
    async def test_link_flow_webhook_and_unlink(self, client_factory, make_user, db_session):
        user = await make_user()
        client = client_factory(user)
        with patch("app.config.settings.telegram_bot_token", SecretStr("")):
            assert (await client.post("/api/notifications/telegram/link")).status_code == 400

        with (
            patch("app.config.settings.telegram_bot_token", SecretStr("123:abc")),
            patch("app.config.settings.telegram_webhook_secret", SecretStr("s")),
        ):
            link = (await client.post("/api/notifications/telegram/link")).json()
            token = link["link_token"]
            assert link["deep_link"].endswith(f"?start={token}")

            hook = client_factory()
            hdr = {"x-telegram-bot-api-secret-token": "s"}
            welcome = await hook.post(
                "/api/notifications/telegram/webhook",
                json={"message": {"text": "/start", "chat": {"id": 42}}},
                headers=hdr,
            )
            assert "Welcome" in welcome.json()["response"]
            bad = await hook.post(
                "/api/notifications/telegram/webhook",
                json={"message": {"text": "/start bogus", "chat": {"id": 42}}},
                headers=hdr,
            )
            assert "Invalid or expired" in bad.json()["response"]
            ok = await hook.post(
                "/api/notifications/telegram/webhook",
                json={
                    "message": {
                        "text": f"/start {token}",
                        "chat": {"id": 42},
                        "from": {"username": "alice_tg"},
                    }
                },
                headers=hdr,
            )
            assert "linked" in ok.json()["response"]
            # Token is single use.
            replay = await hook.post(
                "/api/notifications/telegram/webhook",
                json={"message": {"text": f"/start {token}", "chat": {"id": 43}}},
                headers=hdr,
            )
            assert "Invalid or expired" in replay.json()["response"]
            nochat = await hook.post(
                "/api/notifications/telegram/webhook", json={"message": {}}, headers=hdr
            )
            assert nochat.json()["response"] == "No chat ID found"
            other = await hook.post(
                "/api/notifications/telegram/webhook",
                json={"message": {"text": "hello", "chat": {"id": 42}}},
                headers=hdr,
            )
            assert "Send /start" in other.json()["response"]

        stored = (
            await db_session.execute(select(TelegramLink).where(TelegramLink.user_id == user.id))
        ).scalar_one()
        assert stored.verified is True and stored.chat_id == 42 and stored.link_token is None
        unlinked = (await client.delete("/api/notifications/telegram/unlink")).json()
        assert unlinked["linked"] is False and unlinked["verified"] is False
        assert await telegram_service.get_link(db_session, user.id) is None

    async def test_webhook_secret_is_enforced_when_configured(self, client_factory):
        url = "https://example.com/hook-secret"
        header = "x-telegram-bot-api-secret-token"
        handler = AsyncMock(return_value="ok")
        with (
            patch("app.config.settings.telegram_webhook_secret", SecretStr("real-secret")),
            patch("app.config.settings.telegram_webhook_url", url),
            patch.object(telegram_service, "handle_telegram_webhook", handler),
        ):
            path = "/api/notifications/telegram/webhook"
            missing = await client_factory().post(path, json={"message": {}})
            assert missing.status_code == 403
            assert missing.json() == {"detail": "Invalid webhook secret"}
            # The public URL is not the secret.
            as_url = await client_factory().post(path, json={"message": {}}, headers={header: url})
            assert as_url.status_code == 403
            handler.assert_not_awaited()
            allowed = await client_factory().post(
                path, json={"message": {}}, headers={header: "real-secret"}
            )
            assert allowed.status_code == 200
            handler.assert_awaited_once()

    async def test_webhook_unset_secret_fails_closed_in_multi_user(self, client_factory):
        handler = AsyncMock(return_value="ok")
        with (
            patch("app.config.settings.telegram_webhook_secret", SecretStr("")),
            patch("app.config.settings.single_user_mode", False),
            patch.object(telegram_service, "handle_telegram_webhook", handler),
        ):
            resp = await client_factory().post(
                "/api/notifications/telegram/webhook",
                json={"message": {}},
                headers={"x-telegram-bot-api-secret-token": ""},
            )
            assert resp.status_code == 403
            assert resp.json() == {"detail": "Invalid webhook secret"}
            handler.assert_not_awaited()

    async def test_relinking_resets_a_verified_link(self, make_user, db_session):
        user = await make_user()
        first = await telegram_service.generate_link_token(db_session, user.id)
        await telegram_service.verify_link(db_session, first, 7, "me")
        second = await telegram_service.generate_link_token(db_session, user.id)
        link = await telegram_service.get_link(db_session, user.id)
        assert second != first and link.verified is False and link.chat_id is None
        assert await telegram_service.unlink(db_session, user.id) is True
        assert await telegram_service.unlink(db_session, user.id) is False

    async def test_send_message_requires_configuration(self):
        with patch("app.config.settings.telegram_bot_token", SecretStr("")):
            assert await telegram_service.send_telegram_message(1, "x") is False
        with (
            patch("app.config.settings.telegram_bot_token", SecretStr("1:x")),
            patch("aiogram.Bot") as bot_cls,
        ):
            bot = bot_cls.return_value
            bot.send_message = AsyncMock()
            bot.session.close = AsyncMock()
            assert await telegram_service.send_telegram_message(5, "hi") is True
            bot.send_message.assert_awaited_once_with(chat_id=5, text="hi", parse_mode="HTML")
            bot.send_message.side_effect = RuntimeError("blocked")
            assert await telegram_service.send_telegram_message(5, "hi") is False

    async def test_message_templates_render(self):
        with patch.object(
            telegram_service, "send_telegram_message", AsyncMock(return_value=True)
        ) as send:
            await telegram_service.send_pipeline_complete(1, "f.pdf", "NET101", 3, 4, 5)
            await telegram_service.send_exam_reminder(1, "Midterm", "NET101", "2030-01-01")
            await telegram_service.send_cards_due(1, 9)
            await telegram_service.send_weekly_digest(1, 1, 2, 3, 4, 5)
            await telegram_service.send_weekly_digest(1, 1, 2, 3, 4, 0)
        texts = [c.args[1] for c in send.await_args_list]
        assert "f.pdf" in texts[0] and "Midterm" in texts[1] and "<b>9</b>" in texts[2]
        assert "flashcards due" in texts[3] and "all caught up" in texts[4]


class TestPush:
    async def test_subscribe_is_upsert_and_unsubscribe_is_owner_scoped(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        body = {"endpoint": "https://push.example/abc", "p256dh": "key1", "auth": "auth1"}
        client = client_factory(alice)
        first = await client.post("/api/notifications/push/subscribe", json=body)
        second = await client.post(
            "/api/notifications/push/subscribe", json={**body, "p256dh": "key2"}
        )
        assert first.json()["id"] == second.json()["id"]
        subs = (
            (
                await db_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == alice.id)
                )
            )
            .scalars()
            .all()
        )
        assert [s.p256dh for s in subs] == ["key2"]

        # Bob cannot remove Alice's subscription by guessing the endpoint.
        denied = await client_factory(bob).request(
            "DELETE", "/api/notifications/push/unsubscribe", json={"endpoint": body["endpoint"]}
        )
        assert denied.status_code == 404
        ok = await client.request(
            "DELETE", "/api/notifications/push/unsubscribe", json={"endpoint": body["endpoint"]}
        )
        assert ok.status_code == 200

    async def test_vapid_key_endpoint(self, client_factory):
        with patch("app.config.settings.vapid_public_key", ""):
            assert (
                await client_factory().get("/api/notifications/push/vapid-key")
            ).status_code == 400
        with patch("app.config.settings.vapid_public_key", "PUBKEY"):
            resp = await client_factory().get("/api/notifications/push/vapid-key")
        assert resp.json() == {"public_key": "PUBKEY"}

    async def test_send_push_counts_successes_and_prunes_stale_subscriptions(
        self, make_user, db_session
    ):
        from pywebpush import WebPushException

        user = await make_user()
        for name in ("ok", "gone", "flaky"):
            db_session.add(
                PushSubscription(
                    id=name + generate_id()[:6],
                    user_id=user.id,
                    endpoint=f"https://push.example/{name}",
                    p256dh="k",
                    auth="a",
                )
            )
        await db_session.flush()

        def fake_webpush(subscription_info, **_):
            endpoint = subscription_info["endpoint"]
            if endpoint.endswith("gone"):
                raise WebPushException("gone", response=MagicMock(status_code=410))
            if endpoint.endswith("flaky"):
                raise WebPushException("boom", response=MagicMock(status_code=500))

        with (
            patch("app.config.settings.vapid_private_key", SecretStr("private")),
            patch("pywebpush.webpush", side_effect=fake_webpush),
        ):
            sent = await push_service.send_push_notification(db_session, user.id, "t", "b")
        assert sent == 1
        remaining = {
            s.endpoint.rsplit("/", 1)[1]
            for s in (
                await db_session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == user.id)
                )
            ).scalars()
        }
        assert remaining == {"ok", "flaky"}  # only the 410 was pruned

    async def test_send_push_without_keys_or_subscriptions_is_zero(self, make_user, db_session):
        user = await make_user()
        with patch("app.config.settings.vapid_private_key", SecretStr("")):
            assert await push_service.send_push_notification(db_session, user.id, "t", "b") == 0
        with patch("app.config.settings.vapid_private_key", SecretStr("private")):
            assert await push_service.send_push_notification(db_session, user.id, "t", "b") == 0


class TestTestNotificationEndpoint:
    async def test_email_channel(self, client_factory, make_user):
        client = client_factory(await make_user())
        with patch.object(email_service, "send_email", AsyncMock(return_value=True)) as send:
            ok = await client.post("/api/notifications/test", json={"channel": "email"})
        assert ok.json()["success"] is True
        assert send.await_args.args[1] == "StudyAIO: Test Notification"
        with patch.object(email_service, "send_email", AsyncMock(return_value=False)):
            failed = await client.post("/api/notifications/test", json={"channel": "email"})
        assert failed.json()["success"] is False

    async def test_telegram_channel_needs_a_verified_link(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        client = client_factory(user)
        assert (
            await client.post("/api/notifications/test", json={"channel": "telegram"})
        ).status_code == 400
        token = await telegram_service.generate_link_token(db_session, user.id)
        await telegram_service.verify_link(db_session, token, 99)
        with patch.object(
            telegram_service, "send_telegram_message", AsyncMock(return_value=True)
        ) as send:
            resp = await client.post("/api/notifications/test", json={"channel": "telegram"})
        assert resp.json()["success"] is True and send.await_args.args[0] == 99

    async def test_push_channel_and_unknown_channel(self, client_factory, make_user):
        client = client_factory(await make_user())
        none = await client.post("/api/notifications/test", json={"channel": "push"})
        assert none.json()["success"] is False and "No active push" in none.json()["message"]
        assert (
            await client.post("/api/notifications/test", json={"channel": "sms"})
        ).status_code == 400


class TestDispatch:
    @pytest.fixture(autouse=True)
    def _notifications_on(self):
        with patch("app.config.settings.notifications_enabled", True):
            yield

    async def _enable(self, db_session, user, channels, event="cards_due"):
        for channel in channels:
            db_session.add(
                NotificationPreference(
                    id=generate_id(),
                    user_id=user.id,
                    channel=channel,
                    event_type=event,
                    enabled=True,
                )
            )
        await db_session.flush()

    async def test_only_enabled_channels_fire(self, make_user, db_session):
        user = await make_user()
        await self._enable(db_session, user, ["email", "push"])
        with (
            patch.object(email_service, "send_cards_due", AsyncMock(return_value=True)) as email,
            patch.object(telegram_service, "send_cards_due", AsyncMock(return_value=True)) as tg,
            patch.object(push_service, "send_push_notification", AsyncMock(return_value=2)) as push,
        ):
            result = await notification_service.notify_cards_due(db_session, user.id, 5)
        assert result == {"email": True, "push": True}
        email.assert_awaited_once_with(user.email, due_count=5)
        tg.assert_not_awaited()
        assert "5 flashcards" in push.await_args.kwargs["body"]

    async def test_disabled_or_unknown_events_send_nothing(self, make_user, db_session):
        user = await make_user()
        assert await notification_service.notify_cards_due(db_session, user.id, 1) == {}
        assert await notification_service.notify(db_session, user.id, "nonsense") == {}
        await self._enable(db_session, user, ["email"])
        with patch("app.config.settings.notifications_enabled", False):
            assert await notification_service.notify_cards_due(db_session, user.id, 1) == {}

    async def test_sender_failure_is_isolated_per_channel(self, make_user, db_session):
        user = await make_user()
        await self._enable(db_session, user, ["email", "telegram", "push"])
        with (
            patch.object(
                email_service, "send_cards_due", AsyncMock(side_effect=RuntimeError("smtp"))
            ),
            patch.object(push_service, "send_push_notification", AsyncMock(return_value=0)),
        ):
            result = await notification_service.notify_cards_due(db_session, user.id, 1)
        assert result == {"email": False, "telegram": False, "push": False}

    async def test_telegram_goes_to_the_users_own_chat(self, make_user, db_session):
        user = await make_user()
        await self._enable(db_session, user, ["telegram"], event="exam_reminder")
        token = await telegram_service.generate_link_token(db_session, user.id)
        await telegram_service.verify_link(db_session, token, 777)
        with patch.object(
            telegram_service, "send_exam_reminder", AsyncMock(return_value=True)
        ) as send:
            result = await notification_service.notify_exam_reminder(
                db_session, user.id, "Final", "NET101", "2030-01-01"
            )
        assert result == {"telegram": True}
        assert send.await_args.args[0] == 777

    async def test_pipeline_complete_writes_inbox_and_review_variant(self, make_user, db_session):
        user = await make_user()
        await notification_service.notify_pipeline_complete(
            db_session, user.id, "w3.pdf", "NET101", 3, 2, 2
        )
        await notification_service.notify_review_created(db_session, user.id, "w3.pdf", "NET101", 3)
        inbox = (
            (await db_session.execute(select(Notification).where(Notification.user_id == user.id)))
            .scalars()
            .all()
        )
        assert [n.kind for n in inbox] == ["pipeline"]
        assert inbox[0].href == "/courses/NET101/weeks/3"

    def test_push_body_variants(self):
        build = notification_service._build_push_body
        assert "w.pdf" in build("pipeline_complete", {"filename": "w.pdf"})
        assert "1 flashcard " in build("cards_due", {"due_count": 1})
        assert "3 flashcards" in build("cards_due", {"due_count": 3})
        assert "Midterm" in build("exam_reminder", {"exam_title": "Midterm", "exam_date": "x"})
        assert "digest" in build("weekly_digest", {})
        assert "New other notification" in build("other", {})


@contextmanager
def frozen_clock(instant: datetime):
    """Pin the clock the scheduled jobs read (ADR 0006: sends happen at local 08:00)."""
    with (
        patch("app.core.clock.utc_now", return_value=instant),
        patch.object(notification_tasks, "utc_now", return_value=instant),
    ):
        yield


class TestScheduledJobs:
    async def _course(self, owner_id, code="JOB1"):
        async with async_session_factory() as session:
            course = Course(id=generate_id(), code=code, name=code, user_id=owner_id)
            session.add(course)
            await session.commit()
            return course.id

    async def test_deadline_reminders_are_scoped_deduped_and_windowed(self, committed_user):
        # 08:00Z on the real UTC date: created_at (DB clock) falls inside this local day.
        now = datetime.now(UTC)
        frozen = now.replace(hour=8, minute=0, second=0, microsecond=0)
        owner = await committed_user()
        course_id = await self._course(owner.id)
        async with async_session_factory() as session:
            for title, offset in (
                ("Due today", 0),
                ("Due soon", 3),
                ("Far away", 30),
                ("Past", -2),
            ):
                session.add(
                    Deadline(
                        id=generate_id(),
                        course_id=course_id,
                        title=title,
                        due_date=frozen.date() + timedelta(days=offset),
                        deadline_type="assignment",
                    )
                )
            await session.commit()

        with frozen_clock(frozen):
            emitted = await notification_tasks._send_deadline_reminders()
        assert emitted >= 2
        async with async_session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(Notification).where(Notification.user_id == owner.id)
                    )
                )
                .scalars()
                .all()
            )
        assert sorted(n.title for n in rows) == ["Due soon due in 3 days", "Due today due today"]
        assert all(n.kind == "deadline" and n.href.startswith("/courses/JOB1/ops") for n in rows)

        with frozen_clock(frozen + timedelta(minutes=30)):  # same hour: no duplicates
            await notification_tasks._send_deadline_reminders()
        async with async_session_factory() as session:
            again = (
                (
                    await session.execute(
                        select(Notification).where(Notification.user_id == owner.id)
                    )
                )
                .scalars()
                .all()
            )
        assert len(again) == 2

        with frozen_clock(frozen.replace(hour=14)):  # not 08:00 local: nothing is sent
            assert await notification_tasks._send_deadline_reminders() == 0

    async def _opted_in_with_due_card(self, owner_id, code, tz=None):
        from app.models.flashcard import Flashcard

        course_id = await self._course(owner_id, code=code)
        async with async_session_factory() as session:
            if tz:
                session.add(
                    UserSettings(id=generate_id(), user_id=owner_id, settings_json={}, timezone=tz)
                )
            session.add(
                NotificationPreference(
                    id=generate_id(),
                    user_id=owner_id,
                    channel="email",
                    event_type="cards_due",
                    enabled=True,
                )
            )
            artifact_id = generate_id()
            session.add(
                LectureArtifact(
                    id=artifact_id,
                    user_id=owner_id,
                    course_id=course_id,
                    week=1,
                    title=f"{code} week 1",
                    original_filename=f"{code}.pdf",
                    file_path=f"uploads/{artifact_id}_{code}.pdf",
                    file_type="pdf",
                    sha256=generate_id().replace("-", "") * 2,
                    file_size_bytes=1,
                    status="processed",
                )
            )
            await session.flush()
            session.add(
                Flashcard(
                    id=generate_id(),
                    course_id=course_id,
                    week=1,
                    front="f",
                    back="b",
                    tags=[],
                    source_artifact_id=artifact_id,
                    source_page_ref=1,
                )
            )
            await session.commit()

    async def _run_daily(self, instant, owner_id):
        with (
            frozen_clock(instant),
            patch.object(
                notification_service, "notify_cards_due", AsyncMock(return_value={})
            ) as notify,
        ):
            await notification_tasks._send_daily_reminders()
        return [c for c in notify.await_args_list if c.args[1] == owner_id]

    async def test_daily_reminder_reaches_opted_in_user_with_due_cards(self, committed_user):
        owner = await committed_user()
        await self._opted_in_with_due_card(owner.id, "JOB2")
        calls = await self._run_daily(datetime(2026, 10, 9, 8, 0, tzinfo=UTC), owner.id)
        assert len(calls) == 1 and calls[0].args[2] == 1

    async def test_daily_reminder_is_not_resent_within_the_same_local_day(self, committed_user):
        owner = await committed_user()
        await self._opted_in_with_due_card(owner.id, "JOB2B")
        first = await self._run_daily(datetime(2026, 10, 9, 8, 0, tzinfo=UTC), owner.id)
        second = await self._run_daily(datetime(2026, 10, 9, 8, 45, tzinfo=UTC), owner.id)
        assert len(first) == 1
        assert second == []

    async def test_daily_reminder_waits_for_the_owners_local_08(self, committed_user):
        owner = await committed_user()
        await self._opted_in_with_due_card(owner.id, "JOB2C", tz="Asia/Tokyo")
        # 08:00Z is 17:00 in Tokyo: not yet (nor any longer) their send time.
        assert await self._run_daily(datetime(2026, 10, 10, 8, 0, tzinfo=UTC), owner.id) == []
        # 23:00Z the previous UTC day is 08:00 on the 11th in Tokyo.
        calls = await self._run_daily(datetime(2026, 10, 10, 23, 0, tzinfo=UTC), owner.id)
        assert len(calls) == 1 and calls[0].args[2] == 1

    async def test_weekly_digest_reaches_opted_in_user(self, committed_user):
        owner = await committed_user()
        async with async_session_factory() as session:
            session.add(
                NotificationPreference(
                    id=generate_id(),
                    user_id=owner.id,
                    channel="email",
                    event_type="weekly_digest",
                    enabled=True,
                )
            )
            await session.commit()
        sunday = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)

        async def run(instant):
            with (
                frozen_clock(instant),
                patch.object(notification_service, "notify", AsyncMock(return_value={})) as notify,
            ):
                await notification_tasks._send_weekly_digest()
            return [c for c in notify.await_args_list if c.args[1] == owner.id]

        assert len(await run(sunday)) == 1
        assert await run(sunday.replace(minute=40)) == []  # same hour: no duplicate
        assert await run(sunday - timedelta(days=1)) == []  # Saturday: not digest day

    async def test_jobs_return_zero_when_nobody_opted_in(self):
        async with async_session_factory() as session:
            enabled = (
                await session.execute(
                    select(NotificationPreference.id).where(
                        NotificationPreference.enabled.is_(True)
                    )
                )
            ).first()
        if enabled is None:
            assert await notification_tasks._send_daily_reminders() == 0
            assert await notification_tasks._send_weekly_digest() == 0

    def test_celery_wrappers_report_status(self):
        with patch.object(notification_tasks, "run_async", return_value=3):
            for task in (
                notification_tasks.send_deadline_reminders,
                notification_tasks.send_daily_reminders,
                notification_tasks.send_weekly_digest,
            ):
                expected = {"status": "completed", "notified": 3}
                if task is notification_tasks.send_daily_reminders:
                    expected["nudged"] = 3  # GL#15: study nudges ride the daily task
                assert task.run() == expected
        with patch.object(notification_tasks, "run_async", side_effect=RuntimeError("db down")):
            assert notification_tasks.send_daily_reminders.run() == {
                "status": "failed",
                "notified": 0,
                "nudged": 0,
            }
