"""An in-memory table set that answers SQLAlchemy statements like a database.

Floor tests that follow user data through several real service calls (create,
merge, delete a course, delete the account) need a session whose answers
depend on what earlier calls wrote. A ``MagicMock`` session answers every
query the same way, which is how floor pins have passed vacuously before
(``mock_session`` answering counts with a truthy mock).

:class:`MiniDB` keeps ORM instances per table and evaluates each statement's
WHERE clause row by row with :func:`tests.safety._predicate.admits`, so the
answer is the one Postgres would give for the constructs it models: SELECT
over one table or inner joins, ``IN`` over a list or an uncorrelated
subquery, ORDER BY, LIMIT, ``count()``, and DELETE, UPDATE and INSERT.
Anything else raises :class:`~tests.safety._predicate.Unreadable`, so a test
built on this fails loudly when the code moves past it instead of passing on
a guess. Constraints and foreign keys are not enforced.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Table
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.elements import ColumnElement, UnaryExpression
from sqlalchemy.sql.functions import Function
from sqlalchemy.sql.selectable import Join, Select

from tests.safety._predicate import SUBQUERY, Row, Unreadable, admits, value


def _model_for_table() -> dict[str, type]:
    import app.models  # noqa: F401  (registers every model)
    from app.core.database import Base

    return {m.class_.__table__.name: m.class_ for m in Base.registry.mappers}


def _tables_of(from_: Any) -> list[Table]:
    if isinstance(from_, Join):
        if from_.isouter:
            raise Unreadable("outer join")
        return _tables_of(from_.left) + _tables_of(from_.right)
    if isinstance(from_, Table):
        return [from_]
    raise Unreadable(f"FROM {type(from_).__name__}")


def _attr_keys(model: type) -> dict[str, str]:
    """Column name -> mapped attribute key (``metadata`` -> ``metadata_``)."""
    mapper = sa_inspect(model)
    return {col.name: prop.key for prop in mapper.column_attrs for col in prop.columns}


class Result:
    """The subset of ``sqlalchemy.engine.Result`` the services use."""

    def __init__(self, rows: list[tuple], rowcount: int | None = None) -> None:
        self._rows = rows
        self.rowcount = len(rows) if rowcount is None else rowcount

    def __iter__(self):
        return iter(self._rows)

    def all(self) -> list[tuple]:
        return list(self._rows)

    def first(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    def one_or_none(self) -> tuple | None:
        if len(self._rows) > 1:
            raise AssertionError("MiniDB: one_or_none() matched more than one row")
        return self.first()

    def one(self) -> tuple:
        if len(self._rows) != 1:
            raise AssertionError(f"MiniDB: one() matched {len(self._rows)} rows")
        return self._rows[0]

    def scalars(self) -> Result:
        return Result([r[0] for r in self._rows])

    def scalar(self) -> Any:
        first = self.first()
        if first is None:
            return None
        return first[0] if isinstance(first, tuple) else first

    def scalar_one_or_none(self) -> Any:
        row = self.one_or_none()
        if row is None:
            return None
        return row[0] if isinstance(row, tuple) else row

    def scalar_one(self) -> Any:
        row = self.one()
        return row[0] if isinstance(row, tuple) else row


class MiniDB:
    """ORM instances per table, queried by evaluating statements row by row."""

    def __init__(self) -> None:
        self.rows: dict[str, list[Any]] = defaultdict(list)
        self.models = _model_for_table()

    # ── rows ──────────────────────────────────────────────────────────

    def row(self, obj: Any) -> Row:
        table = type(obj).__table__
        keys = _attr_keys(type(obj))
        return {(table.name, col.name): getattr(obj, keys[col.name], None) for col in table.columns}

    def add(self, obj: Any) -> None:
        table = type(obj).__table__
        bucket = self.rows[table.name]
        if any(o is obj for o in bucket):
            return
        keys = _attr_keys(type(obj))
        for col in table.columns:
            default = col.default
            if getattr(obj, keys[col.name], None) is None and default is not None:
                if default.is_scalar:
                    setattr(obj, keys[col.name], default.arg)
                elif default.is_callable:
                    setattr(obj, keys[col.name], default.arg(None))
        bucket.append(obj)

    def remove(self, obj: Any) -> None:
        bucket = self.rows[type(obj).__table__.name]
        bucket[:] = [o for o in bucket if o is not obj]

    def get(self, model: type, pk: Any) -> Any:
        pk_col = model.__table__.primary_key.columns.values()[0]
        key = _attr_keys(model)[pk_col.name]
        return next((o for o in self.rows[model.__table__.name] if getattr(o, key) == pk), None)

    # ── statements ────────────────────────────────────────────────────

    def execute(self, statement: Any) -> Result:
        if isinstance(statement, Select):
            return self._select(statement)
        if isinstance(statement, Delete):
            hits = self._matching(statement.table, statement.whereclause)
            for obj in hits:
                self.remove(obj)
            return Result([], rowcount=len(hits))
        if isinstance(statement, Update):
            hits = self._matching(statement.table, statement.whereclause)
            for obj in hits:
                row = self.row(obj)
                keys = _attr_keys(type(obj))
                for col, expr in (statement._values or {}).items():  # noqa: SLF001
                    name = getattr(col, "name", None) or getattr(col, "key", None) or str(col)
                    setattr(obj, keys[name], value(expr, row))
            return Result([], rowcount=len(hits))
        if isinstance(statement, Insert):
            if statement._multi_values or statement.select is not None:  # noqa: SLF001
                raise Unreadable("multi-row or INSERT ... SELECT")
            model = self.models[statement.table.name]
            keys = _attr_keys(model)
            values = {
                keys[getattr(c, "name", None) or str(c)]: value(v, {})
                for c, v in (statement._values or {}).items()  # noqa: SLF001
            }
            self.add(model(**values))
            return Result([], rowcount=1)
        raise Unreadable(f"statement {type(statement).__name__}")

    def _matching(self, table: Table, where: Any) -> list[Any]:
        probe = sa.select(table)
        if where is not None:
            probe = probe.where(where)
        return [objs[0] for _row, objs in self._candidates(probe)]

    def _resolve_subquery(self, statement: Select) -> list[Any]:
        return [r[0] for r in self._select(statement).all()]

    def _candidates(self, statement: Select) -> list[tuple[Row, tuple]]:
        tables = [t for f in statement.get_final_froms() for t in _tables_of(f)]
        out = []
        token = SUBQUERY.set(self._resolve_subquery)
        try:
            for combo in itertools.product(*(self.rows[t.name] for t in tables)):
                row: Row = {}
                for obj in combo:
                    row |= self.row(obj)
                if admits(statement, row):
                    out.append((row, combo))
        finally:
            SUBQUERY.reset(token)
        return out

    def _select(self, statement: Select) -> Result:
        if statement._group_by_clauses or statement._having_criteria:  # noqa: SLF001
            raise Unreadable("GROUP BY / HAVING")
        matches = self._candidates(statement)
        for clause in reversed(list(statement._order_by_clauses)):  # noqa: SLF001
            desc = (
                isinstance(clause, UnaryExpression) and clause.modifier is sa.sql.operators.desc_op
            )
            expr = clause.element if isinstance(clause, UnaryExpression) else clause
            matches.sort(
                key=lambda m, e=expr: (value(e, m[0]) is None, value(e, m[0])), reverse=desc
            )
        raw = list(statement._raw_columns)  # noqa: SLF001
        if any(isinstance(c, Function) and c.name.lower() == "count" for c in raw):
            if len(raw) != 1:
                raise Unreadable("count() beside other columns")
            return Result([(len(matches),)])
        rows = [tuple(self._project(c, row, combo) for c in raw) for row, combo in matches]
        limit = statement._limit  # noqa: SLF001
        if limit is not None:
            rows = rows[:limit]
        return Result(rows)

    def _project(self, column: Any, row: Row, combo: tuple) -> Any:
        if isinstance(column, Table):
            return next(o for o in combo if type(o).__table__.name == column.name)
        if not isinstance(column, ColumnElement):  # pragma: no cover - select() admits none
            raise Unreadable(f"selected {type(column).__name__}")
        return value(column, row)


class MiniSession:
    """An ``AsyncSession`` stand-in over a :class:`MiniDB`."""

    def __init__(self, db: MiniDB) -> None:
        self.db = db

    async def execute(self, statement: Any, *_a: Any, **_k: Any) -> Result:
        return self.db.execute(statement)

    async def scalar(self, statement: Any, *_a: Any, **_k: Any) -> Any:
        return self.db.execute(statement).scalar()

    async def get(self, model: type, pk: Any, *_a: Any, **_k: Any) -> Any:
        return self.db.get(model, pk)

    def add(self, obj: Any, *_a: Any, **_k: Any) -> None:
        self.db.add(obj)

    def add_all(self, objs: Any) -> None:
        for obj in objs:
            self.db.add(obj)

    async def delete(self, obj: Any) -> None:
        self.db.remove(obj)

    async def flush(self, *_a: Any, **_k: Any) -> None:
        return None
