"""#63: a merge settles its own week conflicts, against a real database.

`merge_courses` used to file a `ReviewItem` for a week summarized in both
courses and leave it there. That deferred the question to an inbox with no way
to answer it -- `/review-items/{id}/resolve` has an apply-branch for
`lecture_artifact` only, so resolving a `merge_week_conflict` item marked it
resolved, returned 200, and changed nothing. The source summary was also
stranded in the archived source course on purpose, to keep the review item's
entity reachable.

What replaces it is a policy applied during the merge, and the reason these
tests are here rather than in `tests/unit` is that every assertion worth making
spans tables and storage at once: whose course a summary row belongs to, which
key its bytes live under, whether the *other* summary survived, and whether the
source course was archived. A mocked session can only confirm that some method
was awaited in some order -- which is what the unit test it replaces did, and
why it could pass while the feature was half-built.

The storage assertions matter as much as the rows. Summary keys are derived
from `course_id` (#92) and `summaries.file_path` caches the key, so moving a
summary between courses without re-keying leaves the row in one course and its
bytes under another's prefix -- a divergence nothing notices until
`backfill_summary_storage_keys` "corrects" `file_path` to a key with nothing
behind it. That bug was found while fixing #63 and is fixed here too, so it is
asserted here too.
"""

import pytest
from sqlalchemy import select

from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.review_item import ReviewItem
from app.models.summary import Summary
from app.models.user import User
from app.services import course_service, summary_service

CLEAN_WEEK = 1
CONFLICT_WEEK = 2


async def _user(db_session) -> str:
    user_id = generate_id()
    db_session.add(
        User(
            id=user_id,
            email=f"merge-{user_id[:8]}@test.local",
            username=f"merge_{user_id[:8]}",
            role="user",
            tier="free",
            is_active=True,
            email_verified=False,
            mfa_enabled=False,
        )
    )
    await db_session.flush()
    return user_id


async def _course(db_session, user_id: str, code: str) -> Course:
    course = Course(id=generate_id(), user_id=user_id, code=code, name=code)
    db_session.add(course)
    await db_session.flush()
    return course


async def _summary(db_session, course: Course, week: int, content: str) -> Summary:
    """A summary row whose bytes are actually on disk under its own key."""
    key = summary_service.build_summary_storage_key(course.id, week)
    await get_storage().put(key, content.encode("utf-8"))
    summary = Summary(
        id=generate_id(),
        course_id=course.id,
        week=week,
        content_md=content,
        file_path=key,
        version=1,
        source_artifacts=[],
    )
    db_session.add(summary)
    await db_session.flush()
    return summary


async def _artifact(db_session, user_id: str, course: Course, week: int) -> LectureArtifact:
    artifact = LectureArtifact(
        id=generate_id(),
        user_id=user_id,
        course_id=course.id,
        week=week,
        original_filename=f"week{week}.pdf",
        file_path=f"uploads/{user_id}/week{week}.pdf",
        file_type="pdf",
        sha256=generate_id().replace("-", "") * 2,
        file_size_bytes=1024,
        status="summarized",
    )
    db_session.add(artifact)
    await db_session.flush()
    return artifact


async def _fixture(db_session) -> tuple[str, Course, Course, Summary, Summary, Summary]:
    """Two courses: one clean week in the source, one week summarized in both."""
    user_id = await _user(db_session)
    source = await _course(db_session, user_id, "SRC101")
    target = await _course(db_session, user_id, "TGT202")

    clean = await _summary(db_session, source, CLEAN_WEEK, "# source week 1\n")
    src_conflict = await _summary(db_session, source, CONFLICT_WEEK, "# source week 2\n")
    tgt_conflict = await _summary(db_session, target, CONFLICT_WEEK, "# target week 2\n")

    # An artifact per week in the source, so `regenerate` has something to
    # summarize from once they have moved.
    await _artifact(db_session, user_id, source, CLEAN_WEEK)
    await _artifact(db_session, user_id, source, CONFLICT_WEEK)

    return user_id, source, target, clean, src_conflict, tgt_conflict


