"""#92: summary storage keys, and the backfill that moves the old ones.

`build_summary_storage_key` used to take a course *code*. Codes are unique
only per user (`uq_courses_code_user`), so two students who both take
`CSIT302` got byte-identical keys: the second pipeline run overwrote the
first's file, and both `summaries` rows stored that one path. Nothing raised.

These tests are written against two users who share a course code, because
that is the only arrangement in which the bug is visible -- a single-user
assertion on the key's shape passes just as happily with the broken builder.

The backfill runs against a real `LocalStorageBackend` over `tmp_path` rather
than a mock: what is being asserted is which bytes end up in which file, and a
mocked storage can only report the calls it was asked to make.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.storage import LocalStorageBackend
from app.models.summary import Summary
from app.services import summary_service

# Two users, one course code, one week -- the arrangement from the issue.
COURSE_A = "0192c4d5-1111-4000-8000-00000000000a"
COURSE_B = "0192c4d5-2222-4000-8000-00000000000b"
SHARED_CODE = "CSIT302"
WEEK = 3

LEGACY_KEY = f"summaries/{SHARED_CODE}/{SHARED_CODE}_Week{WEEK}.md"


def _summary(summary_id: str, course_id: str, content: str, file_path: str) -> Summary:
    return Summary(
        id=summary_id,
        course_id=course_id,
        week=WEEK,
        content_md=content,
        file_path=file_path,
        version=1,
        source_artifacts=[],
    )


def _session(rows: list[Summary]) -> AsyncMock:
    """A session that hands back *rows* from the backfill's one SELECT."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


@pytest.fixture
def storage(tmp_path):
    return LocalStorageBackend(str(tmp_path))


class TestBuildSummaryStorageKey:
    """The key must carry an owner. The course id is one; the code is not."""

    def test_two_users_sharing_a_course_code_get_distinct_keys(self):
        """The collision from #92, stated directly."""
        key_a = summary_service.build_summary_storage_key(COURSE_A, WEEK)
        key_b = summary_service.build_summary_storage_key(COURSE_B, WEEK)

        assert key_a != key_b
        # Not merely distinct: neither may be derivable from the shared code,
        # or the two users are one guess apart again.
        assert SHARED_CODE not in key_a
        assert SHARED_CODE not in key_b

    def test_key_is_the_documented_shape(self):
        assert (
            summary_service.build_summary_storage_key(COURSE_A, WEEK)
            == f"summaries/{COURSE_A}/Week{WEEK}.md"
        )

    def test_first_segment_is_the_course_id_the_files_route_resolves(self):
        """`app.api.files._authorize_path` owns this coupling.

        It takes the first segment after the prefix and asks
        `course_service.get_course_by_id` whether the caller owns it. A key
        whose first segment is anything else scopes to nothing.
        """
        key = summary_service.build_summary_storage_key(COURSE_A, WEEK)
        prefix, owner_segment, filename = key.split("/")

        assert prefix == summary_service.SUMMARY_KEY_PREFIX
        assert owner_segment == COURSE_A
        assert filename.endswith(".md")

    def test_the_builder_takes_an_id_and_has_no_course_code_input(self):
        """A rename (`rename_course`) must not be able to move the file.

        Asserting on the signature, not just the output: the code is a
        mutable, per-user-unique string, so a builder that accepts one at all
        can be handed one again by a future caller.
        """
        params = list(inspect.signature(summary_service.build_summary_storage_key).parameters)
        assert params == ["course_id", "week"]


class TestBuildSummaryFilePath:
    """The local-path helper follows the same shape as the storage key."""

    def test_path_is_keyed_on_the_course_id(self, tmp_path):
        result = summary_service.build_summary_file_path(str(tmp_path), COURSE_A, WEEK)

        assert result.name == f"Week{WEEK}.md"
        assert result.parent.name == COURSE_A

    def test_two_users_sharing_a_course_code_get_distinct_paths(self, tmp_path):
        path_a = summary_service.build_summary_file_path(str(tmp_path), COURSE_A, WEEK)
        path_b = summary_service.build_summary_file_path(str(tmp_path), COURSE_B, WEEK)

        assert path_a != path_b

    def test_creates_the_course_directory(self, tmp_path):
        summary_service.build_summary_file_path(str(tmp_path), COURSE_A, WEEK)

        assert (tmp_path / COURSE_A).is_dir()


