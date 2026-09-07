"""Two-user IDOR checks at the row level -- the half `tests/unit` cannot reach.

`tests/unit/services/test_review_service.py` asserts on *compiled SQL*. That was
not a stylistic choice: `tests/unit` has no database (no sqlite driver is
installed, and the models use JSONB), so when #58/PR #62 rewrote the pending
listing to resolve ownership through `_owned_by` it could only prove which
tables the query names and that every ownership branch is bound to the caller's
id. Whether Postgres then hands back the owner's rows *and only* the owner's
rows was left to CI, and its author flagged the row-level version as belonging
here once #56 made this suite runnable locally.

So these tests deliberately do not mock anything. Two real users own two real
graphs of rows, and each service call is asked the only question a compiled
query cannot answer: which rows come back.

The pending-review predicate is the one worth this much attention because
`ReviewItem` is polymorphic -- `entity_type` + `entity_id`, no foreign key --
so ownership resolves per entity type through a different table each time
(`lecture_artifacts.user_id`, or `summaries` -> `courses.user_id`). That is a
join the type checker cannot see and a compiled-SQL assertion can only describe.
"""

import hashlib

import pytest
import sqlalchemy

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.review_item import ReviewItem
from app.models.summary import Summary
from app.models.user import User
from app.services import artifact_service, review_service

STRANGER_ID = "00000000-0000-0000-0000-0000000000bb"


async def _stranger(db_session) -> str:
    """A second real user, rolled back with the test's SAVEPOINT."""
    db_session.add(
        User(
            id=STRANGER_ID,
            email="stranger@test.local",
            username="stranger_test",
            role="user",
            tier="free",
            is_active=True,
            email_verified=False,
            mfa_enabled=False,
        )
    )
    await db_session.flush()
    return STRANGER_ID


async def _artifact(db_session, user_id: str, filename: str) -> LectureArtifact:
    """An artifact with content nobody else in the test has.

    The digest is derived from the owner *and* the filename, so it is distinct
    per row rather than merely per user. That was once forced on this helper by
    the stale global UNIQUE(sha256); `c9d0e1f2g3h4` dropped it, and the digest
    stays row-distinct anyway because these tests are about which rows a query
    returns -- see TestArtifactDigestUniquenessIsPerUser at the bottom of this
    file for the sharing case.
    """
    artifact = LectureArtifact(
        id=generate_id(),
        user_id=user_id,
        original_filename=filename,
        file_path=f"/data/uploads/{filename}",
        file_type="pdf",
        sha256=hashlib.sha256(f"{user_id}:{filename}".encode()).hexdigest(),
        file_size_bytes=256,
        status="ingested",
    )
    db_session.add(artifact)
    await db_session.flush()
    return artifact


async def _summary(db_session, user_id: str, code: str, week: int) -> Summary:
    """A summary, and the course that carries its ownership."""
    course = Course(id=generate_id(), user_id=user_id, code=code, name=code)
    db_session.add(course)
    await db_session.flush()
    summary = Summary(
        id=generate_id(),
        course_id=course.id,
        week=week,
        content_md="# week",
        file_path=f"/data/summaries/{code}_w{week}.md",
    )
    db_session.add(summary)
    await db_session.flush()
    return summary


