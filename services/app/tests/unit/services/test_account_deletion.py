"""Unit tests for account export and deletion.

The load-bearing test here is `test_every_table_is_classified`: it fails when a
new table is added to the schema without deciding whether it holds user data.
Without it, "delete my account" quietly starts leaving rows behind.
"""

from datetime import UTC, datetime

import pytest

from app.core.database import Base
from app.services import account_service


def _probe_ids() -> account_service.OwnedIds:
    """OwnedIds with a distinctive value per parent type."""
    return account_service.OwnedIds(
        artifacts=["ART-1"],
        courses=["COURSE-1"],
        exams=["EXAM-1"],
        chat_sessions=["CHAT-1"],
        concepts=["CONCEPT-1"],
        quiz_questions=["QQ-1"],
    )


def _edges() -> dict[str, set[str]]:
    """Table name -> the tables it has foreign keys into."""
    return {
        table.name: {fk.column.table.name for fk in table.foreign_keys}
        for table in Base.metadata.tables.values()
    }


def _can_reach(edges: dict[str, set[str]], start: str, target: str) -> bool:
    """Whether `target` is reachable from `start` by following foreign keys."""
    stack, seen = [start], {start}
    while stack:
        node = stack.pop()
        for nxt in edges.get(node, ()):
            if nxt == target:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def _cyclic_edges() -> list[tuple[str, str, str, str | None]]:
    """Foreign keys that sit on a cycle.

    An edge u -> v is on a cycle exactly when v can reach u again. Checking
    reachability per edge (rather than just "both tables are in some cycle")
    matters: `course_documents.user_id -> users` joins two *separate* cycles
    and is not itself cyclic.

    Returns:
        (table, column, referenced_table, ondelete) for each cyclic edge.
    """
    edges = _edges()
    found = []
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if _can_reach(edges, target, table.name):
                found.append((table.name, fk.parent.name, target, fk.ondelete))
    return found


class TestTableClassification:
    """Every mapped table must be either user-scoped or explicitly global."""

    def test_every_table_is_classified(self):
        user_scoped, unclassified = account_service.classify_tables()
        assert unclassified == [], (
            "These tables are neither user-scoped nor listed in "
            "account_service.GLOBAL_TABLES, so account deletion would leave "
            f"their rows behind: {unclassified}. Add a predicate in "
            "_build_predicates(), or add the table to GLOBAL_TABLES if it "
            "genuinely holds no user data."
        )
        assert user_scoped, "Expected at least some user-scoped tables"

    def test_classification_covers_the_whole_schema(self):
        user_scoped, unclassified = account_service.classify_tables()
        all_tables = {t.name for t in Base.metadata.sorted_tables}
        accounted = set(user_scoped) | set(unclassified) | account_service.GLOBAL_TABLES
        assert all_tables - accounted == set()

    def test_users_table_is_global(self):
        """`users` is deleted explicitly by primary key, last."""
        assert "users" in account_service.GLOBAL_TABLES

    def test_invite_codes_survive_their_creator(self):
        """Deleting the issuing admin must not void other testers' invites."""
        assert "invite_codes" in account_service.GLOBAL_TABLES

    def test_shared_catalogs_are_global(self):
        assert "achievements" in account_service.GLOBAL_TABLES
        assert "daily_challenges" in account_service.GLOBAL_TABLES


class TestForeignKeyCycles:
    """`_ordered_tables()` ignores FK cycles; this proves that is safe.

    A cycle makes the delete order between its members arbitrary. That is only
    harmless while every edge in the cycle is SET NULL or CASCADE — a RESTRICT
    or NO ACTION edge would make one of the two possible orders fail at
    runtime, on a real user's deletion request.
    """

    def test_cyclic_foreign_keys_are_nullable_or_cascading(self):
        offenders = [
            f"{table}.{column} -> {target} (ondelete={ondelete})"
            for table, column, target, ondelete in _cyclic_edges()
            if (ondelete or "").upper() not in {"SET NULL", "CASCADE"}
        ]
        assert offenders == [], (
            "These foreign keys are part of a cycle but are not SET NULL or "
            f"CASCADE, so account deletion order is no longer safe: {offenders}"
        )

    def test_the_known_cycles_are_still_the_only_ones(self):
        """A new cycle deserves a fresh look at deletion order, not silence."""
        cyclic_tables = {table for table, _, _, _ in _cyclic_edges()}
        assert cyclic_tables == {"assessments", "course_documents", "users", "invite_codes"}


