"""The beta funnel, against real rows (GL#3 follow-on / instrumentation).

`get_beta_funnel` is almost entirely SQL — distinct counts, a GROUP BY/HAVING
over activity days, and a couple of aggregates. A mocked session would assert
that the code calls `execute` and nothing about whether the queries answer the
question, which is the part that can be wrong.

The funnel exists to say where invited testers stop. Its value depends on those
counts being *right*, so they are checked against rows whose expected answer is
obvious by construction.
"""

import secrets
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models.artifact import LectureArtifact
from app.models.invite_code import InviteCode
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.services import admin_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    """Collision-proof suffix — uuid7 is time-prefixed, so its head is not."""
    return secrets.token_hex(5)


async def _user(session, tag: str, *, role: str = "user", verified: bool = False) -> str:
    uid = f"{tag}-user"
    session.add(
        User(
            id=uid,
            email=f"{tag}@example.com",
            username=tag,
            hashed_password="x",
            role=role,
            email_verified=verified,
        )
    )
    await session.flush()
    return uid


async def _artifact(session, tag: str, uid: str, *, status: str) -> None:
    session.add(
        LectureArtifact(
            id=f"{tag}-art",
            user_id=uid,
            original_filename="lecture.pdf",
            file_path=f"uploads/{tag}.pdf",
            file_type="pdf",
            sha256=secrets.token_hex(32),
            file_size_bytes=10,
            status=status,
        )
    )
    await session.flush()


async def _active_days(session, tag: str, uid: str, days: list[int]) -> None:
    """One `usage_records` row per day, which is how the app writes them."""
    for offset in days:
        session.add(
            UsageRecord(
                id=f"{tag}-usage-{offset}",
                user_id=uid,
                record_date=date.today() - timedelta(days=offset),
                uploads_count=1,
            )
        )
    await session.flush()


async def _funnel(session, **kwargs) -> dict:
    return await admin_service.get_beta_funnel(session, **kwargs)


class TestFunnelSteps:
    async def test_a_tester_who_registered_and_stopped(self, db_session):
        """The number the funnel exists to surface."""
        tag = _tag()
        before = await _funnel(db_session)
        await _user(db_session, tag)

        after = await _funnel(db_session)

        assert after["registered"] == before["registered"] + 1
        assert after["uploaded"] == before["uploaded"]
        assert after["stalled_after_registering"] == before["stalled_after_registering"] + 1

    async def test_uploading_advances_the_step(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag)
        await _artifact(db_session, tag, uid, status="ingested")

        after = await _funnel(db_session)

        assert after["uploaded"] == before["uploaded"] + 1
        assert after["processed"] == before["processed"]
        assert after["stalled_after_registering"] == before["stalled_after_registering"]

    async def test_processed_is_distinct_from_uploaded(self, db_session):
        """The gap between them is the pipeline failing people.

        That is a different problem from testers losing interest, and conflating
        the two would send you to fix the wrong thing.
        """
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag)
        await _artifact(db_session, tag, uid, status="processed")

        after = await _funnel(db_session)

        assert after["uploaded"] == before["uploaded"] + 1
        assert after["processed"] == before["processed"] + 1

    async def test_verified_tracks_the_flag(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        await _user(db_session, tag, verified=True)

        after = await _funnel(db_session)

        assert after["verified"] == before["verified"] + 1

    async def test_two_uploads_from_one_user_count_once(self, db_session):
        """`uploaded` counts people, not files — it is a funnel step."""
        tag = _tag()
        uid = await _user(db_session, tag)
        await _artifact(db_session, tag, uid, status="processed")
        before = await _funnel(db_session)

        db_session.add(
            LectureArtifact(
                id=f"{tag}-art2",
                user_id=uid,
                original_filename="second.pdf",
                file_path=f"uploads/{tag}-2.pdf",
                file_type="pdf",
                sha256=secrets.token_hex(32),
                file_size_bytes=10,
                status="processed",
            )
        )
        await db_session.flush()

        assert (await _funnel(db_session))["uploaded"] == before["uploaded"]


class TestReturned:
    async def test_one_active_day_is_not_a_return(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag)
        await _active_days(db_session, tag, uid, [0])

        assert (await _funnel(db_session))["returned"] == before["returned"]

    async def test_two_distinct_days_is(self, db_session):
        """The cheapest honest retention signal available without new events."""
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag)
        await _active_days(db_session, tag, uid, [0, 3])

        assert (await _funnel(db_session))["returned"] == before["returned"] + 1

    async def test_activity_older_than_a_week_is_not_active_7d(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag)
        await _active_days(db_session, tag, uid, [30, 40])

        after = await _funnel(db_session)
        assert after["active_7d"] == before["active_7d"]
        # Still a return — they came back twice, just not lately.
        assert after["returned"] == before["returned"] + 1