async def _pending(db_session, entity_type: str, entity_id: str) -> ReviewItem:
    item = ReviewItem(
        id=generate_id(),
        review_type="classification_course",
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json={},
        suggested_values={},
        status="pending",
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio(loop_scope="session")
class TestPendingReviewsAreScopedByRow:
    """#53/#58: two users, real rows, one predicate."""

    async def test_each_user_sees_only_their_own_artifact_backed_items(
        self, db_session, test_user_id
    ):
        """The artifact-backed branch resolves through lecture_artifacts.user_id."""
        stranger_id = await _stranger(db_session)
        mine = await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, test_user_id, "mine.pdf")).id,
        )
        theirs = await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, stranger_id, "theirs.pdf")).id,
        )

        mine_ids = {
            i.id
            for i in await review_service.list_pending_reviews(db_session, user_id=test_user_id)
        }
        their_ids = {
            i.id for i in await review_service.list_pending_reviews(db_session, user_id=stranger_id)
        }

        assert mine.id in mine_ids
        assert theirs.id not in mine_ids
        assert theirs.id in their_ids
        assert mine.id not in their_ids

    async def test_each_user_sees_only_their_own_summary_backed_items(
        self, db_session, test_user_id
    ):
        """#58 at the row level: the second ownership branch, two joins deep.

        A summary-backed item resolves through `summaries` -> `courses.user_id`.
        The compiled-SQL test can see that the branch exists and is bound to the
        caller; only a database can show that the join actually lands on the
        right course and excludes the other user's identically-shaped row.
        """
        stranger_id = await _stranger(db_session)
        mine = await _pending(
            db_session, "summary", (await _summary(db_session, test_user_id, "CSIT302", 3)).id
        )
        theirs = await _pending(
            db_session, "summary", (await _summary(db_session, stranger_id, "CSIT302", 3)).id
        )

        mine_ids = {
            i.id
            for i in await review_service.list_pending_reviews(db_session, user_id=test_user_id)
        }
        their_ids = {
            i.id for i in await review_service.list_pending_reviews(db_session, user_id=stranger_id)
        }

        assert mine.id in mine_ids
        assert theirs.id not in mine_ids
        assert theirs.id in their_ids
        assert mine.id not in their_ids

    async def test_count_matches_the_listing_for_both_users(self, db_session, test_user_id):
        """The inbox badge and the page it links to must agree, per user."""
        stranger_id = await _stranger(db_session)
        await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, test_user_id, "a.pdf")).id,
        )
        await _pending(
            db_session, "summary", (await _summary(db_session, test_user_id, "CSIT101", 1)).id
        )
        await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, stranger_id, "b.pdf")).id,
        )

        for user_id in (test_user_id, stranger_id):
            listed = await review_service.list_pending_reviews(db_session, user_id=user_id)
            counted = await review_service.count_pending_reviews(db_session, user_id=user_id)
            assert counted == len(listed), f"badge disagrees with the list for {user_id}"

        assert await review_service.count_pending_reviews(db_session, user_id=test_user_id) == 2
        assert await review_service.count_pending_reviews(db_session, user_id=stranger_id) == 1

    async def test_an_unhandled_entity_type_is_returned_to_nobody(self, db_session, test_user_id):
        """Fail-closed, proven by rows rather than by reading the predicate.

        `_owned_by` is an allow-list of entity tables. An entity type nobody
        added a branch for must be invisible to everyone -- a bug report -- and
        never fall through to being visible to everyone, which is an incident.
        """
        stranger_id = await _stranger(db_session)
        orphan = await _pending(db_session, "flashcard", generate_id())

        for user_id in (test_user_id, stranger_id):
            listed = {
                i.id for i in await review_service.list_pending_reviews(db_session, user_id=user_id)
            }
            assert orphan.id not in listed

        # ...and it is not hidden by being absent: an unscoped internal caller
        # still sees it, so the row really is in the table.
        unscoped = {i.id for i in await review_service.list_pending_reviews(db_session)}
        assert orphan.id in unscoped

    async def test_empty_user_id_returns_nothing_rather_than_everything(
        self, db_session, test_user_id
    ):
        """`user_id=""` scopes to a user who owns nothing; it does not open up.

        The old `if user_id:` treated the empty string as "no scope" and
        returned every user's pending items.
        """
        await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, test_user_id, "c.pdf")).id,
        )

        assert await review_service.list_pending_reviews(db_session, user_id="") == []
        assert await review_service.count_pending_reviews(db_session, user_id="") == 0

    async def test_list_by_status_is_scoped_the_same_way(self, db_session, test_user_id):
        """Resolved/dismissed items go through `_owned_by` too (#53).

        The version this replaced was inlined in the endpoint with no scoping
        at all, and listed every user's resolved items.
        """
        stranger_id = await _stranger(db_session)
        theirs = await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, stranger_id, "d.pdf")).id,
        )
        theirs.status = "resolved"
        await db_session.flush()

        listed = await review_service.list_reviews_by_status(
            db_session, "resolved", user_id=test_user_id
        )
        assert theirs.id not in {i.id for i in listed}
        assert theirs.id in {
            i.id
            for i in await review_service.list_reviews_by_status(
                db_session, "resolved", user_id=stranger_id
            )
        }

    async def test_get_review_item_by_id_is_scoped(self, db_session, test_user_id):
        """The id-addressed path agrees with the listing, on real rows."""
        stranger_id = await _stranger(db_session)
        theirs = await _pending(
            db_session,
            "lecture_artifact",
            (await _artifact(db_session, stranger_id, "e.pdf")).id,
        )

        assert (
            await review_service.get_review_item(db_session, theirs.id, user_id=test_user_id)
            is None
        )
        found = await review_service.get_review_item(db_session, theirs.id, user_id=stranger_id)
        assert found is not None and found.id == theirs.id


