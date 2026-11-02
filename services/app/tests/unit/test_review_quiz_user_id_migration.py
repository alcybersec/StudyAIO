"""Tests for the review_items / quiz_attempts user_id migration (R-010).

The revision is loaded by path and run through Alembic ``Operations`` on scratch
SQLite, as the other migration tests do. Its backfill is plain correlated-subquery
SQL and its NOT NULL step goes through ``batch_alter_table``, so the same code runs
on SQLite here and on Postgres in production.
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "d4f6b8c0e2a3_add_user_id_to_review_items_quiz_attempts.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("review_quiz_user_id_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


@pytest.fixture
def engine():
    eng = sa.create_engine("sqlite://")
    meta = sa.MetaData()
    sa.Table("users", meta, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table(
        "courses",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "lecture_artifacts",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "summaries",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "quiz_questions",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "quiz_attempts",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("quiz_question_id", sa.String(36), nullable=False),
    )
    sa.Table(
        "review_items",
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
    )
    meta.create_all(eng)
    return eng


def _exec(engine, sql):
    with engine.begin() as conn:
        conn.execute(sa.text(sql))


def _seed_owned(engine):
    _exec(engine, "INSERT INTO users VALUES ('u1'), ('u2')")
    _exec(engine, "INSERT INTO courses VALUES ('c1','u1'), ('c2','u2')")
    _exec(engine, "INSERT INTO lecture_artifacts VALUES ('a1','u1'), ('a2','u2')")
    _exec(engine, "INSERT INTO summaries VALUES ('s1','c2')")
    _exec(engine, "INSERT INTO quiz_questions VALUES ('q1','c1'), ('q2','c2')")
    _exec(engine, "INSERT INTO quiz_attempts VALUES ('t1','q1'), ('t2','q2'), ('t3','q2')")
    _exec(
        engine,
        "INSERT INTO review_items VALUES "
        "('r1','lecture_artifact','a1'), ('r2','lecture_artifact','a2'), ('r3','summary','s1')",
    )


def _run(engine, migration, direction):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(migration, direction)()


def _owners(engine, table):
    with engine.connect() as conn:
        return dict(conn.execute(sa.text(f"SELECT id, user_id FROM {table}")).fetchall())


def _columns(engine, table):
    return {c["name"]: c for c in sa.inspect(engine).get_columns(table)}


class TestBackfill:
    def test_quiz_attempts_take_the_owner_of_their_question_course(self, engine, migration):
        _seed_owned(engine)
        _run(engine, migration, "upgrade")
        assert _owners(engine, "quiz_attempts") == {"t1": "u1", "t2": "u2", "t3": "u2"}

    def test_review_items_take_the_owner_of_their_entity(self, engine, migration):
        _seed_owned(engine)
        _run(engine, migration, "upgrade")
        assert _owners(engine, "review_items") == {"r1": "u1", "r2": "u2", "r3": "u2"}

    def test_fully_owned_tables_become_not_null(self, engine, migration):
        _seed_owned(engine)
        _run(engine, migration, "upgrade")
        assert _columns(engine, "quiz_attempts")["user_id"]["nullable"] is False
        assert _columns(engine, "review_items")["user_id"]["nullable"] is False

    def test_empty_tables_become_not_null(self, engine, migration):
        _run(engine, migration, "upgrade")
        assert _columns(engine, "review_items")["user_id"]["nullable"] is False


class TestOrphans:
    def test_orphan_review_item_is_kept_and_column_stays_nullable(self, engine, migration):
        _seed_owned(engine)
        _exec(engine, "INSERT INTO review_items VALUES ('r9','lecture_artifact','gone')")
        _exec(engine, "INSERT INTO review_items VALUES ('r8','mystery_type','a1')")
        _run(engine, migration, "upgrade")

        owners = _owners(engine, "review_items")
        assert owners["r9"] is None
        assert owners["r8"] is None
        assert owners["r1"] == "u1"
        assert len(owners) == 5  # nothing deleted
        assert _columns(engine, "review_items")["user_id"]["nullable"] is True
        # quiz_attempts is provably orphan-free, so it is still tightened.
        assert _columns(engine, "quiz_attempts")["user_id"]["nullable"] is False


class TestRoundTrip:
    def test_downgrade_drops_columns_and_indexes(self, engine, migration):
        _seed_owned(engine)
        _run(engine, migration, "upgrade")
        _run(engine, migration, "downgrade")
        for table in ("review_items", "quiz_attempts"):
            assert "user_id" not in _columns(engine, table)
            names = {i["name"] for i in sa.inspect(engine).get_indexes(table)}
            assert f"ix_{table}_user_id" not in names
        assert len(_owners(engine, "review_items")) == 3

    def test_up_down_up_on_populated_database(self, engine, migration):
        _seed_owned(engine)
        _run(engine, migration, "upgrade")
        _run(engine, migration, "downgrade")
        _run(engine, migration, "upgrade")
        assert _owners(engine, "quiz_attempts") == {"t1": "u1", "t2": "u2", "t3": "u2"}
        assert _owners(engine, "review_items") == {"r1": "u1", "r2": "u2", "r3": "u2"}

    def test_user_id_is_indexed_after_upgrade(self, engine, migration):
        _run(engine, migration, "upgrade")
        for table, name in (
            ("review_items", "ix_review_items_user_id"),
            ("quiz_attempts", "ix_quiz_attempts_user_id"),
        ):
            assert name in {i["name"] for i in sa.inspect(engine).get_indexes(table)}
