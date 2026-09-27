"""The #107 courseops backfill, against a real database and real storage.

The unit tests drive `backfill_courseops_storage_keys` through a fake session that
answers from the statement's own bound parameters. That covers the branching but
not the SQL: an `update()` that never lands, or a count that reads the wrong
column, would pass there and fail here.

It matters more than usual for this function, because the instance it was written
for has **zero** `course_documents` rows — so running it in production reports
zeros and proves nothing. This is where the non-trivial case is exercised.
"""

import secrets

import pytest

from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.user import User
from app.services import courseops_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tag() -> str:
    """A collision-proof suffix.

    `generate_id()[:8]` is not safe here: uuid7 is time-prefixed, so ids minted in
    the same millisecond share a prefix.
    """
    return secrets.token_hex(5)


def _legacy_key(digest: str, name: str) -> str:
    """The pre-#107 shape: content-addressed, no owner. Spelled out on purpose."""
    return f"courseops/{digest[:16]}_{name}"


async def _seed_owner(session, tag: str) -> tuple[str, str]:
    """Create a user and a course, returning their ids."""
    uid, cid = f"{tag}-user", f"{tag}-course"
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
    session.add(Course(id=cid, user_id=uid, code=f"C{tag[:6].upper()}", name="Course"))
    await session.flush()
    return uid, cid


async def _seed_document(session, *, doc_id, uid, cid, key, digest) -> None:
    session.add(
        CourseDocument(
            id=doc_id,
            user_id=uid,
            course_id=cid,
            document_type="handbook",
            original_filename="handbook.pdf",
            file_path=key,
            file_type="pdf",
            sha256=digest,
            file_size_bytes=12,
        )
    )
    await session.flush()


async def _file_path(session, doc_id: str) -> str:
    doc = await session.get(CourseDocument, doc_id)
    await session.refresh(doc)
    return doc.file_path


class TestBackfillAgainstRealRows:
    async def test_re_keys_the_row_and_copies_the_blob(self, db_session, storage):
        tag = _tag()
        digest = secrets.token_hex(32)
        uid, cid = await _seed_owner(db_session, tag)
        legacy = _legacy_key(digest, "handbook.pdf")
        await _seed_document(
            db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
        )
        await storage.put(legacy, b"%PDF-1.4 handbook")

        counts = await courseops_service.backfill_courseops_storage_keys(db_session, storage)
        await db_session.flush()

        expected = courseops_service.courseops_key(uid, digest, "handbook.pdf")
        assert await _file_path(db_session, f"{tag}-doc") == expected
        assert await storage.get(expected) == b"%PDF-1.4 handbook"
        assert not await storage.exists(legacy)
        assert counts["blobs_copied"] >= 1
        assert counts["paths_updated"] >= 1

    async def test_two_owners_sharing_one_blob_each_get_their_own(self, db_session, storage):
        """The case that made copying — not moving — the correct choice."""
        digest = secrets.token_hex(32)
        legacy = _legacy_key(digest, "handbook.pdf")
        await storage.put(legacy, b"%PDF-1.4 one handbook")

        owners = []
        for _ in range(2):
            tag = _tag()
            uid, cid = await _seed_owner(db_session, tag)
            await _seed_document(
                db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
            )
            owners.append((tag, uid))

        await courseops_service.backfill_courseops_storage_keys(db_session, storage)
        await db_session.flush()

        for tag, uid in owners:
            expected = courseops_service.courseops_key(uid, digest, "handbook.pdf")
            assert await _file_path(db_session, f"{tag}-doc") == expected
            assert await storage.get(expected) == b"%PDF-1.4 one handbook"
        assert not await storage.exists(legacy)

    async def test_a_dry_run_leaves_the_database_and_disk_alone(self, db_session, storage):
        tag = _tag()
        digest = secrets.token_hex(32)
        uid, cid = await _seed_owner(db_session, tag)
        legacy = _legacy_key(digest, "handbook.pdf")
        await _seed_document(
            db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
        )
        await storage.put(legacy, b"%PDF-1.4 handbook")

        counts = await courseops_service.backfill_courseops_storage_keys(
            db_session, storage, dry_run=True
        )

        assert counts["paths_updated"] >= 1  # it reports what it would do
        assert await _file_path(db_session, f"{tag}-doc") == legacy
        assert await storage.exists(legacy)
        assert not await storage.exists(
            courseops_service.courseops_key(uid, digest, "handbook.pdf")
        )

    async def test_running_twice_changes_nothing_the_second_time(self, db_session, storage):
        """Idempotence, against the real column rather than a scripted mock."""
        tag = _tag()
        digest = secrets.token_hex(32)
        uid, cid = await _seed_owner(db_session, tag)
        legacy = _legacy_key(digest, "handbook.pdf")
        await _seed_document(
            db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
        )
        await storage.put(legacy, b"%PDF-1.4 handbook")

        await courseops_service.backfill_courseops_storage_keys(db_session, storage)
        await db_session.flush()
        expected = await _file_path(db_session, f"{tag}-doc")

        second = await courseops_service.backfill_courseops_storage_keys(db_session, storage)
        await db_session.flush()

        assert second["blobs_copied"] == 0
        assert second["paths_updated"] == 0
        assert await _file_path(db_session, f"{tag}-doc") == expected
        assert await storage.exists(expected)

    async def test_keep_legacy_leaves_the_old_blob_but_still_re_keys(self, db_session, storage):
        tag = _tag()
        digest = secrets.token_hex(32)
        uid, cid = await _seed_owner(db_session, tag)
        legacy = _legacy_key(digest, "handbook.pdf")
        await _seed_document(
            db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
        )
        await storage.put(legacy, b"%PDF-1.4 handbook")

        await courseops_service.backfill_courseops_storage_keys(
            db_session, storage, delete_legacy=False
        )
        await db_session.flush()

        assert await _file_path(db_session, f"{tag}-doc") != legacy
        assert await storage.exists(legacy)

    async def test_a_missing_legacy_blob_still_re_keys_the_row(self, db_session, storage):
        """Agreement with the migration matters more than the file being there."""
        tag = _tag()
        digest = secrets.token_hex(32)
        uid, cid = await _seed_owner(db_session, tag)
        legacy = _legacy_key(digest, "gone.pdf")
        await _seed_document(
            db_session, doc_id=f"{tag}-doc", uid=uid, cid=cid, key=legacy, digest=digest
        )

        counts = await courseops_service.backfill_courseops_storage_keys(db_session, storage)
        await db_session.flush()

        assert counts["legacy_missing"] >= 1
        assert await _file_path(db_session, f"{tag}-doc") == courseops_service.courseops_key(
            uid, digest, "gone.pdf"
        )

    async def test_an_instance_with_no_course_documents_is_a_clean_no_op(self, db_session, storage):
        """The production case: zero rows must not be an error.

        Asserted because this is the only path the deployed instance takes — it
        has no `course_documents` rows and no `courseops/` directory at all.
        """
        counts = await courseops_service.backfill_courseops_storage_keys(db_session, storage)

        assert counts["blobs_copied"] == 0
        assert counts["paths_updated"] == 0
        assert counts["legacy_deleted"] == 0
        assert counts["legacy_missing"] == 0
