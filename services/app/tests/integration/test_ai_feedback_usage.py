"""AI feedback votes and usage events against a real database (GL#36, GL#37).

What a mocked session cannot show: the unique constraint really makes a second
vote an update, another tenant's ids are indistinguishable from missing ones and
leave no row, the retention SQL (UTC day arithmetic, week truncation, role
exclusion) agrees with the Python that interprets it, and account deletion
removes both tables' rows.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select

from app.core.clock import utc_today
from app.core.utils import generate_id
from app.models.ai_feedback import AIFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.usage_event import UsageEvent
from app.services import account_service, usage_service

from ._support import make_docx, make_pdf, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def dispatched():
    run = MagicMock(return_value=SimpleNamespace(id="task-1"))
    with patch("app.api.uploads.run_pipeline", run):
        yield run


async def _votes(db_session, user_id, **filters) -> list[AIFeedback]:
    stmt = select(AIFeedback).where(AIFeedback.user_id == user_id)
    for name, value in filters.items():
        stmt = stmt.where(getattr(AIFeedback, name) == value)
    return list((await db_session.execute(stmt)).scalars())


async def _events(db_session, user_id, event: str | None = None) -> list[UsageEvent]:
    stmt = select(UsageEvent).where(UsageEvent.user_id == user_id)
    if event:
        stmt = stmt.where(UsageEvent.event == event)
    return list((await db_session.execute(stmt.order_by(UsageEvent.occurred_at))).scalars())


async def _chat_message(db_session, user_id, course_id=None, role="assistant") -> ChatMessage:
    chat = ChatSession(id=generate_id(), user_id=user_id, course_id=course_id, title="t")
    db_session.add(chat)
    await db_session.flush()
    msg = ChatMessage(id=generate_id(), session_id=chat.id, role=role, content="an answer")
    db_session.add(msg)
    await db_session.flush()
    return msg


class TestCrossUserFeedback:
    """Floor 1: B cannot rate, probe, or even see A's targets."""

    async def test_other_users_targets_are_404_and_leave_no_row(
        self, client_factory, two_tenants, db_session
    ):
        alice, bob, a, _b = two_tenants
        a_msg = await _chat_message(db_session, alice.id, a.course.id)
        targets = {
            "summary": a.summary.id,
            "flashcard": a.flashcards[0].id,
            "quiz_question": a.questions[0].id,
            "chat_message": a_msg.id,
            "answer": a_msg.id,
        }
        bob_client = client_factory(bob)
        for target_type, target_id in targets.items():
            resp = await bob_client.put(
                "/api/feedback",
                json={"target_type": target_type, "target_id": target_id, "rating": -1},
            )
            assert resp.status_code == 404, (target_type, resp.text)
            # Same answer as an id that never existed: no probing for other tenants' ids.
            missing = await bob_client.put(
                "/api/feedback",
                json={"target_type": target_type, "target_id": generate_id(), "rating": -1},
            )
            assert missing.status_code == 404 and missing.json() == resp.json()

        assert await _votes(db_session, bob.id) == []
        assert await _votes(db_session, alice.id) == []
        assert await _events(db_session, bob.id, "feedback_given") == []

    async def test_owner_can_rate_each_target_type(self, client_factory, two_tenants, db_session):
        alice, _bob, a, _b = two_tenants
        a_msg = await _chat_message(db_session, alice.id, a.course.id)
        client = client_factory(alice)
        targets = {
            "summary": a.summary.id,
            "flashcard": a.flashcards[0].id,
            "quiz_question": a.questions[0].id,
            "chat_message": a_msg.id,
            "answer": a_msg.id,
        }
        for target_type, target_id in targets.items():
            resp = await client.put(
                "/api/feedback",
                json={"target_type": target_type, "target_id": target_id, "rating": 1},
            )
            assert resp.status_code == 200, (target_type, resp.text)
            assert resp.json()["course_id"] == a.course.id
        assert len(await _votes(db_session, alice.id)) == len(targets)

    async def test_user_message_is_not_an_answer(self, client_factory, make_user, db_session):
        user = await make_user()
        mine = await _chat_message(db_session, user.id, role="user")
        resp = await client_factory(user).put(
            "/api/feedback",
            json={"target_type": "answer", "target_id": mine.id, "rating": 1},
        )
        assert resp.status_code == 404

    async def test_lookup_and_delete_never_cross_users(
        self, client_factory, two_tenants, db_session
    ):
        alice, bob, a, _b = two_tenants
        await client_factory(alice).put(
            "/api/feedback",
            json={"target_type": "summary", "target_id": a.summary.id, "rating": 1},
        )
        bob_client = client_factory(bob)

        listed = await bob_client.get(
            "/api/feedback/mine",
            params={"target_type": "summary", "target_ids": [a.summary.id]},
        )
        assert listed.status_code == 200 and listed.json() == {"items": []}

        gone = await bob_client.delete(f"/api/feedback/summary/{a.summary.id}")
        assert gone.status_code == 404
        assert len(await _votes(db_session, alice.id)) == 1

    async def test_admin_aggregate_carries_no_user_identifiers(
        self, client_factory, make_user, two_tenants
    ):
        alice, _bob, a, _b = two_tenants
        await client_factory(alice).put(
            "/api/feedback",
            json={
                "target_type": "summary",
                "target_id": a.summary.id,
                "rating": -1,
                "reason": "inaccurate",
                "comment": "wrong about sockets",
            },
        )
        admin = await make_user(role="admin")
        resp = await client_factory(admin).get("/api/admin/ai-feedback")
        assert resp.status_code == 200, resp.text
        assert alice.id not in resp.text and alice.email not in resp.text
        assert resp.json()["by_rating"]["down"] >= 1

        # An ordinary user cannot read the aggregate.
        assert (await client_factory(alice).get("/api/admin/ai-feedback")).status_code == 403


