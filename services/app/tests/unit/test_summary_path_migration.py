"""Tests for the summary file_path re-keying migration (issue #92).

The migration is loaded by path -- Alembic version modules are not importable
as a package -- and run against a throwaway SQLite database with `op` replaced
by a stub that hands it that connection. The statements themselves are what is
worth testing here: `upgrade` is a per-row rewrite and `downgrade` joins back
through `courses`, and neither is exercised by anything else in `tests/unit`
(the integration suite runs the real thing on Postgres).

The fixture is always *two* users holding the same course code, because a
single-user database migrates identically under the old and new shapes. The
collision is the whole subject.
"""

import importlib.util
import inspect
from pathlib import Path

import pytest
import sqlalchemy

from app.services import summary_service

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "6b2e9a4c71df_summary_file_path_per_course.py"
)

SHARED_CODE = "CSIT302"
COURSE_A = "0192c4d5-1111-4000-8000-00000000000a"
COURSE_B = "0192c4d5-2222-4000-8000-00000000000b"
LEGACY_KEY = f"summaries/{SHARED_CODE}/{SHARED_CODE}_Week3.md"


def _load():
    spec = importlib.util.spec_from_file_location("summary_path_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


@pytest.fixture
def bound(migration, monkeypatch):
    """The migration, bound to a SQLite database holding the collision.

    Two users, one course code, one week, one `file_path` shared by both rows
    -- the state a live instance is in before this revision runs.
    """
    engine = sqlalchemy.create_engine("sqlite://")
    connection = engine.connect()

    connection.execute(
        sqlalchemy.text("CREATE TABLE courses (id TEXT PRIMARY KEY, user_id TEXT, code TEXT)")
    )
    connection.execute(
        sqlalchemy.text(
            "CREATE TABLE summaries ("
            "id TEXT PRIMARY KEY, course_id TEXT, week INTEGER, file_path TEXT)"
        )
    )
    for course_id, user in ((COURSE_A, "user-a"), (COURSE_B, "user-b")):
        connection.execute(
            sqlalchemy.text("INSERT INTO courses VALUES (:id, :user, :code)"),
            {"id": course_id, "user": user, "code": SHARED_CODE},
        )
    for summary_id, course_id in (("sum-a", COURSE_A), ("sum-b", COURSE_B)):
        connection.execute(
            sqlalchemy.text("INSERT INTO summaries VALUES (:id, :course, 3, :path)"),
            {"id": summary_id, "course": course_id, "path": LEGACY_KEY},
        )

    class _Op:
        @staticmethod
        def get_bind():
            return connection

    monkeypatch.setattr(migration, "op", _Op)
    try:
        yield migration, connection
    finally:
        connection.close()
        engine.dispose()


def _paths(connection) -> dict[str, str]:
    rows = connection.execute(sqlalchemy.text("SELECT id, file_path FROM summaries")).fetchall()
    return {row[0]: row[1] for row in rows}


class TestKeyShapes:
    """The two shapes, stated as functions so the diff between them is plain."""

    def test_two_users_sharing_a_course_code_get_distinct_paths(self, migration):
        assert migration.new_file_path(COURSE_A, 3) != migration.new_file_path(COURSE_B, 3)

    def test_the_legacy_shape_is_what_collided(self, migration):
        """Pins the bug being migrated away from.

        Both users produce one string, which is why one file served both of
        them. If this ever stops being true the old shape was not what this
        revision thinks it was, and `downgrade` is writing fiction.
        """
        assert migration.legacy_file_path(SHARED_CODE, 3) == LEGACY_KEY
        # Course code and week are its only inputs, so nothing about *which*
        # user's summary it is can reach the string.
        assert list(inspect.signature(migration.legacy_file_path).parameters) == [
            "course_code",
            "week",
        ]

    def test_it_agrees_with_the_application_builder_today(self, migration):
        """The column and the code that writes it must mean the same thing.

        Deliberately a separate assertion rather than an import: a migration
        is pinned history. If a later revision changes the shape again, this
        test fails and points whoever did it at this file, instead of the
        migration silently starting to write next year's keys into last
        year's database.
        """
        assert migration.new_file_path(COURSE_A, 3) == summary_service.build_summary_storage_key(
            COURSE_A, 3
        )


class TestUpgrade:
    """One file_path per course id, derived from the row itself."""

    def test_colliding_rows_are_split(self, bound):
        migration, connection = bound

        migration.upgrade()

        paths = _paths(connection)
        assert paths["sum-a"] == f"summaries/{COURSE_A}/Week3.md"
        assert paths["sum-b"] == f"summaries/{COURSE_B}/Week3.md"
        assert paths["sum-a"] != paths["sum-b"]

    def test_the_course_code_is_gone_from_the_path(self, bound):
        """Nothing per-user-ambiguous may be left in the key."""
        migration, connection = bound

        migration.upgrade()

        assert all(SHARED_CODE not in path for path in _paths(connection).values())

    def test_it_is_idempotent(self, bound):
        """Re-running a revision by hand, or after a failed deploy, is safe."""
        migration, connection = bound

        migration.upgrade()
        first = _paths(connection)
        migration.upgrade()

        assert _paths(connection) == first

    def test_it_does_not_depend_on_the_old_value(self, bound):
        """The new key is re-derived, not parsed out of what is there.

        A row whose `file_path` was never the standard shape -- an absolute
        path from an older deployment, say -- must still land on the right
        key.
        """
        migration, connection = bound
        connection.execute(
            sqlalchemy.text("UPDATE summaries SET file_path = :p WHERE id = 'sum-a'"),
            {"p": "/app/data/summaries/CSIT302/CSIT302_Week3.md"},
        )

        migration.upgrade()

        assert _paths(connection)["sum-a"] == f"summaries/{COURSE_A}/Week3.md"


class TestDowngrade:
    """Back to the colliding shape, which is what the old shape *was*."""

    def test_it_restores_the_code_shaped_path(self, bound):
        migration, connection = bound

        migration.upgrade()
        migration.downgrade()

        paths = _paths(connection)
        assert paths["sum-a"] == LEGACY_KEY
        assert paths["sum-b"] == LEGACY_KEY

    def test_the_join_through_courses_is_what_supplies_the_code(self, bound):
        """`summaries` has no code of its own; a wrong join would be silent."""
        migration, connection = bound
        connection.execute(
            sqlalchemy.text("UPDATE courses SET code = 'MATH200' WHERE id = :id"),
            {"id": COURSE_B},
        )

        migration.upgrade()
        migration.downgrade()

        paths = _paths(connection)
        assert paths["sum-a"] == LEGACY_KEY
        assert paths["sum-b"] == "summaries/MATH200/MATH200_Week3.md"
