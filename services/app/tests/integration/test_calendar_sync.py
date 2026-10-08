"""Google Calendar sync and .ics export, against real rows with a fake Google client.

The Google API client is replaced by a small recording fake. Everything else
(owner scoping of syncs, deadline/exam selection, change detection by hash,
mapping rows) runs against Postgres.
"""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.exceptions import CalendarSyncError
from app.core.utils import generate_id
from app.models.calendar_event import CalendarEvent
from app.models.calendar_sync import CalendarSync
from app.models.deadline import Deadline
from app.models.exam import Exam
from app.services import calendar_service, gcal_service

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


class FakeGoogle:
    """Just enough of the Google Calendar v3 resource surface, recording calls."""

    def __init__(self, items=None, next_token="tok-2", fail_list=False):
        self.items = items or []
        self.next_token = next_token
        self.fail_list = fail_list
        self.inserted: list[dict] = []
        self.updated: list[tuple[str, dict]] = []
        self.list_kwargs: list[dict] = []

    def events(self):
        outer = self

        class Events:
            def insert(self, calendarId, body):  # noqa: N803
                outer.inserted.append(body)
                return SimpleNamespace(execute=lambda: {"id": f"g-{len(outer.inserted)}"})

            def update(self, calendarId, eventId, body):  # noqa: N803
                outer.updated.append((eventId, body))
                return SimpleNamespace(execute=lambda: {})

            def list(self, **kwargs):
                outer.list_kwargs.append(kwargs)

                def execute():
                    if outer.fail_list:
                        raise RuntimeError("410 Gone")
                    return {"items": outer.items, "nextSyncToken": outer.next_token}

                return SimpleNamespace(execute=execute)

        return Events()


def _patch_google(fake):
    creds = SimpleNamespace(expired=False, refresh_token="r", token="t")
    return patch.object(gcal_service, "_build_gcal_service", return_value=(fake, creds))


async def _sync(db_session, user, direction="push") -> CalendarSync:
    sync = CalendarSync(
        id=generate_id(),
        user_id=user.id,
        google_calendar_id="cal-1",
        sync_direction=direction,
        access_token="access",
        refresh_token="refresh",
    )
    db_session.add(sync)
    await db_session.flush()
    return sync


async def _with_content(db_session, user, code="CAL1"):
    seeded = await seed_course(db_session, user.id, code=code)
    deadline = Deadline(
        id=generate_id(),
        course_id=seeded.course.id,
        title="Lab",
        due_date=date.today() + timedelta(days=5),
        deadline_type="assignment",
    )
    exam = Exam(
        id=generate_id(),
        user_id=user.id,
        course_id=seeded.course.id,
        title="Midterm",
        exam_date=datetime.now(UTC) + timedelta(days=9),
        weeks_scope=[3],
        status="active",
    )
    db_session.add_all([deadline, exam])
    await db_session.flush()
    return seeded, deadline, exam