@pytest.mark.asyncio(loop_scope="session")
class TestArtifactLookupIsScopedByRow:
    """`get_artifact` is the lookup five endpoints authorize with (#53, #66).

    Its unit tests assert that endpoints pass `user_id=` into it. That is the
    right thing for them to assert -- but it says nothing about whether the
    filter selects the right rows, and every one of those endpoints serves a
    file on the strength of it.
    """

    async def test_another_users_artifact_is_not_returned(self, db_session, test_user_id):
        stranger_id = await _stranger(db_session)
        theirs = await _artifact(db_session, stranger_id, "confidential.pdf")

        assert (
            await artifact_service.get_artifact(db_session, theirs.id, user_id=test_user_id) is None
        )
        mine_view = await artifact_service.get_artifact(db_session, theirs.id, user_id=stranger_id)
        assert mine_view is not None and mine_view.id == theirs.id

    async def test_omitting_user_id_stays_unscoped_for_internal_callers(
        self, db_session, test_user_id
    ):
        """The pipeline calls this without a user; that path must keep working."""
        stranger_id = await _stranger(db_session)
        theirs = await _artifact(db_session, stranger_id, "pipeline.pdf")

        found = await artifact_service.get_artifact(db_session, theirs.id)
        assert found is not None and found.id == theirs.id


@pytest.mark.asyncio(loop_scope="session")
class TestArtifactDigestUniquenessIsPerUser:
    """`lecture_artifacts.sha256` is unique per user, not globally.

    `LectureArtifact.__table_args__` has only ever declared
    `UniqueConstraint("sha256", "user_id")`, and `artifact_service`'s dedup
    query has only ever filtered on `(sha256, user_id)`. The migrated schema
    used to disagree: `c73364432b98` created the table with a bare
    `sa.UniqueConstraint("sha256")` (Postgres names it
    `lecture_artifacts_sha256_key`) *and* a unique index
    `ix_lecture_artifacts_sha256`. The multi-tenant migration `f7g8h9i0j1k2`
    dropped the index and added the per-user constraint, but never dropped the
    table-level one, so both were live at head and the second user to upload a
    given file was refused -- a refusal that also disclosed that somebody else
    held those exact bytes (issue #80).

    `c9d0e1f2g3h4` drops the stale constraint. These two tests are what proves
    it: the first that the behaviour is fixed, the second that it was fixed by
    the schema actually changing rather than by some unrelated shift in what
    the insert does.

    The other half of the rule -- that one user still cannot hold the same
    digest twice -- is not retested here;
    `test_db_constraints.TestArtifactConstraints.test_artifact_sha256_unique`
    already covers it against the same schema, and it is what would catch this
    revision dropping one constraint too many.

    No test could see the original bug before #56: `tests/unit` has no
    database, so it tests the model's `__table_args__`, which were correct all
    along. Only the migrated schema was wrong, which is why this lives in the
    integration suite -- it runs against a real `alembic upgrade head`.
    """

    async def test_two_users_can_hold_the_same_file(self, db_session, test_user_id):
        """The same digest under two owners must be two legal rows."""
        stranger_id = await _stranger(db_session)
        shared = hashlib.sha256(b"a lecture deck the whole cohort downloaded").hexdigest()

        for owner in (test_user_id, stranger_id):
            db_session.add(
                LectureArtifact(
                    id=generate_id(),
                    user_id=owner,
                    original_filename="week1.pdf",
                    file_path="/data/uploads/week1.pdf",
                    file_type="pdf",
                    sha256=shared,
                    file_size_bytes=256,
                    status="ingested",
                )
            )
        await db_session.flush()

        owners = await db_session.execute(
            sqlalchemy.select(LectureArtifact.user_id).where(LectureArtifact.sha256 == shared)
        )
        assert set(owners.scalars()) == {test_user_id, stranger_id}

    async def test_the_stale_constraint_is_gone_from_the_schema(self, db_session):
        """Name the constraints, so the test above cannot pass for the wrong reason.

        An insert of two rows can start succeeding for reasons that have
        nothing to do with #80 -- a changed fixture, a rolled-back session, a
        column that stopped being written. Asserting on `pg_constraint`
        directly is what ties the green above to the migration: the global
        rule is absent and the per-user one is still present.
        """
        rows = await db_session.execute(
            sqlalchemy.text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'lecture_artifacts'::regclass AND contype = 'u'"
            )
        )
        names = {r[0] for r in rows}
        assert "uq_artifacts_sha256_user" in names, (
            "the per-user constraint the model declares is missing from the "
            f"migrated schema: {sorted(names)}"
        )
        assert "lecture_artifacts_sha256_key" not in names, (
            "the stale global UNIQUE(sha256) is back in the migrated schema -- "
            "c9d0e1f2g3h4 drops it, so either that revision is not applied or "
            f"something later re-added it. Found: {sorted(names)}"
        )