@pytest.mark.asyncio(loop_scope="session")
class TestNoReviewItemIsFiled:
    """The half-built path is gone, not merely bypassed."""

    async def test_merge_files_no_review_item(self, db_session):
        user_id, _, _, _, _, _ = await _fixture(db_session)

        before = set((await db_session.execute(select(ReviewItem.id))).scalars().all())
        await course_service.merge_courses(db_session, user_id, "SRC101", into_code="TGT202")
        await db_session.flush()
        after = set((await db_session.execute(select(ReviewItem.id))).scalars().all())

        # A conflict happened -- week 2 was summarized in both -- and still no
        # review item exists. This is the assertion that fails if anyone
        # reintroduces the deferral.
        assert after == before

    async def test_result_reports_the_conflict_it_resolved(self, db_session):
        user_id, _, _, _, _, _ = await _fixture(db_session)

        result = await course_service.merge_courses(
            db_session, user_id, "SRC101", into_code="TGT202"
        )

        assert result["conflict_weeks"] == [CONFLICT_WEEK]
        assert result["moved_summaries"] == 1
        assert result["conflict_resolution"] == "regenerate"
        assert "review_items_created" not in result


@pytest.mark.asyncio(loop_scope="session")
class TestCleanWeekIsRekeyed:
    """A moved summary's bytes follow it to the new course's prefix."""

    async def test_moved_summary_row_and_blob_agree(self, db_session):
        user_id, source, target, clean, _, _ = await _fixture(db_session)
        old_key = clean.file_path
        assert old_key == summary_service.build_summary_storage_key(source.id, CLEAN_WEEK)

        await course_service.merge_courses(db_session, user_id, "SRC101", into_code="TGT202")
        await db_session.flush()
        await db_session.refresh(clean)

        new_key = summary_service.build_summary_storage_key(target.id, CLEAN_WEEK)
        storage = get_storage()

        assert clean.course_id == target.id
        # The row's cached key, the key its course implies, and the key the
        # bytes are under are all the same string. Before this fix the first
        # stayed on the source course's prefix while the second moved.
        assert clean.file_path == new_key
        assert await storage.exists(new_key)
        assert (await storage.get(new_key)).decode() == "# source week 1\n"
        assert not await storage.exists(old_key)


@pytest.mark.asyncio(loop_scope="session")
class TestRegeneratePolicy:
    """The default: discard the source summary, rebuild the week from both."""

    async def test_source_summary_is_deleted_and_target_survives(self, db_session):
        user_id, _, target, _, src_conflict, tgt_conflict = await _fixture(db_session)
        src_key, src_id = src_conflict.file_path, src_conflict.id

        result = await course_service.merge_courses(
            db_session, user_id, "SRC101", into_code="TGT202", on_conflict="regenerate"
        )
        await db_session.flush()

        assert await db_session.get(Summary, src_id) is None
        assert not await get_storage().exists(src_key)

        # The target's summary is untouched until the background re-summarize
        # replaces it -- so a failed enqueue degrades to keep_target, never to
        # a week with no summary at all.
        await db_session.refresh(tgt_conflict)
        assert tgt_conflict.content_md == "# target week 2\n"
        assert result["regenerated_weeks"] == [CONFLICT_WEEK]

    async def test_regeneration_targets_an_artifact_now_in_the_target_course(self, db_session):
        user_id, _, target, _, _, _ = await _fixture(db_session)

        result = await course_service.merge_courses(
            db_session, user_id, "SRC101", into_code="TGT202", on_conflict="regenerate"
        )
        await db_session.flush()

        # The caller enqueues these post-commit. Each must belong to the target
        # course by then, because the summarize stage reads every extraction for
        # the *course*+week it finds on the artifact -- an id still pointing at
        # the source would summarize the pre-merge set.
        assert len(result["summarize_artifact_ids"]) == 1
        artifact = await db_session.get(LectureArtifact, result["summarize_artifact_ids"][0])
        assert artifact.course_id == target.id
        assert artifact.week == CONFLICT_WEEK

    async def test_no_artifact_means_no_phantom_regeneration(self, db_session):
        """A conflict week whose artifacts are gone reports nothing to rebuild."""
        user_id = await _user(db_session)
        source = await _course(db_session, user_id, "SRC303")
        target = await _course(db_session, user_id, "TGT404")
        await _summary(db_session, source, CONFLICT_WEEK, "# source\n")
        await _summary(db_session, target, CONFLICT_WEEK, "# target\n")
        # Deliberately no artifacts.

        result = await course_service.merge_courses(
            db_session, user_id, "SRC303", into_code="TGT404", on_conflict="regenerate"
        )

        assert result["conflict_weeks"] == [CONFLICT_WEEK]
        # Promising a regeneration that can never run would be worse than
        # saying the target's summary stands.
        assert result["regenerated_weeks"] == []
        assert result["summarize_artifact_ids"] == []