class TestPush:
    async def test_push_creates_then_skips_unchanged_then_updates_changed(
        self, make_user, db_session
    ):
        user = await make_user()
        sync = await _sync(db_session, user)
        _, deadline, exam = await _with_content(db_session, user)
        fake = FakeGoogle()

        with _patch_google(fake):
            first = await gcal_service.push_events(db_session, user.id, sync.id)
            second = await gcal_service.push_events(db_session, user.id, sync.id)
            deadline.title = "Lab (renamed)"
            await db_session.flush()
            third = await gcal_service.push_events(db_session, user.id, sync.id)
        assert (first, second, third) == (2, 0, 1)
        assert {b["summary"] for b in fake.inserted} == {"[ASSIGNMENT] Lab", "[EXAM] Midterm"}
        assert fake.updated[0][1]["summary"] == "[ASSIGNMENT] Lab (renamed)"
        mapped = (
            (
                await db_session.execute(
                    select(CalendarEvent).where(CalendarEvent.calendar_sync_id == sync.id)
                )
            )
            .scalars()
            .all()
        )
        assert {(m.entity_type, m.entity_id) for m in mapped} == {
            ("deadline", deadline.id),
            ("exam", exam.id),
        }
        await db_session.refresh(sync)
        assert sync.last_synced_at is not None

    async def test_push_sends_only_the_owners_content(self, make_user, db_session):
        owner, other = await make_user(), await make_user()
        sync = await _sync(db_session, owner)
        await _with_content(db_session, owner, code="CAL1")
        await _with_content(db_session, other, code="CAL2")
        fake = FakeGoogle()
        with _patch_google(fake):
            assert await gcal_service.push_events(db_session, owner.id, sync.id) == 2
        assert len(fake.inserted) == 2

    async def test_another_users_sync_cannot_be_driven(self, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        sync = await _sync(db_session, owner)
        for call in (
            gcal_service.push_events,
            gcal_service.pull_events,
            gcal_service.sync_calendar,
        ):
            with pytest.raises(CalendarSyncError):
                await call(db_session, stranger.id, sync.id)

    async def test_google_failures_do_not_abort_the_push(self, make_user, db_session):
        user = await make_user()
        sync = await _sync(db_session, user)
        await _with_content(db_session, user)

        class Broken(FakeGoogle):
            def events(self):
                class E:
                    def insert(self, **_):
                        raise RuntimeError("quota")

                return E()

        with _patch_google(Broken()):
            assert await gcal_service.push_events(db_session, user.id, sync.id) == 0
        rows = (
            await db_session.execute(
                select(CalendarEvent).where(CalendarEvent.calendar_sync_id == sync.id)
            )
        ).first()
        assert rows is None  # nothing recorded as synced when Google refused


class TestPull:
    async def test_pull_imports_new_events_once_and_stores_sync_token(self, make_user, db_session):
        user = await make_user()
        sync = await _sync(db_session, user, direction="pull")
        items = [
            {"id": "e1", "summary": "Lecture", "start": {"date": "2030-01-01"}},
            {"id": "e2", "summary": "Seminar", "start": {"dateTime": "2030-01-02T10:00:00Z"}},
            {"summary": "no id"},
        ]
        fake = FakeGoogle(items=items)
        with _patch_google(fake):
            first = await gcal_service.pull_events(db_session, user.id, sync.id)
            second = await gcal_service.pull_events(db_session, user.id, sync.id)
        assert (first, second) == (2, 0)
        await db_session.refresh(sync)
        assert sync.sync_token == "tok-2"
        assert fake.list_kwargs[1]["syncToken"] == "tok-2"  # incremental after the first pull

    async def test_first_pull_sends_a_valid_rfc3339_time_min(self, make_user, db_session):
        user = await make_user()
        sync = await _sync(db_session, user, direction="pull")
        fake = FakeGoogle()
        with _patch_google(fake):
            await gcal_service.pull_events(db_session, user.id, sync.id)
        time_min = fake.list_kwargs[0]["timeMin"]
        assert "+00:00Z" not in time_min
        datetime.fromisoformat(time_min.replace("Z", "+00:00"))

    async def test_expired_sync_token_is_cleared_for_a_full_resync(self, make_user, db_session):
        user = await make_user()
        sync = await _sync(db_session, user, direction="pull")
        sync.sync_token = "stale"
        await db_session.flush()
        with _patch_google(FakeGoogle(fail_list=True)):
            with pytest.raises(CalendarSyncError):
                await gcal_service.pull_events(db_session, user.id, sync.id)
        await db_session.refresh(sync)
        assert sync.sync_token is None


class TestOrchestration:
    async def test_direction_selects_push_pull_or_both(self, make_user, db_session):
        user = await make_user()
        await _with_content(db_session, user)
        results = {}
        for direction in ("push", "pull", "bidirectional"):
            sync = await _sync(db_session, user, direction=direction)
            with _patch_google(FakeGoogle(items=[{"id": f"x-{direction}", "summary": "s"}])):
                results[direction] = await gcal_service.sync_calendar(db_session, user.id, sync.id)
        assert results["push"] == {"pushed": 2, "pulled": 0}
        assert results["pull"] == {"pushed": 0, "pulled": 1}
        assert results["bidirectional"]["pulled"] == 1

    async def test_webhook_pulls_for_known_channel_only(self, make_user, db_session):
        user = await make_user()
        sync = await _sync(db_session, user, direction="pull")
        fake = FakeGoogle(items=[{"id": "w1", "summary": "pushed by google"}])
        with _patch_google(fake):
            await gcal_service.handle_gcal_webhook(db_session, sync.id, "res")
            await gcal_service.handle_gcal_webhook(db_session, "unknown-channel", "res")
        assert len(fake.list_kwargs) == 1


class TestCalendarApi:
    async def test_connect_status_sync_disconnect(self, client_factory, make_user, db_session):
        user = await make_user()
        client = client_factory(user)
        creds = SimpleNamespace(token="tok", refresh_token="ref")
        flow = MagicMock()
        flow.credentials = creds
        service = MagicMock()
        service.calendars.return_value.insert.return_value.execute.return_value = {
            "id": "created-cal"
        }

        with (
            patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=flow),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            connected = await client.post("/api/calendar/connect", json={"auth_code": "code"})
        assert connected.status_code == 200, connected.text
        sync_id = connected.json()["sync_id"]
        flow.fetch_token.assert_called_once_with(code="code")
        stored = await db_session.get(CalendarSync, sync_id)
        assert stored.user_id == user.id and stored.google_calendar_id == "created-cal"

        status = (await client.get("/api/calendar/status")).json()["calendars"]
        assert [c["id"] for c in status] == [sync_id] and status[0]["event_count"] == 0

        await _with_content(db_session, user)
        with _patch_google(FakeGoogle()):
            synced = await client.post("/api/calendar/sync")
        assert synced.json() == {"pushed": 2, "pulled": 0}
        assert (await client.get("/api/calendar/status")).json()["calendars"][0]["event_count"] == 2

        with patch("httpx.AsyncClient.post"):
            gone = await client.delete(f"/api/calendar/disconnect/{sync_id}")
        assert gone.json() == {"detail": "Calendar disconnected"}
        assert (await client.get("/api/calendar/status")).json()["calendars"] == []
        again = await client.delete(f"/api/calendar/disconnect/{sync_id}")
        assert again.json() == {"detail": "Calendar sync not found"}

    async def test_connect_failure_is_reported(self, client_factory, make_user):
        client = client_factory(await make_user())
        with patch(
            "google_auth_oauthlib.flow.Flow.from_client_config", side_effect=RuntimeError("bad")
        ):
            resp = await client.post("/api/calendar/connect", json={"auth_code": "x"})
        assert resp.status_code >= 400

    async def test_calendar_syncs_are_owner_scoped(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        sync = await _sync(db_session, owner)
        other = client_factory(stranger)
        assert (await other.get("/api/calendar/status")).json()["calendars"] == []
        assert (await other.delete(f"/api/calendar/disconnect/{sync.id}")).json() == {
            "detail": "Calendar sync not found"
        }
        assert await db_session.get(CalendarSync, sync.id) is not None
        with _patch_google(FakeGoogle()) as _:
            assert (await other.post("/api/calendar/sync")).json() == {"pushed": 0, "pulled": 0}

    async def test_webhook_requires_a_channel_header(self, client_factory, make_user, db_session):
        client = client_factory()
        assert (await client.post("/api/calendar/webhook")).status_code == 400
        user = await make_user()
        sync = await _sync(db_session, user, direction="pull")
        with _patch_google(FakeGoogle()):
            ok = await client.post(
                "/api/calendar/webhook",
                headers={"x-goog-channel-id": sync.id, "x-goog-resource-id": "r"},
            )
        assert ok.status_code == 200


class TestIcsAndTaskPlan:
    async def test_ics_contains_confirmed_and_upcoming_deadlines(self, make_user, db_session):
        user = await make_user()
        seeded, deadline, _ = await _with_content(db_session, user)
        result = await calendar_service.generate_ics(db_session, "CAL1", user_id=user.id)
        assert result is not None
        buf, filename = result
        text = buf.read().decode()
        assert filename.endswith(".ics") and "SUMMARY" in text and "Lab" in text
        assert await calendar_service.generate_ics(db_session, "NOPE", user_id=user.id) is None
        stranger = await make_user()
        assert await calendar_service.generate_ics(db_session, "CAL1", user_id=stranger.id) is None

    async def test_task_plan_markdown(self, make_user, db_session):
        user = await make_user()
        await _with_content(db_session, user)
        result = await calendar_service.generate_task_plan_md(db_session, "CAL1", user_id=user.id)
        assert result is not None
        buf, filename = result
        text = buf.read().decode()
        assert filename.endswith(".md") and "CAL1" in text and "Lab" in text
