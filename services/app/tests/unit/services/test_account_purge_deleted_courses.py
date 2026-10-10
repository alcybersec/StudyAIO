"""Account purge reaches summary blobs of courses deleted earlier (M32 C5 / R-020).

A deleted course takes its `summaries` and `summary_versions` rows with it, but
ADR 0004 keeps the blobs, so after that the course id exists nowhere in the
database. `course_service.delete_course` therefore *writes* a zero-byte ledger
marker keyed on the owner and the course id (it deletes nothing), and the
account purge, the only deleter, sweeps from it.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.storage import LocalStorageBackend
from app.core.utils import generate_id
from app.services import account_service, course_service, summary_service


def _session_with(artifacts: list, courses: list[str]) -> MagicMock:
    first = MagicMock()
    first.all.return_value = artifacts
    second = MagicMock()
    second.scalars.return_value.all.return_value = courses
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[first, second])
    return session


def test_ledger_prefix_is_per_user() -> None:
    assert course_service.deleted_course_ledger_prefix("u1") != (
        course_service.deleted_course_ledger_prefix("u2")
    )
    assert "u1" in course_service.deleted_course_ledger_key("u1", "c9")
    assert course_service.deleted_course_ledger_key("u1", "c9").endswith("/c9")


@pytest.mark.asyncio
async def test_purge_sweeps_summaries_of_ledgered_deleted_course(tmp_path) -> None:
    store = LocalStorageBackend(base_dir=str(tmp_path))
    gone = generate_id()
    key = summary_service.build_summary_storage_key(gone, 1)
    vkey = summary_service.build_summary_storage_key(gone, 1, version=1)
    await store.put(key, b"s")
    await store.put(vkey, b"v")
    await store.put(course_service.deleted_course_ledger_key("u1", gone), b"")
    # Another user's deleted course, and its marker, must survive.
    other_id = generate_id()
    other = summary_service.build_summary_storage_key(other_id, 1)
    await store.put(other, b"o")
    await store.put(course_service.deleted_course_ledger_key("u2", other_id), b"")

    await account_service.purge_user_storage(_session_with([], []), "u1", store)

    assert not await store.exists(key)
    assert not await store.exists(vkey)
    assert await store.list_keys(course_service.deleted_course_ledger_prefix("u1")) == []
    assert await store.exists(other)
    assert await store.list_keys(course_service.deleted_course_ledger_prefix("u2")) != []


@pytest.mark.asyncio
async def test_delete_course_records_ledger_marker_and_keeps_blobs(tmp_path) -> None:
    store = LocalStorageBackend(base_dir=str(tmp_path))
    course = MagicMock()
    course.id = "course-001"
    found = MagicMock()
    found.scalar_one_or_none.return_value = course
    empty = MagicMock()
    empty.rowcount = 0
    empty.scalars.return_value.all.return_value = []
    session = MagicMock()
    session.flush = AsyncMock()

    async def dispatch(query):
        sql = str(query)
        if sql.upper().startswith("SELECT") and "FROM courses" in sql:
            return found
        return empty

    session.execute = AsyncMock(side_effect=dispatch)
    blob = summary_service.build_summary_storage_key("course-001", 1)
    await store.put(blob, b"keep")

    await course_service.delete_course(session, "user-001", "CSIT302", storage=store)

    assert await store.exists(course_service.deleted_course_ledger_key("user-001", "course-001"))
    assert await store.exists(blob)  # ADR 0004: course delete keeps blobs


@pytest.mark.asyncio
async def test_purge_ignores_ledger_entries_that_are_not_course_ids(tmp_path) -> None:
    """A folder placeholder ('.../') must not widen the sweep to every summary."""
    other_id = generate_id()
    store = LocalStorageBackend(base_dir=str(tmp_path))
    other = summary_service.build_summary_storage_key(other_id, 1)
    await store.put(other, b"o")
    prefix = course_service.deleted_course_ledger_prefix("u1")
    store.list_keys = AsyncMock(return_value=[f"{prefix}/", f"{prefix}/imported", f"{prefix}/x/"])

    await account_service.purge_user_storage(_session_with([], []), "u1", store)

    assert await store.exists(other)


@pytest.mark.asyncio
async def test_purge_keeps_ledger_when_listing_fails(tmp_path) -> None:
    """A failed listing aborts the ledger sweep: the markers are the only attribution."""
    gone = generate_id()
    store = LocalStorageBackend(base_dir=str(tmp_path))
    marker = course_service.deleted_course_ledger_key("u1", gone)
    await store.put(marker, b"")
    store.list_keys = AsyncMock(side_effect=RuntimeError("s3 down"))

    await account_service.purge_user_storage(_session_with([], []), "u1", store)

    assert await store.exists(marker)
