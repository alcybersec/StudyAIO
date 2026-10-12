"""Contract test for `models.weakspot v1` (docs/CONTRACTS.md, ADR 0007 Decision 6).

Compares the entry's column table with the ORM metadata (``app.models``, owner
``data``): each listed column exists with the listed type, nullability and
foreign key. Also pins what the table cannot say in one row:

* both new tables carry ``user_id NOT NULL`` → ``users.id`` (floor 1);
* ``study_plans`` is unique on ``(user_id, plan_date)``: one plan per local day;
* ``targeted_generations`` has a **partial** unique index on
  ``(user_id, course_id, week, kind)`` limited to in-flight rows, so two
  concurrent requests cannot both enqueue;
* ``origin`` defaults to ``'pipeline'`` in the database, so existing items
  backfill without a data migration;
* the scoring query's index on ``quiz_attempts (quiz_question_id, created_at)``.

The migration itself (single head, upgrade/downgrade on pg16) is ``data``'s and
``qa``'s to test; this file pins the shape both sides code against.

Red until ``data`` lands the models and the migration (M33-S2-DATA-019).
"""

import re

import pytest
from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from tests.contracts._weakspot_docs import contract_section, table_rows

HEADING = "### models.weakspot v1"
NEW_TABLES = ("study_plans", "targeted_generations")


@pytest.fixture(scope="module")
def tables():
    import app.models  # noqa: F401  (registers every model on the metadata)
    from app.core.database import Base

    return Base.metadata.tables


@pytest.fixture(scope="module")
def rows() -> list[list[str]]:
    found = table_rows(contract_section(HEADING), "Table")
    assert len(found) >= 25, f"{HEADING} lists {len(found)} columns; expected the full table"
    return found


def _type_matches(column, spec: str) -> bool:
    """Whether a column's type is the entry's ``Type`` cell (FK suffix ignored)."""
    spec = spec.split(" FK ")[0].strip("`")
    t = column.type
    if m := re.fullmatch(r"String\((\d+)\)", spec):
        return isinstance(t, String) and t.length == int(m.group(1))
    if spec == "Integer":
        return isinstance(t, Integer)
    if spec == "Date":
        return isinstance(t, Date) and not isinstance(t, DateTime)
    if spec == "JSONB":
        return isinstance(t, JSONB)
    if spec == "DateTime(timezone=True)":
        return isinstance(t, DateTime) and t.timezone is True
    raise AssertionError(f"unrecognised type spec in {HEADING}: {spec!r}")


def _fk_target(spec: str) -> str | None:
    m = re.search(r"FK `?([a-z_]+\.[a-z_]+)`?", spec)
    return m.group(1) if m else None


def test_new_tables_exist(tables):
    missing = [t for t in NEW_TABLES if t not in tables]
    assert not missing, f"tables not on the metadata yet: {missing} (`data` adds them)"


def test_columns_match_the_entry(tables, rows):
    problems = []
    for table, column, type_spec, null, _notes in rows:
        table, column = table.strip("`"), column.strip("`")
        if table not in tables:
            problems.append(f"{table}: table missing")
            continue
        col = tables[table].columns.get(column)
        if col is None:
            problems.append(f"{table}.{column}: column missing")
            continue
        if not _type_matches(col, type_spec):
            problems.append(f"{table}.{column}: type {col.type!r} is not {type_spec}")
        if col.nullable != (null == "yes"):
            problems.append(f"{table}.{column}: nullable={col.nullable}, entry says {null!r}")
        target = _fk_target(type_spec)
        if target and target not in {fk.target_fullname for fk in col.foreign_keys}:
            problems.append(f"{table}.{column}: no FK to {target}")
    assert not problems, f"{HEADING} disagrees with the models:\n" + "\n".join(problems)


@pytest.mark.parametrize("table", NEW_TABLES)
def test_new_tables_are_user_owned(tables, table):
    assert table in tables, f"{table} not on the metadata yet"
    user_id = tables[table].columns.get("user_id")
    assert user_id is not None and user_id.nullable is False, f"{table}.user_id (floor 1)"
    assert "users.id" in {fk.target_fullname for fk in user_id.foreign_keys}
    for name in ("id", "created_at", "updated_at"):
        assert name in tables[table].columns, f"{table}.{name}"


def _unique_column_sets(table) -> list[set[str]]:
    sets = [
        {c.name for c in con.columns}
        for con in table.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    sets += [{c.name for c in ix.columns} for ix in table.indexes if ix.unique]
    return sets


def test_one_plan_per_user_per_local_day(tables):
    assert "study_plans" in tables, "study_plans not on the metadata yet"
    assert {"user_id", "plan_date"} in _unique_column_sets(tables["study_plans"])


def test_in_flight_generation_is_unique(tables):
    assert "targeted_generations" in tables, "targeted_generations not on the metadata yet"
    partial = [
        ix
        for ix in tables["targeted_generations"].indexes
        if ix.unique
        and {c.name for c in ix.columns} == {"user_id", "course_id", "week", "kind"}
        and ix.dialect_options["postgresql"].get("where") is not None
    ]
    assert partial, "no partial unique index on (user_id, course_id, week, kind) for in-flight rows"
    where = str(partial[0].dialect_options["postgresql"]["where"])
    assert "queued" in where and "running" in where, where


def test_daily_cap_index(tables):
    assert "targeted_generations" in tables, "targeted_generations not on the metadata yet"
    cols = [[c.name for c in ix.columns] for ix in tables["targeted_generations"].indexes]
    assert ["user_id", "created_at"] in cols


@pytest.mark.parametrize("table", ["quiz_questions", "flashcards"])
def test_origin_defaults_to_pipeline_in_the_database(tables, table):
    origin = tables[table].columns.get("origin")
    assert origin is not None, f"{table}.origin missing"
    assert origin.server_default is not None, f"{table}.origin has no server default"
    assert "pipeline" in str(origin.server_default.arg), origin.server_default.arg


def test_scoring_index_on_attempts(tables):
    cols = [[c.name for c in ix.columns] for ix in tables["quiz_attempts"].indexes]
    assert ["quiz_question_id", "created_at"] in cols, (
        "quiz_attempts needs an index on (quiz_question_id, created_at) for the scoring query"
    )
