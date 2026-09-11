"""Integration tests for account deletion against a real database.

The unit tests can only check the shape of the predicates. Whether deletion
*actually* leaves nothing behind depends on foreign keys, table ordering and
the real schema, so it has to be exercised end to end.

This suite caught a live bug: `review_items` has no foreign key, so it sorted
after `lecture_artifacts` and its rows survived, because the predicate used a
subquery over already-deleted parents. See `account_service.OwnedIds`.

It also, for a long time, did *not* catch #97. Every assertion here was about
rows, and the storage purge was sweeping a summary prefix that has never
existed, so the files outlived the account while this suite stayed green.
`TestPurgeUserStorage` is the half that was missing: it asserts on bytes on
disk, in both directions — the owner's files are gone, and nobody else's are.

Every test that deletes an account passes the `storage` fixture below — a
backend rooted in pytest's `tmp_path`. The default is `get_storage()`, which
resolves `settings.data_dir`; that is `/app/data` unless `DATA_DIR` says
otherwise, and the integration runner does not set `DATA_DIR`. A suite whose
subject is *deleting files* must not be one unset variable away from deleting
a developer's real uploads, so nothing here is left on the default.
"""

import secrets
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.database import Base
from app.core.storage import LocalStorageBackend
from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.exam import Exam
from app.models.extraction import Extraction
from app.models.review_item import ReviewItem
from app.models.summary import Summary
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services import account_service, preview_service, summary_service


def _tag() -> str:
    """A short, collision-free prefix for one test's rows."""
    return secrets.token_hex(5)


@pytest.fixture
def storage(tmp_path) -> LocalStorageBackend:
    """A storage backend rooted in a throwaway directory — see the module docstring."""
    return LocalStorageBackend(str(tmp_path))


async def _seed_user(session, tag: str) -> dict[str, str]:
    """Create a user with one of everything. Returns the IDs created."""
    now = datetime.now(UTC)
    uid, cid, aid, sid = (f"{tag}-user", f"{tag}-course", f"{tag}-art", f"{tag}-chat")

    session.add(
        User(
            id=uid,
            email=f"{tag}@delete.test",
            username=f"{tag}_user",
            hashed_password="x",
            created_at=now,
            updated_at=now,
        )
    )
    # Everything below references the user, so it must exist first.
    await session.flush()

    session.add(Course(id=cid, user_id=uid, code=f"DEL{tag}", name=f"Course {tag}"))
    session.add(
        LectureArtifact(
            id=aid,
            user_id=uid,
            course_id=cid,
            week=1,
            title="Lecture 1",
            original_filename="a.pdf",
            # The real shape `artifact_service` writes: uploads/<id>_<name>.
            file_path=f"uploads/{aid}_a.pdf",
            file_type="pdf",
            sha256=f"sha-{tag}",
            file_size_bytes=10,
            status="processed",
        )
    )
    await session.flush()

    session.add(
        Extraction(
            id=f"{tag}-ex",
            artifact_id=aid,
            manifest_json={},
            page_count=1,
            image_count=0,
            extraction_path=f"extractions/{aid}",
        )
    )
    session.add(
        Summary(
            id=f"{tag}-sum",
            course_id=cid,
            week=1,
            content_md="# x",
            # Built, not spelled out: the row must point where the pipeline
            # actually writes, or a storage test proves nothing (#97).
            file_path=summary_service.build_summary_storage_key(cid, 1),
            version=1,
            source_artifacts=[aid],
        )
    )
    session.add(
        Chunk(id=f"{tag}-chunk", artifact_id=aid, stable_id=f"{aid}-0", text="c", page_ref=1)
    )
    # Polymorphic — no foreign key. This is the row that regressed.
    session.add(
        ReviewItem(
            id=f"{tag}-review",
            review_type="classification",
            entity_type="lecture_artifact",
            entity_id=aid,
            payload_json={},
            suggested_values={},
        )
    )
    session.add(
        Exam(
            id=f"{tag}-exam",
            user_id=uid,
            course_id=cid,
            title="Midterm",
            exam_date=now,
            weeks_scope=[1],
        )
    )
    session.add(ChatSession(id=sid, user_id=uid, title="chat"))
    await session.flush()
    session.add(ChatMessage(id=f"{tag}-msg", session_id=sid, role="user", content="hi"))
    session.add(UserSettings(id=f"{tag}-settings", user_id=uid, settings_json={}))
    await session.flush()

    return {"user": uid, "course": cid, "artifact": aid, "chat": sid}


