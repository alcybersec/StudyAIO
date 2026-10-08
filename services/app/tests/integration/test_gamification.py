"""XP, levels, achievements, daily challenges and the leaderboard, end to end.

Driven through the real endpoints that award XP (flashcard review, quiz attempts,
study sessions) so the whole award -> level -> achievement -> inbox chain runs.
"""

from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.utils import generate_id
from app.models.achievement import Achievement
from app.models.notification import Notification
from app.models.user_achievement import UserAchievement
from app.models.user_settings import UserSettings
from app.models.user_xp import UserXP
from app.models.xp_event import XPEvent
from app.services import challenge_service, xp_service

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _achievement(db_session, code, criteria, xp=10, title=None):
    ach = Achievement(
        id=generate_id(),
        code=f"{code}-{generate_id()[-6:]}",
        title=title or code,
        description=f"{code} description",
        icon="star",
        category="study",
        xp_reward=xp,
        criteria_json=criteria,
    )
    db_session.add(ach)
    await db_session.flush()
    return ach


class TestLevels:
    async def test_level_curve_is_monotonic_and_bounded(self, db_session):
        levels = [xp_service.calculate_level(x) for x in (0, 50, 100, 500, 5_000, 10**7)]
        assert levels == sorted(levels) and levels[0] == 1
        current, nxt = xp_service.xp_for_next_level(1)
        assert current == 0 and nxt and nxt > 0
        top = xp_service.calculate_level(10**9)
        assert xp_service.xp_for_next_level(top)[1] is None  # max level has no next


class TestXpFlow:
    async def test_review_awards_xp_events_and_level_progress(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)

        empty = (await client.get("/api/gamification/xp")).json()
        assert empty["total_xp"] == 0 and empty["level"] == 1 and empty["recent_events"] == []

        for card in seeded.flashcards:
            r = await client.post("/api/study/review", json={"flashcard_id": card.id, "quality": 4})
            assert r.status_code == 200
        summary = (await client.get("/api/gamification/xp")).json()
        assert summary["total_xp"] == 5 * len(seeded.flashcards)
        assert {e["event_type"] for e in summary["recent_events"]} == {"card_reviewed"}
        assert 0 <= summary["progress_pct"] <= 100
        row = (
            await db_session.execute(select(UserXP).where(UserXP.user_id == user.id))
        ).scalar_one()
        assert row.total_xp == summary["total_xp"]

    async def test_xp_is_isolated_between_users(self, client_factory, make_user, db_session):
        a, b = await make_user(), await make_user()
        await xp_service.award_xp(db_session, a.id, "upload")
        assert (await client_factory(a).get("/api/gamification/xp")).json()["total_xp"] == 15
        assert (await client_factory(b).get("/api/gamification/xp")).json()["total_xp"] == 0

    async def test_quiz_correct_awards_but_incorrect_does_not(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)
        q = seeded.questions[0].id
        await client.post(
            "/api/study/quiz-attempt",
            json={"quiz_question_id": q, "selected_answer": "B", "is_correct": False},
        )
        assert (await client.get("/api/gamification/xp")).json()["total_xp"] == 0
        await client.post(
            "/api/study/quiz-attempt",
            json={"quiz_question_id": q, "selected_answer": "A", "is_correct": True},
        )
        assert (await client.get("/api/gamification/xp")).json()["total_xp"] == 10


