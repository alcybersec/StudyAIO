"""Tests for per-user courseops storage keys (issue #107 / GL#4).

The key was `courseops/<sha256[:16]>_<name>` — content-addressed with no owner —
so two users who uploaded the same handbook shared one blob. Nothing was
corrupted; the *lifecycle* was broken, because `purge_user_storage` could not
delete a blob another user's live row still pointed at, and so closing an
account left its course documents on disk forever.

These cover the three halves of the fix: the key shape, the per-document blob
deletion it made safe, and the migration's row transform.
"""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Select, Update

from app.core.storage import LocalStorageBackend
from app.services import courseops_service
from app.services.courseops_service import (
    _delete_blob_if_unreferenced,
    courseops_key,
    courseops_key_prefix_for_user,
)

USER_A = "0192abcd-dead-beef-cafe-00000000000a"
USER_B = "0192abcd-dead-beef-cafe-00000000000b"
DIGEST = "0123456789abcdef" + "f" * 48

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "4f1c7a2e9b63_courseops_file_path_per_user.py"
)


@pytest.fixture
def storage(tmp_path):
    return LocalStorageBackend(str(tmp_path))


def _count_session(remaining: int) -> AsyncMock:
    """A session whose one SELECT COUNT answers with `remaining`."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = remaining
    session.execute = AsyncMock(return_value=result)
    return session


class TestCourseopsKey:
    def test_carries_the_owner(self):
        assert courseops_key(USER_A, DIGEST, "handbook.pdf").startswith(f"courseops/{USER_A}/")

    def test_truncates_the_digest_to_sixteen(self):
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")
        assert key.endswith("/0123456789abcdef_handbook.pdf")

    def test_two_users_with_identical_content_get_different_keys(self):
        """The bug, stated directly."""
        assert courseops_key(USER_A, DIGEST, "h.pdf") != courseops_key(USER_B, DIGEST, "h.pdf")

    def test_one_user_re_uploading_the_same_file_gets_one_key(self):
        """Dedup within an account is deliberately preserved."""
        assert courseops_key(USER_A, DIGEST, "h.pdf") == courseops_key(USER_A, DIGEST, "h.pdf")

    def test_same_name_different_content_stays_apart(self):
        other = "fedcba9876543210" + "0" * 48
        assert courseops_key(USER_A, DIGEST, "h.pdf") != courseops_key(USER_A, other, "h.pdf")

    def test_prefix_has_no_trailing_slash(self):
        """Matches the other prefixes the purge sweeps; see `purge_user_storage`."""
        assert courseops_key_prefix_for_user(USER_A) == f"courseops/{USER_A}"

    def test_every_key_lies_under_its_owners_prefix(self):
        """The invariant `_delete_blob_if_unreferenced` and the purge both rely on."""
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")
        assert key.startswith(f"{courseops_key_prefix_for_user(USER_A)}/")
        assert not key.startswith(f"{courseops_key_prefix_for_user(USER_B)}/")

    def test_a_sanitized_name_cannot_add_a_segment(self):
        """`sanitize_filename` strips separators, so the key is always 3 segments.

        The migration's legacy/current discriminator is the segment count, so a
        name that could smuggle a slash through would break it.
        """
        from app.core.utils import sanitize_filename

        key = courseops_key(USER_A, DIGEST, sanitize_filename("../../etc/passwd"))
        assert len(key.split("/")) == 3


@pytest.mark.asyncio
class TestDeleteBlobIfUnreferenced:
    async def test_deletes_when_nothing_references_it(self, storage):
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")
        await storage.put(key, b"%PDF-1.4")

        deleted = await _delete_blob_if_unreferenced(_count_session(0), USER_A, key, storage)

        assert deleted is True
        assert not await storage.exists(key)

    async def test_keeps_it_while_another_row_points_at_it(self, storage):
        """One handbook attached to two courses is two rows and one blob."""
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")
        await storage.put(key, b"%PDF-1.4")

        deleted = await _delete_blob_if_unreferenced(_count_session(1), USER_A, key, storage)

        assert deleted is False
        assert await storage.exists(key)

    async def test_refuses_a_legacy_key_even_when_unreferenced(self, storage):
        """The load-bearing guard: a pre-#107 blob may be another user's too.

        A count over *this* user's rows says nothing about theirs, so an
        owner-less key must be left alone however unreferenced it looks here.
        """
        legacy = "courseops/0123456789abcdef_handbook.pdf"
        await storage.put(legacy, b"%PDF-1.4")

        deleted = await _delete_blob_if_unreferenced(_count_session(0), USER_A, legacy, storage)

        assert deleted is False
        assert await storage.exists(legacy)

    async def test_refuses_another_users_key(self, storage):
        key = courseops_key(USER_B, DIGEST, "handbook.pdf")
        await storage.put(key, b"%PDF-1.4")

        deleted = await _delete_blob_if_unreferenced(_count_session(0), USER_A, key, storage)

        assert deleted is False
        assert await storage.exists(key)

    async def test_refuses_a_key_outside_the_courseops_namespace(self, storage):
        """A row pointing anywhere else must not make this a general deleter."""
        key = f"uploads/{USER_A}_lecture.pdf"
        await storage.put(key, b"%PDF-1.4")

        deleted = await _delete_blob_if_unreferenced(_count_session(0), USER_A, key, storage)

        assert deleted is False
        assert await storage.exists(key)

    async def test_a_storage_failure_does_not_raise(self):
        """The row is already gone; a stuck blob must not become a 500."""
        store = MagicMock()
        store.exists = AsyncMock(return_value=True)
        store.delete = AsyncMock(side_effect=OSError("read-only filesystem"))
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")

        deleted = await _delete_blob_if_unreferenced(_count_session(0), USER_A, key, store)

        assert deleted is False

    async def test_scopes_the_reference_count_to_the_owner(self, storage):
        """A count over every user's rows would never reach zero for a shared name.

        Asserted on the statement's own bound parameters rather than on the
        return value: a mock answers whatever it was wired with regardless of
        the SQL it was handed, so the wiring is the only thing that proves the
        filter is there.
        """
        key = courseops_key(USER_A, DIGEST, "handbook.pdf")
        await storage.put(key, b"%PDF-1.4")
        session = _count_session(0)

        await _delete_blob_if_unreferenced(session, USER_A, key, storage)

        stmt = session.execute.await_args.args[0]
        assert isinstance(stmt, Select)
        bound = set(stmt.compile().params.values())
        assert USER_A in bound
        assert key in bound


class TestMigrationTransform:
    """The migration's row transform is the whole of its behaviour."""

    @pytest.fixture(scope="class")
    def migration(self):
        spec = importlib.util.spec_from_file_location("courseops_key_migration", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_prepends_the_owner_to_a_legacy_key(self, migration):
        assert (
            migration.new_file_path(USER_A, "courseops/0123456789abcdef_h.pdf")
            == f"courseops/{USER_A}/0123456789abcdef_h.pdf"
        )

    def test_agrees_with_the_application_key_builder(self, migration):
        """Two spellings of one shape; they must not drift.

        The migration spells the shape out rather than importing it — pinned
        history must keep meaning what it meant — so this is the only thing
        holding the two together.
        """
        legacy = f"courseops/{DIGEST[:16]}_handbook.pdf"
        assert migration.new_file_path(USER_A, legacy) == courseops_key(
            USER_A, DIGEST, "handbook.pdf"
        )

    def test_is_idempotent(self, migration):
        """Re-running must not nest a second user id."""
        once = migration.new_file_path(USER_A, "courseops/0123456789abcdef_h.pdf")
        assert migration.new_file_path(USER_A, once) == once

    def test_leaves_a_foreign_key_alone(self, migration):
        for key in ("uploads/abc_h.pdf", "summaries/course-1/Week1.md", ""):
            assert migration.new_file_path(USER_A, key) == key

    def test_downgrade_restores_the_shared_shape(self, migration):
        legacy = "courseops/0123456789abcdef_h.pdf"
        assert migration.legacy_file_path(USER_A, migration.new_file_path(USER_A, legacy)) == legacy

    def test_downgrade_refuses_another_users_key(self, migration):
        """Stripping an id that is not the row's owner would invent a key."""
        key = f"courseops/{USER_B}/0123456789abcdef_h.pdf"
        assert migration.legacy_file_path(USER_A, key) == key


@pytest.mark.asyncio
class TestBackfillUnreachableShapes:
    """The backfill must touch only legacy courseops keys."""

    async def _run(self, rows, storage):
        """Drive the backfill with a session that answers from the real SQL."""
        updates: list[tuple[str, str]] = []

        class Session:
            async def execute(self, stmt):
                result = MagicMock()
                if isinstance(stmt, Update):
                    params = stmt.compile().params
                    updates.append((params["id_1"], params["file_path"]))
                    return result
                sql = str(stmt)
                if "count(" in sql:
                    result.scalar_one.return_value = 0
                else:
                    result.all.return_value = rows
                return result

        counts = await courseops_service.backfill_courseops_storage_keys(
            Session(), storage, delete_legacy=True
        )
        return counts, updates

    async def test_re_keys_a_legacy_row_and_copies_its_blob(self, storage):
        legacy = "courseops/0123456789abcdef_h.pdf"
        await storage.put(legacy, b"%PDF-1.4 original")

        counts, updates = await self._run([("doc-1", USER_A, legacy)], storage)

        new_key = f"courseops/{USER_A}/0123456789abcdef_h.pdf"
        assert counts["blobs_copied"] == 1
        assert counts["paths_updated"] == 1
        assert counts["legacy_deleted"] == 1
        assert updates == [("doc-1", new_key)]
        assert await storage.get(new_key) == b"%PDF-1.4 original"
        assert not await storage.exists(legacy)

    async def test_two_users_sharing_a_blob_each_get_a_copy(self, storage):
        """Copying is correct here precisely because the key is content-addressed."""
        legacy = "courseops/0123456789abcdef_h.pdf"
        await storage.put(legacy, b"%PDF-1.4 one handbook")

        counts, _ = await self._run([("doc-1", USER_A, legacy), ("doc-2", USER_B, legacy)], storage)

        assert counts["blobs_copied"] == 2
        for uid in (USER_A, USER_B):
            assert await storage.get(f"courseops/{uid}/0123456789abcdef_h.pdf") == (
                b"%PDF-1.4 one handbook"
            )
        assert not await storage.exists(legacy)

    async def test_an_already_migrated_row_is_skipped(self, storage):
        key = courseops_key(USER_A, DIGEST, "h.pdf")
        await storage.put(key, b"%PDF-1.4")

        counts, updates = await self._run([("doc-1", USER_A, key)], storage)

        assert (counts["blobs_copied"], counts["paths_updated"]) == (0, 0)
        assert updates == []
        assert await storage.exists(key)

    async def test_a_missing_legacy_blob_is_counted_not_fatal(self, storage):
        counts, updates = await self._run(
            [("doc-1", USER_A, "courseops/0123456789abcdef_gone.pdf")], storage
        )

        assert counts["legacy_missing"] == 1
        assert counts["blobs_copied"] == 0
        assert counts["paths_updated"] == 1  # the row still agrees with the migration
        assert len(updates) == 1

    async def test_a_dry_run_changes_nothing(self, storage):
        legacy = "courseops/0123456789abcdef_h.pdf"
        await storage.put(legacy, b"%PDF-1.4 original")
        rows = [("doc-1", USER_A, legacy)]

        class Session:
            async def execute(self, stmt):
                result = MagicMock()
                result.all.return_value = rows
                result.scalar_one.return_value = 1
                return result

        counts = await courseops_service.backfill_courseops_storage_keys(
            Session(), storage, dry_run=True
        )

        assert counts["blobs_copied"] == 1
        assert counts["legacy_deleted"] == 1
        assert await storage.exists(legacy)
        assert not await storage.exists(f"courseops/{USER_A}/0123456789abcdef_h.pdf")