class TestWhoCounts:
    async def test_admins_are_excluded_by_default(self, db_session):
        """On a small instance the operator's own account moves every step."""
        tag = _tag()
        before = await _funnel(db_session)
        await _user(db_session, tag, role="admin")

        after = await _funnel(db_session)

        assert after["registered"] == before["registered"]
        assert after["excluded_admins"] == before["excluded_admins"] + 1

    async def test_admins_can_be_opted_back_in(self, db_session):
        tag = _tag()
        before = await _funnel(db_session, include_admins=True)
        await _user(db_session, tag, role="admin")

        after = await _funnel(db_session, include_admins=True)

        assert after["registered"] == before["registered"] + 1
        assert after["include_admins"] is True

    async def test_demo_accounts_never_count(self, db_session):
        """A demo account is a product feature, not somebody trying the app."""
        tag = _tag()
        before = await _funnel(db_session, include_admins=True)
        await _user(db_session, tag, role="demo")

        after = await _funnel(db_session, include_admins=True)

        assert after["registered"] == before["registered"]
        assert after["excluded_demo"] == before["excluded_demo"] + 1

    async def test_an_excluded_users_upload_is_excluded_too(self, db_session):
        """Filtering users but not their rows would leak them back in."""
        tag = _tag()
        before = await _funnel(db_session)
        uid = await _user(db_session, tag, role="admin")
        await _artifact(db_session, tag, uid, status="processed")
        await _active_days(db_session, tag, uid, [0, 1])

        after = await _funnel(db_session)

        assert after["uploaded"] == before["uploaded"]
        assert after["processed"] == before["processed"]
        assert after["returned"] == before["returned"]
        assert after["active_7d"] == before["active_7d"]


class TestInvites:
    async def test_issued_counts_capacity_and_redeemed_counts_use(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        db_session.add(
            InviteCode(id=f"{tag}-inv", code=f"BETA-{tag.upper()}", max_uses=5, used_count=2)
        )
        await db_session.flush()

        after = await _funnel(db_session)

        assert after["invites_issued"] == before["invites_issued"] + 5
        assert after["invites_redeemed"] == before["invites_redeemed"] + 2

    async def test_a_revoked_code_stops_flattering_the_issued_count(self, db_session):
        """Capacity you have withdrawn is not capacity you handed out."""
        tag = _tag()
        before = await _funnel(db_session)
        db_session.add(
            InviteCode(
                id=f"{tag}-inv",
                code=f"BETA-{tag.upper()}",
                max_uses=5,
                used_count=1,
                revoked_at=datetime.now(UTC),
            )
        )
        await db_session.flush()

        after = await _funnel(db_session)

        assert after["invites_issued"] == before["invites_issued"]
        # Redemptions already happened, so they still count.
        assert after["invites_redeemed"] == before["invites_redeemed"] + 1

    async def test_an_expired_code_does_not_count_as_issued(self, db_session):
        tag = _tag()
        before = await _funnel(db_session)
        db_session.add(
            InviteCode(
                id=f"{tag}-inv",
                code=f"BETA-{tag.upper()}",
                max_uses=3,
                used_count=0,
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await db_session.flush()

        assert (await _funnel(db_session))["invites_issued"] == before["invites_issued"]