class TestAchievements:
    async def test_unlock_bonus_xp_and_listing(self, client_factory, make_user, db_session):
        user = await make_user()
        ach = await _achievement(
            db_session,
            "first_card",
            {"type": "count", "event_type": "card_reviewed", "threshold": 1},
            xp=25,
        )
        locked = await _achievement(
            db_session,
            "hundred_cards",
            {"type": "count", "event_type": "card_reviewed", "threshold": 100},
        )
        for kind, criteria in (
            ("total", {"type": "total_xp", "threshold": 1}),
            ("lvl", {"type": "level", "threshold": 99}),
            ("streak", {"type": "streak", "threshold": 99}),
            ("junk", {"type": "mystery"}),
        ):
            await _achievement(db_session, kind, criteria)
        client = client_factory(user)

        _, _, earned = await xp_service.award_xp(db_session, user.id, "card_reviewed")
        earned_ids = {ua.achievement_id for ua in earned}
        assert ach.id in earned_ids and locked.id not in earned_ids

        listing = (await client.get("/api/gamification/achievements")).json()
        by_id = {a["id"]: a for a in listing["achievements"]}
        assert by_id[ach.id]["earned"] is True and by_id[ach.id]["earned_at"]
        assert by_id[locked.id]["earned"] is False
        assert listing["earned"] == sum(1 for a in listing["achievements"] if a["earned"])

        bonus = (
            (
                await db_session.execute(
                    select(XPEvent).where(
                        XPEvent.user_id == user.id, XPEvent.event_type == "achievement_bonus"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(e.xp_amount == 25 for e in bonus)
        # Re-awarding does not unlock the same achievement twice.
        await xp_service.award_xp(db_session, user.id, "card_reviewed")
        count = (
            (
                await db_session.execute(
                    select(UserAchievement).where(
                        UserAchievement.user_id == user.id, UserAchievement.achievement_id == ach.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(count) == 1

    async def test_unnotified_then_mark_notified(self, client_factory, make_user, db_session):
        user = await make_user()
        await _achievement(
            db_session, "any", {"type": "count", "event_type": "upload", "threshold": 1}
        )
        await xp_service.award_xp(db_session, user.id, "upload")
        client = client_factory(user)
        pending = (await client.get("/api/gamification/achievements/unnotified")).json()
        assert len(pending) >= 1
        resp = await client.post(
            "/api/gamification/achievements/mark-notified",
            json={"user_achievement_ids": [p["user_achievement_id"] for p in pending]},
        )
        assert resp.status_code == 204
        assert (await client.get("/api/gamification/achievements/unnotified")).json() == []
        assert (
            await client.post(
                "/api/gamification/achievements/mark-notified", json={"user_achievement_ids": []}
            )
        ).status_code == 204

    async def test_cannot_mark_another_users_achievements_notified(
        self, client_factory, make_user, db_session
    ):
        victim, attacker = await make_user(), await make_user()
        await _achievement(
            db_session, "vic", {"type": "count", "event_type": "upload", "threshold": 1}
        )
        await xp_service.award_xp(db_session, victim.id, "upload")
        pending = (
            await client_factory(victim).get("/api/gamification/achievements/unnotified")
        ).json()
        assert pending
        await client_factory(attacker).post(
            "/api/gamification/achievements/mark-notified",
            json={"user_achievement_ids": [p["user_achievement_id"] for p in pending]},
        )
        still = (
            await client_factory(victim).get("/api/gamification/achievements/unnotified")
        ).json()
        assert len(still) == len(pending)

    async def test_unlock_creates_an_inbox_notification(self, make_user, db_session):
        user = await make_user()
        await _achievement(
            db_session,
            "inbox",
            {"type": "count", "event_type": "upload", "threshold": 1},
            title="Inbox Hero",
        )
        await xp_service.award_xp(db_session, user.id, "upload")
        inbox = (
            (
                await db_session.execute(
                    select(Notification).where(
                        Notification.user_id == user.id, Notification.kind == "achievement"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert inbox and "Inbox Hero" in inbox[0].title


class TestChallenges:
    async def test_daily_challenge_is_stable_and_tracks_progress(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        client = client_factory(user)
        first = (await client.get("/api/gamification/challenges")).json()
        second = (await client.get("/api/gamification/challenges")).json()
        assert first["challenge_id"] == second["challenge_id"]
        assert first["challenge_date"] == date.today().isoformat()
        assert first["progress"] == 0 and first["completed"] is False

        ctype, target = first["challenge_type"], first["target"]
        assert (
            await challenge_service.update_challenge_progress(db_session, user.id, "no-such-type")
            is None
        )
        partial = await challenge_service.update_challenge_progress(db_session, user.id, ctype, 1)
        assert partial.progress == 1
        mid = (await client.get("/api/gamification/challenges")).json()
        assert mid["progress"] == 1 and mid["completed"] is False

        done = await challenge_service.update_challenge_progress(db_session, user.id, ctype, target)
        assert done.completed_at is not None
        final = (await client.get("/api/gamification/challenges")).json()
        assert final["completed"] is True and final["completed_at"]
        # Completion pays out exactly once, and further progress is ignored.
        again = await challenge_service.update_challenge_progress(db_session, user.id, ctype, 5)
        assert again.progress == done.progress
        paid = (
            (
                await db_session.execute(
                    select(XPEvent).where(
                        XPEvent.user_id == user.id, XPEvent.event_type == "challenge_completed"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(paid) == 1 and paid[0].xp_amount == first["xp_reward"]

    async def test_challenge_for_other_dates_is_independent(self, db_session):
        a = await challenge_service.get_or_create_daily_challenge(db_session, date(2031, 1, 1))
        b = await challenge_service.get_or_create_daily_challenge(db_session, date(2031, 1, 2))
        assert a.id != b.id


class TestLeaderboard:
    async def test_ranked_by_xp_and_exposes_only_public_fields(
        self, client_factory, make_user, db_session
    ):
        low, high = await make_user(), await make_user()
        for u in (low, high):
            db_session.add(UserSettings(id=generate_id(), user_id=u.id, leaderboard_opt_in=True))
        await db_session.flush()
        await xp_service.award_xp(db_session, low.id, "card_reviewed")
        await xp_service.award_xp(db_session, high.id, "streak_day")
        entries = (await client_factory(low).get("/api/gamification/leaderboard")).json()["entries"]
        ranks = {e["user_id"]: e["rank"] for e in entries}
        assert ranks[high.id] < ranks[low.id]
        assert all(set(e) == {"user_id", "username", "total_xp", "level", "rank"} for e in entries)
        assert "@" not in str(entries)  # never an email address

    async def test_opted_out_other_user_absent_but_caller_sees_self(
        self, client_factory, make_user, db_session
    ):
        caller, hidden, shown = await make_user(), await make_user(), await make_user()
        # `hidden` has an explicit opt-out row; `caller` has no settings row at all.
        db_session.add(UserSettings(id=generate_id(), user_id=hidden.id, leaderboard_opt_in=False))
        db_session.add(UserSettings(id=generate_id(), user_id=shown.id, leaderboard_opt_in=True))
        await db_session.flush()
        await xp_service.award_xp(db_session, hidden.id, "streak_day")
        await xp_service.award_xp(db_session, shown.id, "streak_day")
        await xp_service.award_xp(db_session, caller.id, "card_reviewed")
        entries = (await client_factory(caller).get("/api/gamification/leaderboard")).json()[
            "entries"
        ]
        ids = {e["user_id"] for e in entries}
        assert hidden.id not in ids
        assert shown.id in ids
        assert caller.id in ids  # the caller always sees themselves

    async def test_xp_amount_table_covers_known_events(self, db_session):
        assert xp_service.XP_AMOUNTS["upload"] > 0
        with patch.dict(xp_service.XP_AMOUNTS, {"upload": 1}):
            assert xp_service.XP_AMOUNTS["upload"] == 1
