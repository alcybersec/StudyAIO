"""Tests for the email-folding migration (issue #91).

The migration is loaded by path — Alembic version modules are not importable as
a package — and its pure transforms are exercised directly. Those transforms
are where the judgement lives: which rows get rewritten, and which pairs of
rows the migration must refuse to merge on the operator's behalf.

The refusal is the part worth testing hardest. Folding two rows that differ
only by case means choosing which account keeps its sessions, courses and
linked OAuth identities; there is no safe default, and a migration that picks
one silently destroys an account nobody asked it to touch.
"""

import importlib.util
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "d0e1f2g3h4i5_normalize_user_emails.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("normalize_user_emails_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


class TestNormalizeEmail:
    """The migration carries its own frozen copy of the transform."""

    def test_folds_case_across_the_whole_address(self, migration):
        assert migration.normalize_email("Alex@Example.COM") == "alex@example.com"

    def test_strips_surrounding_whitespace(self, migration):
        assert migration.normalize_email(" alex@example.com\n") == "alex@example.com"

    def test_matches_the_application_helper(self, migration):
        """A drift between the two would fold rows into a form nothing looks up."""
        from app.core.utils import normalize_email

        for value in (
            "Alex@Example.com",
            " ALEX@EXAMPLE.COM ",
            "alex@example.com",
            "a.b+tag@Sub.Example.Org",
        ):
            assert migration.normalize_email(value) == normalize_email(value)


class TestFindCollisions:
    """Rows that would land on the same address once folded."""

    def test_no_collision_on_distinct_addresses(self, migration):
        rows = [("u1", "alex@example.com"), ("u2", "sam@example.com")]
        assert migration.find_collisions(rows) == []

    def test_no_collision_when_every_row_is_already_canonical(self, migration):
        rows = [("u1", "alex@example.com"), ("u2", "bob@example.com")]
        assert migration.find_collisions(rows) == []

    def test_case_only_duplicates_collide(self, migration):
        rows = [("u1", "alex@example.com"), ("u2", "Alex@Example.com")]

        collisions = migration.find_collisions(rows)

        assert collisions == [
            ("alex@example.com", [("u1", "alex@example.com"), ("u2", "Alex@Example.com")])
        ]

    def test_whitespace_only_duplicates_collide(self, migration):
        """`btrim`-in-SQL would not have caught a tab or a newline; this does."""
        rows = [("u1", "alex@example.com"), ("u2", "\talex@example.com ")]

        assert len(migration.find_collisions(rows)) == 1

    def test_three_way_collision_reports_every_member(self, migration):
        rows = [
            ("u1", "alex@example.com"),
            ("u2", "ALEX@example.com"),
            ("u3", "Alex@Example.COM"),
        ]

        ((_normalized, members),) = migration.find_collisions(rows)

        assert [user_id for user_id, _ in members] == ["u1", "u2", "u3"]

    def test_an_empty_table_is_not_a_collision(self, migration):
        assert migration.find_collisions([]) == []


class TestRowsToFold:
    """Only the rows that actually need rewriting are rewritten."""

    def test_canonical_rows_are_left_alone(self, migration):
        rows = [("u1", "alex@example.com"), ("u2", "sam@example.com")]
        assert migration.rows_to_fold(rows) == []

    def test_mixed_case_row_is_folded(self, migration):
        rows = [("u1", "Alex@Example.com")]
        assert migration.rows_to_fold(rows) == [("u1", "alex@example.com")]

    def test_only_the_offending_rows_are_returned(self, migration):
        rows = [("u1", "alex@example.com"), ("u2", "SAM@example.com")]
        assert migration.rows_to_fold(rows) == [("u2", "sam@example.com")]

    def test_padded_row_is_folded(self, migration):
        rows = [("u1", " alex@example.com ")]
        assert migration.rows_to_fold(rows) == [("u1", "alex@example.com")]


class TestCollisionReport:
    """The abort message has to be actionable against a live database."""

    def test_names_every_row_involved(self, migration):
        collisions = migration.find_collisions(
            [("u1", "alex@example.com"), ("u2", "Alex@Example.com")]
        )

        report = migration.collision_report(collisions)

        assert "u1" in report
        assert "u2" in report
        assert "Alex@Example.com" in report

    def test_says_the_choice_is_not_being_made_for_the_operator(self, migration):
        collisions = migration.find_collisions(
            [("u1", "alex@example.com"), ("u2", "Alex@Example.com")]
        )

        report = migration.collision_report(collisions)

        assert "1 address(es)" in report
        assert "alex@example.com" in report
        assert "will not make that choice" in report
        assert "alembic upgrade head" in report