class TestPredicates:
    """Spot-check the ownership predicates for tables without a user_id."""

    @pytest.fixture
    def tables(self):
        return {t.name: t for t in Base.metadata.sorted_tables}

    @pytest.mark.parametrize(
        "table_name",
        [
            "chunks",
            "extractions",
            "pipeline_runs",
            "flashcards",
            "quiz_questions",
            "summaries",
            "chat_messages",
            "concept_relations",
            "assessments",
            "deadlines",
            "quiz_attempts",
            "review_items",
        ],
    )
    def test_child_table_has_a_predicate(self, tables, table_name):
        """These have no user_id and must be scoped through a parent."""
        table = tables[table_name]
        assert "user_id" not in table.c, (
            f"{table_name} gained a user_id column — simplify its predicate"
        )
        assert account_service._build_predicates(table, "u1", _probe_ids()) is not None

    def test_user_id_tables_use_the_direct_predicate(self, tables):
        clause = account_service._build_predicates(tables["courses"], "u1", _probe_ids())
        assert "user_id" in str(clause)

    def test_unknown_table_returns_none(self):
        from sqlalchemy import Column, MetaData, String, Table

        orphan = Table("some_new_table", MetaData(), Column("id", String(36)))
        assert account_service._build_predicates(orphan, "u1", _probe_ids()) is None


class TestPredicatesUseSnapshottedIds:
    """Regression guard for a bug that let rows survive deletion.

    Scoping a child table with a live subquery — `artifact_id IN (SELECT id FROM
    lecture_artifacts WHERE user_id = ...)` — breaks whenever that child is
    deleted *after* its parent: the subquery returns nothing and the rows stay.
    `review_items` has no foreign key, so it sorted after `lecture_artifacts`
    and was left behind entirely. Predicates must use the IDs snapshotted in
    `OwnedIds` instead, which is ordering-independent.
    """

    @pytest.fixture
    def tables(self):
        return {t.name: t for t in Base.metadata.sorted_tables}

    @pytest.mark.parametrize(
        "table_name",
        [
            "chunks",
            "extractions",
            "pipeline_runs",
            "flashcards",
            "quiz_questions",
            "summaries",
            "chat_messages",
            "concept_relations",
            "assessments",
            "deadlines",
            "quiz_attempts",
            "review_items",
        ],
    )
    def test_no_predicate_issues_a_subquery(self, tables, table_name):
        clause = str(
            account_service._build_predicates(tables[table_name], "u1", _probe_ids()).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "SELECT" not in clause.upper(), (
            f"{table_name} is scoped with a live subquery, so it will match "
            "nothing once its parent rows are deleted. Use the IDs from "
            "OwnedIds instead."
        )

    def test_review_items_is_scoped_by_artifact_and_course(self):
        """The table that actually regressed."""
        table = {t.name: t for t in Base.metadata.sorted_tables}["review_items"]
        clause = str(
            account_service._build_predicates(table, "u1", _probe_ids()).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "ART-1" in clause
        assert "COURSE-1" in clause

    @pytest.mark.asyncio
    async def test_collect_owned_ids_runs_before_any_delete(self):
        """delete_user_account must snapshot ownership before deleting."""
        import inspect

        source = inspect.getsource(account_service.delete_user_account)
        snapshot_at = source.index("collect_owned_ids")
        delete_at = source.index("delete(table)")
        assert snapshot_at < delete_at


class TestExportRedaction:
    """An export is handed to the user — it must carry no credentials."""

    @pytest.mark.parametrize(
        "column",
        ["hashed_password", "mfa_secret", "backup_codes", "token_hash"],
    )
    def test_credential_columns_are_excluded(self, column):
        assert column in account_service.EXPORT_EXCLUDED_COLUMNS

    def test_serialize_converts_datetimes(self):
        value = account_service._serialize(datetime(2026, 9, 3, tzinfo=UTC))
        assert isinstance(value, str)
        assert value.startswith("2026-09-03")

    def test_serialize_passes_through_primitives(self):
        assert account_service._serialize("x") == "x"
        assert account_service._serialize(5) == 5
        assert account_service._serialize(None) is None
        assert account_service._serialize(True) is True

    def test_serialize_stringifies_unknown_types(self):
        class Weird:
            def __str__(self):
                return "weird"

        assert account_service._serialize(Weird()) == "weird"
