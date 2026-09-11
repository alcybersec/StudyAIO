"""#92: the summary key collision, against a real database.

`tests/unit` can only assert on the shape of a key and on a fake session's
rows. The thing that made #92 possible is a schema fact -- `courses.code` is
unique only per user (`uq_courses_code_user`), while `courses.id` is unique
full stop -- and only Postgres can be asked whether that is still true.

So this file does what the unit tests cannot: it puts two real users with the
same course code in the database, runs the backfill's real query against them,
and checks that the owner-scoped getter the files route now depends on tells
their courses apart.

The migration itself (`d0e1f2g3h4i5`) has already run by the time any of this
executes -- `_run_migrations` upgrades to head -- so its statements are known
to be valid Postgres before a single assertion here.
"""

import pytest

from app.core.storage import LocalStorageBackend
from app.core.utils import generate_id
from app.models.course import Course
from app.models.summary import Summary
from app.models.user import User
from app.services import course_service, summary_service

SHARED_CODE = "CSIT302"
WEEK = 3
LEGACY_KEY = f"summaries/{SHARED_CODE}/{SHARED_CODE}_Week{WEEK}.md"


async def _user(db_session, suffix: str) -> str:
    user_id = generate_id()
    db_session.add(
        User(
            id=user_id,
            email=f"summary-key-{suffix}@test.local",
            username=f"summary_key_{suffix}",
            role="user",
            tier="free",
            is_active=True,
            email_verified=False,
            mfa_enabled=False,
        )
    )
    await db_session.flush()
    return user_id


async def _course_with_summary(db_session, user_id: str, content_md: str) -> tuple[Course, Summary]:
    """A course on the shared code, and a summary pointing at the shared key."""
    course = Course(id=generate_id(), user_id=user_id, code=SHARED_CODE, name=SHARED_CODE)
    db_session.add(course)
    await db_session.flush()

    summary = Summary(
        id=generate_id(),
        course_id=course.id,
        week=WEEK,
        content_md=content_md,
        # What both rows held before this fix: one key, one file.
        file_path=LEGACY_KEY,
        version=1,
        source_artifacts=[],
    )
    db_session.add(summary)
    await db_session.flush()
    return course, summary


@pytest.mark.asyncio(loop_scope="session")
class TestCourseCodesAreOnlyUniquePerUser:
    """The schema fact the whole issue rests on."""

    async def test_two_users_can_hold_the_same_course_code(self, db_session):
        alice = await _user(db_session, "alice")
        bob = await _user(db_session, "bob")

        course_a, _ = await _course_with_summary(db_session, alice, "# alice\n")
        course_b, _ = await _course_with_summary(db_session, bob, "# bob\n")

        assert course_a.code == course_b.code == SHARED_CODE
        assert course_a.id != course_b.id
        # Which is why the old key, built from the code, was the same string
        # for both of them.
        assert summary_service.build_summary_storage_key(
            course_a.id, WEEK
        ) != summary_service.build_summary_storage_key(course_b.id, WEEK)


@pytest.mark.asyncio(loop_scope="session")
class TestBackfillAgainstRealRows:
    """The operator's run, on the state a live instance is actually in."""

    async def test_each_user_gets_their_own_file_and_their_own_content(self, db_session, tmp_path):
        """One file before, two after, and neither holds the other's text."""
        alice = await _user(db_session, "alice")
        bob = await _user(db_session, "bob")
        course_a, summary_a = await _course_with_summary(db_session, alice, "# alice week 3\n")
        course_b, summary_b = await _course_with_summary(db_session, bob, "# bob week 3\n")

        storage = LocalStorageBackend(str(tmp_path))
        # The live state: one file, holding whichever pipeline ran last.
        await storage.put(LEGACY_KEY, b"# bob week 3\n")

        counts = await summary_service.backfill_summary_storage_keys(db_session, storage)

        assert counts["rows"] >= 2
        assert summary_a.file_path == f"summaries/{course_a.id}/Week{WEEK}.md"
        assert summary_b.file_path == f"summaries/{course_b.id}/Week{WEEK}.md"
        assert summary_a.file_path != summary_b.file_path
        assert await storage.get(summary_a.file_path) == b"# alice week 3\n"
        assert await storage.get(summary_b.file_path) == b"# bob week 3\n"
        assert not await storage.exists(LEGACY_KEY)

    async def test_the_row_is_trusted_over_the_file(self, db_session, tmp_path):
        """Alice's file held Bob's text; the backfill must not carry it over."""
        alice = await _user(db_session, "alice")
        course_a, summary_a = await _course_with_summary(db_session, alice, "# alice week 3\n")

        storage = LocalStorageBackend(str(tmp_path))
        await storage.put(LEGACY_KEY, b"# somebody else's week 3\n")

        await summary_service.backfill_summary_storage_keys(db_session, storage)

        assert await storage.get(summary_a.file_path) == b"# alice week 3\n"


@pytest.mark.asyncio(loop_scope="session")
class TestOwnerResolutionForTheFilesRoute:
    """`/api/files/summaries/<course_id>/...` resolves ownership through this.

    PR #72 resolved the old code-shaped segment through `get_course_by_code`.
    The segment is a course id now, so the route calls `get_course_by_id`; if
    that getter ever stopped scoping by user, every summary in the instance
    would be readable by every signed-in caller again (#66).
    """

    async def test_owner_resolves_and_a_stranger_does_not(self, db_session):
        alice = await _user(db_session, "alice")
        bob = await _user(db_session, "bob")
        course_a, _ = await _course_with_summary(db_session, alice, "# alice\n")

        assert (
            await course_service.get_course_by_id(db_session, course_a.id, user_id=alice)
            is not None
        )
        assert await course_service.get_course_by_id(db_session, course_a.id, user_id=bob) is None

    async def test_the_shared_code_does_not_resolve_as_an_id(self, db_session):
        """The old key shape cannot be smuggled through the new lookup.

        `summaries/CSIT302/...` asks for a course whose *id* is `CSIT302`.
        Nobody owns one, so the route 404s instead of serving a file that may
        be the other user's.
        """
        alice = await _user(db_session, "alice")
        await _course_with_summary(db_session, alice, "# alice\n")

        assert await course_service.get_course_by_id(db_session, SHARED_CODE, user_id=alice) is None
