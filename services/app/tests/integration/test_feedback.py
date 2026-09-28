"""Feedback against a real database.

Two things here cannot be checked with a mocked session, and both are contracts
rather than conveniences:

* feedback is **deleted with its author's account**, which is what makes the
  free text they wrote safe to store at all;
* listing joins the reporter, filters and orders in SQL.
"""

import secrets

import pytest
from sqlalchemy import func, select

from app.models.feedback import Feedback
from app.models.user import User
from app.services import account_service, feedback_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    return secrets.token_hex(5)


async def _user(session, tag: str) -> str:
    uid = f"{tag}-user"
    session.add(
        User(
            id=uid,
            email=f"{tag}@example.com",
            username=tag,
            hashed_password="x",
            role="user",
        )
    )
    await session.flush()
    return uid


class TestSubmitAndList:
    async def test_a_report_round_trips(self, db_session):
        tag = _tag()
        uid = await _user(db_session, tag)

        await feedback_service.submit_feedback(
            db_session,
            uid,
            kind="bug",
            message="Summary tab renders empty",
            route="/courses/CSIT302/weeks/3",
            app_version="8d8841b",
        )
        await db_session.flush()

        rows, total = await feedback_service.list_feedback(db_session)
        mine = [r for r in rows if r.user_id == uid]
        assert len(mine) == 1
        assert mine[0].route == "/courses/CSIT302/weeks/3"
        assert mine[0].app_version == "8d8841b"
        assert total >= 1

    async def test_listing_loads_the_reporter(self, db_session):
        """The admin inbox shows who said it; a lazy load would fail there."""
        tag = _tag()
        uid = await _user(db_session, tag)
        await feedback_service.submit_feedback(db_session, uid, kind="idea", message="dark mode")
        await db_session.flush()

        rows, _ = await feedback_service.list_feedback(db_session)
        mine = next(r for r in rows if r.user_id == uid)

        assert mine.user.email == f"{tag}@example.com"

    async def test_filtering_by_status(self, db_session):
        tag = _tag()
        uid = await _user(db_session, tag)
        entry = await feedback_service.submit_feedback(db_session, uid, kind="bug", message="x")
        await db_session.flush()

        await feedback_service.set_status(db_session, entry.id, "closed")
        await db_session.flush()

        new_rows, _ = await feedback_service.list_feedback(db_session, status="new")
        closed_rows, _ = await feedback_service.list_feedback(db_session, status="closed")

        assert entry.id not in {r.id for r in new_rows}
        assert entry.id in {r.id for r in closed_rows}

    async def test_counts_group_by_status(self, db_session):
        tag = _tag()
        uid = await _user(db_session, tag)
        before = await feedback_service.count_by_status(db_session)
        await feedback_service.submit_feedback(db_session, uid, kind="bug", message="x")
        await db_session.flush()

        after = await feedback_service.count_by_status(db_session)

        assert after["new"] == before["new"] + 1


class TestDeletedWithTheAccount:
    async def test_closing_an_account_removes_their_feedback(self, db_session, storage):
        """The contract that makes storing free text acceptable.

        `user_id` is a non-nullable FK, so `account_service` classifies this
        table as user-scoped automatically — this asserts the classification
        actually reaches the rows, which is the half a guard test cannot show.
        """
        tag = _tag()
        uid = await _user(db_session, tag)
        await feedback_service.submit_feedback(
            db_session, uid, kind="bug", message="my phone number is 0700 900 123"
        )
        await db_session.flush()

        before = (
            await db_session.execute(select(func.count(Feedback.id)).where(Feedback.user_id == uid))
        ).scalar_one()
        assert before == 1

        await account_service.delete_user_account(db_session, uid, storage=storage)
        await db_session.flush()

        after = (
            await db_session.execute(select(func.count(Feedback.id)).where(Feedback.user_id == uid))
        ).scalar_one()
        assert after == 0

    async def test_another_users_feedback_survives(self, db_session, storage):
        """The other half: scoped deletion, not a table wipe."""
        mine, theirs = _tag(), _tag()
        my_id = await _user(db_session, mine)
        their_id = await _user(db_session, theirs)
        await feedback_service.submit_feedback(db_session, my_id, kind="bug", message="mine")
        await feedback_service.submit_feedback(db_session, their_id, kind="bug", message="theirs")
        await db_session.flush()

        await account_service.delete_user_account(db_session, my_id, storage=storage)
        await db_session.flush()

        survivors = (
            await db_session.execute(
                select(func.count(Feedback.id)).where(Feedback.user_id == their_id)
            )
        ).scalar_one()
        assert survivors == 1