# The one blob deliberately left behind: `courseops/` is content-addressed, so
# the same bytes uploaded by two users are one object with no owner in the key.
SHARED_COURSEOPS_KEY = "courseops/0123456789abcdef_handbook.pdf"


async def _seed_storage(storage, ids: dict[str, str]) -> dict[str, str]:
    """Write one file in every namespace this user's rows point at.

    Keys come from the builders the application uses, never from a literal
    repeated here — a test that hardcodes the key it expects to be deleted
    cannot detect the purge and the writer disagreeing, which is precisely
    what #97 was.

    Returns:
        Mapping of a short label to the key written.
    """
    aid, cid = ids["artifact"], ids["course"]
    keys = {
        "upload": f"uploads/{aid}_a.pdf",
        "extraction": f"extractions/{aid}/images/page1.png",
        # Superseded and current cache versions: bumping the version leaves the
        # old PDF on disk, so the purge has to sweep both.
        "preview_old": preview_service.preview_keys_for_artifact(aid)[0],
        "preview_current": preview_service.preview_keys_for_artifact(aid)[-1],
        "summary": summary_service.build_summary_storage_key(cid, 1),
        "summary_other_week": summary_service.build_summary_storage_key(cid, 7),
    }
    for label, key in keys.items():
        await storage.put(key, f"{label} for {aid}".encode())
    return keys


@pytest.mark.asyncio(loop_scope="session")
class TestPurgeUserStorage:
    """#97: the rows went, the files stayed.

    The purge enumerated every prefix from the artifact id. Summary files have
    never been keyed that way — before #92 it was the course code, after it the
    course id — so `summaries/<artifact_id>` matched nothing on any instance
    that has ever existed, and deletion reported success with the user's
    generated coursework still on disk.
    """

    async def test_summary_files_are_deleted(self, db_session, storage):
        """The bug, stated directly: the summary file must not survive."""
        ids = await _seed_user(db_session, _tag())
        keys = await _seed_storage(storage, ids)

        await account_service.delete_user_account(db_session, ids["user"], storage=storage)
        await db_session.flush()

        assert not await storage.exists(keys["summary"])
        # A prefix sweep, so every week goes, not just the one week a row named.
        assert not await storage.exists(keys["summary_other_week"])

    async def test_another_users_summary_file_is_untouched(self, db_session, storage):
        """Over-deleting is worse than under-deleting.

        The prefix is built per course id, and course ids are per-user primary
        keys (#92), so one user's sweep must not reach into another's.
        """
        victim = await _seed_user(db_session, _tag())
        keeper = await _seed_user(db_session, _tag())
        victim_keys = await _seed_storage(storage, victim)
        keeper_keys = await _seed_storage(storage, keeper)

        await account_service.delete_user_account(db_session, victim["user"], storage=storage)
        await db_session.flush()

        assert not await storage.exists(victim_keys["summary"])
        for label, key in keeper_keys.items():
            assert await storage.exists(key), f"deleted another user's {label}: {key}"
        assert (
            await storage.get(keeper_keys["summary"])
            == f"summary for {keeper['artifact']}".encode()
        )

    async def test_every_artifact_scoped_namespace_is_deleted(self, db_session, storage):
        """Uploads, extractions and previews — including the stale version.

        `previews/` looked covered because it is artifact-scoped, but nothing
        swept it: the purge deleted `file_path` by key and two prefixes, and
        `previews/v<N>/<id>.pdf` is neither.
        """
        ids = await _seed_user(db_session, _tag())
        keys = await _seed_storage(storage, ids)

        await account_service.delete_user_account(db_session, ids["user"], storage=storage)
        await db_session.flush()

        survivors = [label for label, key in keys.items() if await storage.exists(key)]
        assert survivors == [], f"files survived account deletion: {survivors}"

    async def test_shared_courseops_blob_is_left_alone(self, db_session, storage):
        """A decision, not an oversight — hold it in place with a test.

        `courseops/<sha256[:16]>_<name>` is content-addressed and has no owner
        in the key, so two users who upload the same handbook share one object.
        Purging it on one account's closure would delete the other user's
        document. Until that store tracks ownership, leaving the blob is the
        correct trade: residue beats destroying someone else's data.
        """
        ids = await _seed_user(db_session, _tag())
        await _seed_storage(storage, ids)
        await storage.put(SHARED_COURSEOPS_KEY, b"%PDF-1.4 shared by two users")

        await account_service.delete_user_account(db_session, ids["user"], storage=storage)
        await db_session.flush()

        assert await storage.exists(SHARED_COURSEOPS_KEY)

    async def test_reports_how_many_objects_it_deleted(self, db_session, storage):
        """The count must not be inflated by keys that were never there."""
        ids = await _seed_user(db_session, _tag())
        keys = await _seed_storage(storage, ids)

        deleted = await account_service.purge_user_storage(db_session, ids["user"], storage)

        assert deleted == len(keys)

    async def test_an_account_with_no_files_purges_cleanly(self, db_session, storage):
        """Nothing on disk is not an error, and must not report deletions."""
        ids = await _seed_user(db_session, _tag())

        deleted = await account_service.purge_user_storage(db_session, ids["user"], storage)

        assert deleted == 0