class TestBackfillSummaryStorageKeys:
    """The migration's storage half: two colliding rows, one file, no loss."""

    async def test_each_user_ends_up_with_their_own_file_and_content(self, storage):
        """The live-instance state: one file, holding whoever ran last.

        Both rows point at `summaries/CSIT302/CSIT302_Week3.md`; the file
        holds user B's summary because B's pipeline ran second. This is the
        case the backfill must not solve by moving the file.
        """
        rows = [
            _summary("sum-a", COURSE_A, "# A's week 3\n", LEGACY_KEY),
            _summary("sum-b", COURSE_B, "# B's week 3\n", LEGACY_KEY),
        ]
        await storage.put(LEGACY_KEY, b"# B's week 3\n")

        counts = await summary_service.backfill_summary_storage_keys(_session(rows), storage)

        key_a = summary_service.build_summary_storage_key(COURSE_A, WEEK)
        key_b = summary_service.build_summary_storage_key(COURSE_B, WEEK)
        assert key_a != key_b
        assert await storage.get(key_a) == b"# A's week 3\n"
        assert await storage.get(key_b) == b"# B's week 3\n"
        assert rows[0].file_path == key_a
        assert rows[1].file_path == key_b
        assert counts == {
            "rows": 2,
            "files_written": 2,
            "paths_updated": 2,
            "legacy_deleted": 1,
        }

    async def test_file_content_that_disagrees_with_the_row_is_not_carried_over(self, storage):
        """`content_md` is the source of truth, the file is not.

        A backfill that moved or copied the existing file would hand user A a
        summary generated from user B's lecture material -- the disclosure in
        #92, preserved by the fix for it.
        """
        row = _summary("sum-a", COURSE_A, "# A's real summary\n", LEGACY_KEY)
        await storage.put(LEGACY_KEY, b"# somebody else's summary\n")

        await summary_service.backfill_summary_storage_keys(_session([row]), storage)

        new_key = summary_service.build_summary_storage_key(COURSE_A, WEEK)
        assert await storage.get(new_key) == b"# A's real summary\n"
        assert b"somebody else" not in await storage.get(new_key)

    async def test_legacy_file_is_deleted_only_after_every_row_is_written(self, storage):
        rows = [
            _summary("sum-a", COURSE_A, "# A\n", LEGACY_KEY),
            _summary("sum-b", COURSE_B, "# B\n", LEGACY_KEY),
        ]
        await storage.put(LEGACY_KEY, b"# B\n")

        await summary_service.backfill_summary_storage_keys(_session(rows), storage)

        assert not await storage.exists(LEGACY_KEY)
        for row in rows:
            assert await storage.exists(row.file_path)

    async def test_keep_legacy_leaves_the_old_file_alone(self, storage):
        row = _summary("sum-a", COURSE_A, "# A\n", LEGACY_KEY)
        await storage.put(LEGACY_KEY, b"# A\n")

        counts = await summary_service.backfill_summary_storage_keys(
            _session([row]), storage, delete_legacy=False
        )

        assert await storage.exists(LEGACY_KEY)
        assert counts["legacy_deleted"] == 0

    async def test_a_path_outside_the_summaries_prefix_is_never_deleted(self, storage):
        """Only keys the backfill recognises as its own may be removed.

        A row whose `file_path` was written by hand, or as an absolute path
        this deployment's `data_dir` does not prefix, must cost nothing: the
        new file is still written, but nothing else is touched.
        """
        foreign = "uploads/0192abcd_lecture.pptx"
        row = _summary("sum-a", COURSE_A, "# A\n", foreign)
        await storage.put(foreign, b"PK fake pptx")

        counts = await summary_service.backfill_summary_storage_keys(_session([row]), storage)

        assert await storage.exists(foreign)
        assert await storage.get(foreign) == b"PK fake pptx"
        assert counts["legacy_deleted"] == 0

    async def test_running_it_twice_changes_nothing_the_second_time(self, storage):
        """Idempotent: the operator can re-run it, or run it after a restart."""
        rows = [
            _summary("sum-a", COURSE_A, "# A\n", LEGACY_KEY),
            _summary("sum-b", COURSE_B, "# B\n", LEGACY_KEY),
        ]
        await storage.put(LEGACY_KEY, b"# B\n")

        await summary_service.backfill_summary_storage_keys(_session(rows), storage)
        second = await summary_service.backfill_summary_storage_keys(_session(rows), storage)

        assert second["paths_updated"] == 0
        assert second["legacy_deleted"] == 0
        assert await storage.get(rows[0].file_path) == b"# A\n"
        assert await storage.get(rows[1].file_path) == b"# B\n"

    async def test_dry_run_writes_nothing_and_reports_the_work(self, storage):
        rows = [
            _summary("sum-a", COURSE_A, "# A\n", LEGACY_KEY),
            _summary("sum-b", COURSE_B, "# B\n", LEGACY_KEY),
        ]
        await storage.put(LEGACY_KEY, b"# B\n")

        counts = await summary_service.backfill_summary_storage_keys(
            _session(rows), storage, dry_run=True
        )

        assert counts == {
            "rows": 2,
            "files_written": 2,
            "paths_updated": 2,
            "legacy_deleted": 1,
        }
        assert await storage.exists(LEGACY_KEY)
        assert not await storage.exists(summary_service.build_summary_storage_key(COURSE_A, WEEK))
        assert rows[0].file_path == LEGACY_KEY
        assert rows[1].file_path == LEGACY_KEY