class TestVoteUpsert:
    async def test_second_vote_replaces_the_first_on_the_unique_constraint(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)
        body = {"target_type": "flashcard", "target_id": seeded.flashcards[0].id}

        first = await client.put("/api/feedback", json={**body, "rating": 1})
        assert first.status_code == 200, first.text
        second = await client.put(
            "/api/feedback",
            json={**body, "rating": -1, "reason": "unclear", "comment": "  confusing  "},
        )
        assert second.status_code == 200, second.text

        rows = await _votes(db_session, user.id)
        assert len(rows) == 1
        assert (rows[0].rating, rows[0].reason, rows[0].comment) == (-1, "unclear", "confusing")
        assert rows[0].course_id == seeded.course.id

        # Flipping back to a thumbs-up drops the thumbs-down detail.
        third = await client.put("/api/feedback", json={**body, "rating": 1})
        assert third.status_code == 200
        rows = await _votes(db_session, user.id)
        assert len(rows) == 1 and rows[0].rating == 1 and rows[0].reason is None

    async def test_database_refuses_a_duplicate_row_outright(self, make_user, db_session):
        from sqlalchemy.exc import IntegrityError

        user = await make_user()
        tid = generate_id()
        db_session.add(AIFeedback(user_id=user.id, target_type="summary", target_id=tid, rating=1))
        await db_session.flush()
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                db_session.add(
                    AIFeedback(user_id=user.id, target_type="summary", target_id=tid, rating=-1)
                )
                await db_session.flush()

    async def test_two_users_may_rate_the_same_kind_of_target_independently(
        self, client_factory, two_tenants, db_session
    ):
        alice, bob, a, b = two_tenants
        await client_factory(alice).put(
            "/api/feedback", json={"target_type": "summary", "target_id": a.summary.id, "rating": 1}
        )
        await client_factory(bob).put(
            "/api/feedback",
            json={"target_type": "summary", "target_id": b.summary.id, "rating": -1},
        )
        assert [v.rating for v in await _votes(db_session, alice.id)] == [1]
        assert [v.rating for v in await _votes(db_session, bob.id)] == [-1]

    async def test_delete_removes_only_the_callers_vote(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)
        sid = seeded.summary.id
        await client.put(
            "/api/feedback", json={"target_type": "summary", "target_id": sid, "rating": 1}
        )
        assert (await client.delete(f"/api/feedback/summary/{sid}")).status_code == 204
        assert await _votes(db_session, user.id) == []
        assert (await client.delete(f"/api/feedback/summary/{sid}")).status_code == 404

    @pytest.mark.parametrize(
        "payload",
        [
            {"rating": 0},
            {"rating": 2},
            {"rating": 1, "reason": "inaccurate"},
            {"rating": -1, "reason": "because"},
            {"rating": -1, "comment": "x" * 1001},
        ],
    )
    async def test_invalid_votes_are_422_and_store_nothing(
        self, client_factory, make_user, db_session, payload
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        resp = await client_factory(user).put(
            "/api/feedback",
            json={"target_type": "summary", "target_id": seeded.summary.id, **payload},
        )
        assert resp.status_code == 422, resp.text
        assert await _votes(db_session, user.id) == []

    async def test_mine_returns_only_requested_targets(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)
        for card in seeded.flashcards:
            await client.put(
                "/api/feedback",
                json={"target_type": "flashcard", "target_id": card.id, "rating": 1},
            )
        resp = await client.get(
            "/api/feedback/mine",
            params={"target_type": "flashcard", "target_ids": [seeded.flashcards[0].id]},
        )
        assert [i["target_id"] for i in resp.json()["items"]] == [seeded.flashcards[0].id]


class TestUsageEventEmission:
    async def test_batch_upload_emits_one_event_per_accepted_file_only(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        pdf, docx = make_pdf(), make_docx()
        client = client_factory(user)
        await client.post("/api/uploads", files={"file": ("seen.pdf", pdf, "application/pdf")})
        assert len(await _events(db_session, user.id, "upload_completed")) == 1

        resp = await client.post(
            "/api/uploads/batch",
            files=[
                ("files", ("seen-again.pdf", pdf, "application/pdf")),  # duplicate
                ("files", ("fresh.docx", docx, "application/octet-stream")),  # accepted
                ("files", ("notes.txt", b"x", "text/plain")),  # rejected
                ("files", ("fake.pdf", b"not a pdf", "application/pdf")),  # rejected
            ],
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["succeeded"] == 1
        # 1 from the single upload + 1 accepted batch file; duplicates and errors add none.
        assert len(await _events(db_session, user.id, "upload_completed")) == 2

    async def test_flashcard_review_and_study_session_events_carry_no_content(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)

        card = seeded.flashcards[0]
        assert (
            await client.post("/api/study/review", json={"flashcard_id": card.id, "quality": 4})
        ).status_code == 200
        reviewed = await _events(db_session, user.id, "flashcard_reviewed")
        assert len(reviewed) == 1
        assert reviewed[0].course_id == seeded.course.id
        assert reviewed[0].properties == {"quality": 4}

        exam = await client.post(
            "/api/exams",
            json={
                "course_code": seeded.course.code,
                "title": "Midterm",
                "exam_date": (datetime.now(UTC) + timedelta(days=14)).isoformat(),
                "weeks_scope": [3],
                "target_mastery_pct": 80,
            },
        )
        assert exam.status_code == 201, exam.text
        done = await client.post(
            f"/api/exams/{exam.json()['id']}/sessions",
            json={
                "cards_reviewed": 10,
                "quiz_questions_answered": 4,
                "quiz_correct": 3,
                "duration_seconds": 600,
            },
        )
        assert done.status_code == 201, done.text
        completed = await _events(db_session, user.id, "quiz_completed")
        assert len(completed) == 1
        assert completed[0].properties == {"count": 4, "correct": 3, "duration_seconds": 600}

    async def test_a_foreign_flashcard_review_emits_nothing(
        self, client_factory, two_tenants, db_session
    ):
        _alice, bob, a, _b = two_tenants
        resp = await client_factory(bob).post(
            "/api/study/review", json={"flashcard_id": a.flashcards[0].id, "quality": 3}
        )
        assert resp.status_code == 404
        assert await _events(db_session, bob.id) == []

    async def test_feedback_event_records_rating_and_type_but_never_the_comment(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        await client_factory(user).put(
            "/api/feedback",
            json={
                "target_type": "summary",
                "target_id": seeded.summary.id,
                "rating": -1,
                "reason": "other",
                "comment": "my private grievance",
            },
        )
        (event,) = await _events(db_session, user.id, "feedback_given")
        assert event.properties == {"rating": -1, "target_type": "summary"}
        assert "grievance" not in str(event.properties)

    async def test_client_may_report_views_only(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        other = await make_user()
        other_course = await seed_course(db_session, other.id, code="OTH101")
        client = client_factory(user)

        ok = await client.post(
            "/api/usage-events", json={"event": "summary_viewed", "course_id": seeded.course.id}
        )
        assert ok.status_code == 204
        assert (
            await client.post("/api/usage-events", json={"event": "study_plan_viewed"})
        ).status_code == 204
        for forged in ("quiz_completed", "upload_completed", "made_up"):
            assert (
                await client.post("/api/usage-events", json={"event": forged})
            ).status_code == 422
        assert (
            await client.post(
                "/api/usage-events",
                json={"event": "summary_viewed", "properties": {"text": "lecture"}},
            )
        ).status_code == 422
        # Another tenant's course id is a 404, and records nothing.
        foreign = await client.post(
            "/api/usage-events",
            json={"event": "summary_viewed", "course_id": other_course.course.id},
        )
        assert foreign.status_code == 404
        assert sorted(e.event for e in await _events(db_session, user.id)) == [
            "study_plan_viewed",
            "summary_viewed",
        ]
        assert await _events(db_session, other.id) == []


def _at(day, hour=0, minute=0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


async def _event(db_session, user, when: datetime, event="summary_viewed") -> None:
    db_session.add(UsageEvent(user_id=user.id, event=event, occurred_at=when))
    await db_session.flush()


class TestRetentionReadout:
    """Cohorts are anchored 3 weeks back so D1/D7 are known and D30 is not."""

    @staticmethod
    def _week() -> "object":
        return usage_service.week_start(utc_today()) - timedelta(weeks=3)

    @staticmethod
    def _cohort(readout: dict, week) -> dict:
        (row,) = [c for c in readout["cohorts"] if c["week_start"] == week.isoformat()]
        return row

    async def test_late_utc_day_signup_counts_next_calendar_day_as_d1(self, make_user, db_session):
        wk = self._week()
        sunday = wk + timedelta(days=6)  # last day of the cohort week
        user = await make_user(created_at=_at(sunday, 23, 50))
        await _event(db_session, user, _at(sunday + timedelta(days=1), 0, 5))  # 15 min later

        readout = await usage_service.retention_readout(db_session)

        row = self._cohort(readout, wk)
        # Calendar-day arithmetic: 15 minutes later is already day 1.
        assert (row["signups"], row["d1"], row["d7"], row["d30"]) == (1, 1, 0, None)

    async def test_signup_just_after_midnight_monday_belongs_to_the_next_week(
        self, make_user, db_session
    ):
        wk = self._week()
        before = await make_user(created_at=_at(wk + timedelta(days=6), 23, 59))
        after = await make_user(created_at=_at(wk + timedelta(days=7), 0, 1))
        await _event(db_session, before, _at(wk + timedelta(days=7), 12))
        await _event(db_session, after, _at(wk + timedelta(days=8), 12))

        readout = await usage_service.retention_readout(db_session)

        first, second = self._cohort(readout, wk), self._cohort(readout, wk + timedelta(days=7))
        assert (first["signups"], first["d1"]) == (1, 1)
        assert (second["signups"], second["d1"]) == (1, 1)

    async def test_checkpoints_are_exact_days_not_ranges(self, make_user, db_session):
        wk = self._week()
        day = wk + timedelta(days=1)
        user = await make_user(created_at=_at(day, 10))
        for offset in (0, 2, 7, 8):  # day 0, 2 and 8 are noise; day 7 is the checkpoint
            await _event(db_session, user, _at(day + timedelta(days=offset), 9))

        row = self._cohort(await usage_service.retention_readout(db_session), wk)

        assert (row["d1"], row["d7"]) == (0, 1)

    async def test_a_user_counts_once_however_many_events_that_day(self, make_user, db_session):
        wk = self._week()
        user = await make_user(created_at=_at(wk, 8))
        for hour in (1, 5, 9):
            await _event(db_session, user, _at(wk + timedelta(days=1), hour))

        row = self._cohort(await usage_service.retention_readout(db_session), wk)

        assert row["d1"] == 1

    async def test_admin_and_demo_accounts_are_excluded_everywhere(self, make_user, db_session):
        wk = self._week()
        real = await make_user(created_at=_at(wk, 9))
        await _event(db_session, real, _at(wk + timedelta(days=1), 9), "quiz_completed")
        for role in ("admin", "demo"):
            ghost = await make_user(role=role, created_at=_at(wk, 9))
            await _event(db_session, ghost, _at(wk + timedelta(days=1), 9), "quiz_completed")

        readout = await usage_service.retention_readout(db_session)

        row = self._cohort(readout, wk)
        assert (row["signups"], row["d1"]) == (1, 1)
        feature = [
            f
            for f in readout["features"]
            if f["event"] == "quiz_completed" and f["week_start"] == wk.isoformat()
        ]
        assert [f["active_users"] for f in feature] == [1]

    async def test_unreached_checkpoints_are_null_not_zero(self, make_user, db_session):
        today = utc_today()
        wk = usage_service.week_start(today)
        await make_user(created_at=_at(today, 1))

        row = self._cohort(await usage_service.retention_readout(db_session), wk)

        assert row["signups"] >= 1
        assert (row["d7"], row["d30"]) == (None, None)

    async def test_users_before_the_window_are_not_counted(self, make_user, db_session):
        old = usage_service.week_start(utc_today()) - timedelta(weeks=12)
        user = await make_user(created_at=_at(old, 9))
        await _event(db_session, user, _at(old + timedelta(days=1), 9))

        readout = await usage_service.retention_readout(db_session, weeks=4)

        assert old.isoformat() not in {c["week_start"] for c in readout["cohorts"]}
        assert old.isoformat() not in {f["week_start"] for f in readout["features"]}

    async def test_endpoint_is_admin_only_and_validates_weeks(
        self, client_factory, make_user, db_session
    ):
        wk = self._week()
        member = await make_user(created_at=_at(wk, 9))
        await _event(db_session, member, _at(wk + timedelta(days=1), 9))

        assert (await client_factory(member).get("/api/admin/usage/retention")).status_code == 403
        assert (await client_factory().get("/api/admin/usage/retention")).status_code == 401

        admin_client = client_factory(await make_user(role="admin"))
        resp = await admin_client.get("/api/admin/usage/retention", params={"weeks": 8})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == {"cohorts", "features", "plan_split"}
        row = self._cohort(body, wk)
        assert (row["signups"], row["d1"]) == (1, 1)
        (split,) = [r for r in body["plan_split"] if r["week_start"] == wk.isoformat()]
        assert set(split) == {"week_start", "with_plan", "without_plan"}
        for arm in (split["with_plan"], split["without_plan"]):
            assert set(arm) == {"signups", "d7", "d30"}
        # The member never opened a study plan, so they sit in the without-plan arm.
        assert (split["with_plan"]["signups"], split["without_plan"]["signups"]) == (0, 1)
        assert (
            await admin_client.get("/api/admin/usage/retention", params={"weeks": 0})
        ).status_code == 422
        assert (
            await admin_client.get("/api/admin/usage/retention", params={"weeks": 27})
        ).status_code == 422


class TestAccountDeletion:
    async def test_feedback_and_events_go_with_the_account_and_only_that_account(
        self, client_factory, two_tenants, db_session, storage
    ):
        alice, bob, a, b = two_tenants
        for user, seeded in ((alice, a), (bob, b)):
            client = client_factory(user)
            await client.put(
                "/api/feedback",
                json={
                    "target_type": "summary",
                    "target_id": seeded.summary.id,
                    "rating": -1,
                    "reason": "other",
                    "comment": "free text the user wrote",
                },
            )
            await client.post("/api/usage-events", json={"event": "summary_viewed"})
        assert len(await _votes(db_session, alice.id)) == 1
        assert len(await _events(db_session, alice.id)) == 2  # view + feedback_given

        await account_service.delete_user_account(db_session, alice.id, storage=storage)
        await db_session.flush()

        assert await _votes(db_session, alice.id) == []
        assert await _events(db_session, alice.id) == []
        # Bob's rows are untouched.
        assert len(await _votes(db_session, bob.id)) == 1
        assert len(await _events(db_session, bob.id)) == 2
        total = await db_session.scalar(
            select(func.count()).select_from(AIFeedback).where(AIFeedback.user_id == alice.id)
        )
        assert total == 0