@pytest.mark.asyncio(loop_scope="session")
class TestDeleteUserAccount:
    """Deleting an account must remove everything it owns — and nothing else."""

    async def test_leaves_no_row_behind_in_any_table(self, db_session, storage):
        ids = await _seed_user(db_session, _tag())

        await account_service.delete_user_account(db_session, ids["user"], storage=storage)
        await db_session.flush()

        survivors = []
        owned_values = {ids["artifact"], ids["course"], ids["chat"]}
        for table in Base.metadata.tables.values():
            cols = table.c
            clauses = []
            if "user_id" in cols:
                clauses.append(cols.user_id == ids["user"])
            elif table.name == "users":
                clauses.append(cols.id == ids["user"])
            for name in ("artifact_id", "course_id", "session_id", "entity_id"):
                if name in cols:
                    clauses.append(cols[name].in_(owned_values))
            for clause in clauses:
                count = await db_session.scalar(
                    select(func.count()).select_from(table).where(clause)
                )
                if count:
                    survivors.append(f"{table.name}={count}")

        assert survivors == [], f"Rows survived account deletion: {survivors}"

    async def test_review_items_are_deleted(self, db_session, storage):
        """Regression: review_items has no FK and was previously left behind."""
        tag = _tag()
        ids = await _seed_user(db_session, tag)

        await account_service.delete_user_account(db_session, ids["user"], storage=storage)
        await db_session.flush()

        remaining = await db_session.scalar(
            select(func.count())
            .select_from(ReviewItem)
            .where(ReviewItem.entity_id == ids["artifact"])
        )
        assert remaining == 0

    async def test_does_not_touch_another_users_data(self, db_session, storage):
        victim = await _seed_user(db_session, _tag())
        keeper = await _seed_user(db_session, _tag())

        await account_service.delete_user_account(db_session, victim["user"], storage=storage)
        await db_session.flush()

        assert await db_session.get(User, keeper["user"]) is not None
        for model, key in ((Course, "course"), (LectureArtifact, "artifact")):
            assert await db_session.get(model, keeper[key]) is not None
        still_there = await db_session.scalar(
            select(func.count())
            .select_from(ReviewItem)
            .where(ReviewItem.entity_id == keeper["artifact"])
        )
        assert still_there == 1

    async def test_reports_what_it_deleted(self, db_session, storage):
        ids = await _seed_user(db_session, _tag())

        counts = await account_service.delete_user_account(db_session, ids["user"], storage=storage)

        assert counts["users"] == 1
        assert counts["review_items"] == 1
        assert sum(counts.values()) >= 10


@pytest.mark.asyncio(loop_scope="session")
class TestExportUserData:
    """Export must cover the same ground as deletion, minus credentials."""

    async def test_exports_the_users_own_rows(self, db_session):
        ids = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, ids["user"])

        assert data["user_id"] == ids["user"]
        assert "courses" in data["tables"]
        assert "lecture_artifacts" in data["tables"]
        assert data["tables"]["users"][0]["id"] == ids["user"]

    async def test_never_exports_the_password_hash(self, db_session):
        ids = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, ids["user"])

        assert "hashed_password" not in data["tables"]["users"][0]
        assert "x" not in data["tables"]["users"][0].values()

    async def test_excludes_other_users(self, db_session):
        mine = await _seed_user(db_session, _tag())
        theirs = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, mine["user"])

        course_ids = {row["id"] for row in data["tables"]["courses"]}
        assert mine["course"] in course_ids
        assert theirs["course"] not in course_ids
