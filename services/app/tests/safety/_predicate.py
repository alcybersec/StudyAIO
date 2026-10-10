"""Decide which rows a SQL statement would return, without a database.

The floor-1 sweep asks "does this statement compare ``user_id`` to the
caller?". A deliberate cross-user read such as the opt-in leaderboard needs a
different question: "for a row with *these* values, does the statement keep
it?". :func:`admits` answers that by evaluating the statement's WHERE clause
and its joins against a row given as ``{(table, column): value}``, with SQL's
three-valued logic (``None`` is NULL).

Only the constructs below are understood. Anything else raises
:class:`Unreadable`, so a test built on this fails loudly when the code moves
past the evaluator instead of passing on a guess.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from sqlalchemy import Table
from sqlalchemy.sql import operators as ops
from sqlalchemy.sql.elements import (
    AsBoolean,
    BinaryExpression,
    BindParameter,
    BooleanClauseList,
    Cast,
    ColumnElement,
    False_,
    Grouping,
    Label,
    Null,
    True_,
    UnaryExpression,
)
from sqlalchemy.sql.functions import Function
from sqlalchemy.sql.selectable import Join, ScalarSelect, Select

Row = dict[tuple[str, str], Any]

#: When set, an ``IN (SELECT ...)`` is answered by running the subquery
#: against a whole table set (``tests/safety/_minidb.py``) instead of against
#: the one-row-per-table model below.
SUBQUERY: ContextVar[Callable[[Select], list[Any]] | None] = ContextVar("SUBQUERY", default=None)


class Unreadable(Exception):  # noqa: N818  (a verdict, not an error the code raised)
    """The statement uses a construct this evaluator does not model."""


_COMPARE = {
    ops.eq: operator.eq,
    ops.ne: operator.ne,
    ops.gt: operator.gt,
    ops.ge: operator.ge,
    ops.lt: operator.lt,
    ops.le: operator.le,
}


def _and(values: list[Any]) -> Any:
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def _or(values: list[Any]) -> Any:
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return False


def _not(value: Any) -> Any:
    return None if value is None else not value


def value(expr: Any, row: Row) -> Any:
    """The value ``expr`` takes on ``row`` (``None`` for NULL)."""
    if isinstance(expr, Grouping | Label):
        return value(expr.element, row)
    if isinstance(expr, Cast):
        return value(expr.clause, row)
    if isinstance(expr, BindParameter):
        return expr.effective_value
    if isinstance(expr, True_):
        return True
    if isinstance(expr, False_):
        return False
    if isinstance(expr, Null):
        return None
    if isinstance(expr, BooleanClauseList):
        parts = [value(c, row) for c in expr.clauses]
        if expr.operator is ops.and_:
            return _and(parts)
        if expr.operator is ops.or_:
            return _or(parts)
        raise Unreadable(f"boolean list with operator {expr.operator}")
    if isinstance(expr, AsBoolean):
        inner = value(expr.element, row)
        return inner if expr.operator is ops.is_true else _not(inner)
    if isinstance(expr, UnaryExpression):
        if expr.operator is ops.inv:
            return _not(value(expr.element, row))
        raise Unreadable(f"unary {expr.operator}/{expr.modifier}")
    if isinstance(expr, Function) and expr.name.lower() == "coalesce":
        for clause in expr.clauses:
            v = value(clause, row)
            if v is not None:
                return v
        return None
    if isinstance(expr, BinaryExpression):
        return _binary(expr, row)
    table = getattr(expr, "table", None)
    if isinstance(expr, ColumnElement) and isinstance(table, Table):
        key = (table.name, expr.name)
        if key not in row:
            raise Unreadable(f"column {key[0]}.{key[1]} has no value in the row model")
        return row[key]
    raise Unreadable(f"{type(expr).__name__}: {expr}")


def _binary(expr: BinaryExpression, row: Row) -> Any:
    op = expr.operator
    left = value(expr.left, row)
    if op in (ops.in_op, ops.not_in_op):
        members = _members(expr.right, row)
        if left is None:
            return None
        hit = left in members
        return hit if op is ops.in_op else not hit
    right = value(expr.right, row)
    if op is ops.is_:
        return left == right if None not in (left, right) else left is right
    if op is ops.is_not:
        return not (left == right if None not in (left, right) else left is right)
    if op in _COMPARE:
        if left is None or right is None:
            return None
        return _COMPARE[op](left, right)
    raise Unreadable(f"binary operator {op}")


def _members(expr: Any, row: Row) -> list[Any]:
    """Right side of IN: a bound list, or a correlated single-column subquery."""
    if isinstance(expr, Grouping):
        expr = expr.element
    if isinstance(expr, BindParameter):
        v = expr.effective_value
        return list(v) if isinstance(v, list | tuple | set | frozenset) else [v]
    if isinstance(expr, ScalarSelect):
        expr = expr.element
    if isinstance(expr, Select) and (resolve := SUBQUERY.get()) is not None:
        return resolve(expr)
    if isinstance(expr, Select):
        # The row model is one row per table, so the subquery returns its
        # selected column from this row when its own predicate keeps it.
        if not admits(expr, row):
            return []
        cols = list(expr.selected_columns)
        if len(cols) != 1:
            raise Unreadable("IN subquery selecting more than one column")
        return [value(cols[0], row)]
    raise Unreadable(f"IN over {type(expr).__name__}")


def _apply_joins(from_: Any, row: Row) -> tuple[Row, list[Any]]:
    """Null out the right side of an unmatched outer join; collect inner ON clauses."""
    inner: list[Any] = []
    if isinstance(from_, Join):
        row, left_inner = _apply_joins(from_.left, row)
        row, right_inner = _apply_joins(from_.right, row)
        inner += left_inner + right_inner
        if from_.isouter:
            if value(from_.onclause, row) is not True:
                right = from_.right
                if not isinstance(right, Table):
                    raise Unreadable(f"outer join to {type(right).__name__}")
                row = {k: (None if k[0] == right.name else v) for k, v in row.items()}
        else:
            inner.append(from_.onclause)
    return row, inner


def admits(statement: Select, row: Row) -> bool:
    """True if ``statement`` would return ``row``: every inner ON and the WHERE are true."""
    if not isinstance(statement, Select):
        raise Unreadable(f"{type(statement).__name__} is not a SELECT")
    conditions: list[Any] = []
    for from_ in statement.get_final_froms():
        row, inner = _apply_joins(from_, row)
        conditions += inner
    if statement.whereclause is not None:
        conditions.append(statement.whereclause)
    return _and([value(c, row) for c in conditions]) is True