@pytest.mark.asyncio(loop_scope="session")
class TestKeepTargetPolicy:
    """Spend nothing: the target's summary wins, the source's is discarded."""

    async def test_target_content_stands_and_nothing_is_queued(self, db_session):
        user_id, _, _, _, src_conflict, tgt_conflict = await _fixture(db_session)
        src_key, src_id = src_conflict.file_path, src_conflict.id
        tgt_key = tgt_conflict.file_path

        result = await course_service.merge_courses(
            db_session, user_id, "SRC101", into_code="TGT202", on_conflict="keep_target"
        )
        await db_session.flush()
        await db_session.refresh(tgt_conflict)
        storage = get_storage()

        assert await db_session.get(Summary, src_id) is None
        assert not await storage.exists(src_key)
        assert tgt_conflict.content_md == "# target week 2\n"
        assert tgt_conflict.version == 1
        assert (await storage.get(tgt_key)).decode() == "# target week 2\n"
        assert result["regenerated_weeks"] == []
        assert result["summarize_artifact_ids"] == []


@pytest.mark.asyncio(loop_scope="session")
class TestKeepSourcePolicy:
    """Spend nothing: the source's content replaces the target's."""

    async def test_source_content_overwrites_target_row_and_blob(self, db_session):
        user_id, _, target, _, src_conflict, tgt_conflict = await _fixture(db_session)
        src_id = src_conflict.id

        await course_service.merge_courses(
            db_session, user_id, "SRC101", into_code="TGT202", on_conflict="keep_source"
        )
        await db_session.flush()
        await db_session.refresh(tgt_conflict)

        # One row survives for the week, carrying the source's text, under the
        # target's key -- not two rows, and not the target's old content.
        assert await db_session.get(Summary, src_id) is None
        assert tgt_conflict.content_md == "# source week 2\n"
        assert tgt_conflict.version == 2

        # The key does not move here -- the row was already the target's -- so
        # the blob is only correct if the content is written unconditionally.
        # Skipping the write when the key is unchanged left the source's text in
        # the row and the target's on disk.
        key = summary_service.build_summary_storage_key(target.id, CONFLICT_WEEK)
        assert tgt_conflict.file_path == key
        assert (await get_storage().get(key)).decode() == "# source week 2\n"

        rows = (
            (
                await db_session.execute(
                    select(Summary).where(
                        Summary.course_id == target.id, Summary.week == CONFLICT_WEEK
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


@pytest.mark.asyncio(loop_scope="session")
class TestEverythingElseStillMoves:
    """The conflict handling did not disturb the rest of the merge."""

    async def test_artifacts_move_and_source_is_archived(self, db_session):
        user_id, source, target, _, _, _ = await _fixture(db_session)

        await course_service.merge_courses(db_session, user_id, "SRC101", into_code="TGT202")
        await db_session.flush()
        await db_session.refresh(source)

        left_behind = (
            (
                await db_session.execute(
                    select(LectureArtifact.id).where(LectureArtifact.course_id == source.id)
                )
            )
            .scalars()
            .all()
        )
        assert left_behind == []
        # Archived rather than deleted: the merge stays auditable and the code
        # is not silently freed for reuse.
        assert source.archived_at is not None


@pytest.mark.asyncio(loop_scope="session")
class TestUnknownPolicyIsRefused:
    async def test_bad_policy_raises_before_anything_moves(self, db_session):
        user_id, source, _, _, _, _ = await _fixture(db_session)

        with pytest.raises(ValueError, match="on_conflict"):
            await course_service.merge_courses(
                db_session, user_id, "SRC101", into_code="TGT202", on_conflict="ignore"
            )
        await db_session.flush()
        await db_session.refresh(source)

        # Validation happens before the first write, so a typo cannot half-merge.
        assert source.archived_at is None
        still_there = (
            (
                await db_session.execute(
                    select(LectureArtifact.id).where(LectureArtifact.course_id == source.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(still_there) == 2
