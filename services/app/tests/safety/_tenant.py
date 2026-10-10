"""Helpers for the floor-1 sweep: which tables are user-owned, and is a statement scoped.

A table is *user-owned* when it carries a ``user_id`` column, or when a foreign
key reaches a user-owned table (``summaries`` -> ``courses``, ``chunks`` ->
``lecture_artifacts``). ``review_items`` points at its subject polymorphically
(``entity_type`` + ``entity_id``) with no foreign key, so it is named by hand.

Tables that belong to nobody are pinned in ``UNOWNED_TABLES``; a new table must
land in one set or the other (``test_floor1_every_table_is_classified``), so a
user-owned table that carries neither a ``user_id`` nor a foreign key cannot
slip past the sweep unnoticed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Table
from sqlalchemy.sql import operators, visitors
from sqlalchemy.sql.elements import (
    BinaryExpression,
    BindParameter,
    BooleanClauseList,
    UnaryExpression,
)

#: Shared catalogues and the accounts table itself.
UNOWNED_TABLES = frozenset({"users", "invite_codes", "achievements", "daily_challenges"})

#: Owned, but with no foreign key a closure over the schema could follow.
POLYMORPHIC_OWNED = frozenset({"review_items"})


def all_tables() -> dict[str, Any]:
    """Every mapped table, keyed by name."""
    import app.models  # noqa: F401  (registers every model on Base.metadata)
    from app.core.database import Base

    return dict(Base.metadata.tables)


def user_owned_tables() -> frozenset[str]:
    """Tables with a ``user_id`` column, closed over foreign keys."""
    tables = all_tables()
    owned = {n for n, t in tables.items() if "user_id" in t.c} | set(POLYMORPHIC_OWNED)
    changed = True
    while changed:
        changed = False
        for name, table in tables.items():
            if name in owned or name in UNOWNED_TABLES:
                continue
            if any(fk.column.table.name in owned for col in table.c for fk in col.foreign_keys):
                owned.add(name)
                changed = True
    return frozenset(owned)


def tables_in(statement: Any) -> set[str]:
    """Names of every table a statement references (FROM, JOIN, subqueries, DML target)."""
    names = set()
    for element in visitors.iterate(statement):
        if isinstance(element, Table):  # includes ORM-annotated tables
            names.add(element.name)
    return names


def filters_by_id_list(statement: Any) -> bool:
    """True if the statement filters with ``<column> IN (<bound list>)``."""
    for element in visitors.iterate(statement):
        if (
            isinstance(element, BinaryExpression)
            and element.operator is operators.in_op
            and isinstance(element.right, BindParameter)
        ):
            return True
    return False


def _compares_to_caller(element: Any, user_id: str) -> bool:
    """``<table>.user_id = :caller`` or ``<table>.user_id IN (:caller)``, nothing looser."""
    if not isinstance(element, BinaryExpression):
        return False
    if element.operator not in (operators.eq, operators.in_op):
        return False  # !=, NOT IN, <, ...: the caller's id excluded, or not pinned
    for column, other in ((element.left, element.right), (element.right, element.left)):
        if getattr(column, "name", None) != "user_id" or not isinstance(other, BindParameter):
            continue
        value = other.effective_value
        if value == user_id:
            return True
        if isinstance(value, list | tuple | set | frozenset):
            # IN (:caller, :victim) admits the victim's rows too.
            return bool(value) and all(v == user_id for v in value)
    return False


def _widening(element: Any) -> bool:
    """An OR, or a NOT, under which a caller comparison no longer constrains the rows."""
    if isinstance(element, BooleanClauseList):
        return element.operator is operators.or_
    return isinstance(element, UnaryExpression) and element.operator is operators.inv


def filters_on_user(statement: Any, user_id: str) -> bool:
    """True if some ``<table>.user_id = :caller`` constrains the rows the statement touches.

    Accepts ``= :p`` and ``IN (:p)`` where every value is the caller. A
    comparison to some *other* user's id does not count — that is the bug. Nor
    does one that only *widens*: under an ``OR`` (``user_id = :caller OR
    public``) or a ``NOT`` it constrains nothing, unless every branch of the
    ``OR`` is itself caller-scoped. Subqueries are searched too, as before:
    ``course_id IN (SELECT id FROM courses WHERE user_id = :caller)`` counts.
    """
    shadowed: set[int] = set()
    for element in visitors.iterate(statement):
        if not _widening(element):
            continue
        if isinstance(element, BooleanClauseList) and all(
            filters_on_user(clause, user_id) for clause in element.clauses
        ):
            return True
        shadowed |= {id(inner) for inner in visitors.iterate(element)}
    return any(
        id(element) not in shadowed and _compares_to_caller(element, user_id)
        for element in visitors.iterate(statement)
    )


def inserts_for_caller(statement: Any, user_id: str) -> bool:
    """True if ``statement`` is an INSERT that writes only rows owned by the caller.

    Every ``user_id`` value it inserts (each row of a multi-row VALUES) must be
    the caller; an ``INSERT ... SELECT`` has no literal owner and never counts.
    An ``ON CONFLICT DO UPDATE`` counts only when its conflict target is a
    unique key that includes ``user_id`` and it has no extra ``WHERE``: then
    the conflicting row, the only one it can update, has the caller's id too.
    GL#19 made ``record_usage`` such an upsert on ``uq_usage_user_date``.
    """
    import re

    from sqlalchemy.dialects import postgresql
    from sqlalchemy.sql.dml import Insert

    if not isinstance(statement, Insert) or getattr(statement, "select", None) is not None:
        return False
    if "user_id" not in statement.table.c:
        return False
    params = statement.compile(dialect=postgresql.dialect()).params
    owners = [v for k, v in params.items() if re.fullmatch(r"user_id(_m\d+)?", k)]
    if not owners or any(v != user_id for v in owners):
        return False
    conflict = getattr(statement, "_post_values_clause", None)
    if conflict is None:
        return True
    if getattr(conflict, "update_whereclause", None) is not None:
        return False
    target = getattr(conflict, "constraint_target", None)
    if isinstance(target, str):
        keys = [
            {c.name for c in con.columns}
            for con in statement.table.constraints
            if getattr(con, "name", None) == target and hasattr(con, "columns")
        ]
        keys += [
            {c.name for c in ix.columns} for ix in statement.table.indexes if ix.name == target
        ]
        cols = keys[0] if keys else set()
    else:
        cols = {getattr(e, "name", e) for e in (conflict.inferred_target_elements or [])}
    return "user_id" in cols


def bind_values(statement: Any) -> list[Any]:
    """Every bound value in a statement, ``IN`` lists flattened."""
    values: list[Any] = []
    for element in visitors.iterate(statement):
        if isinstance(element, BindParameter):
            value = element.effective_value
            if isinstance(value, list | tuple | set | frozenset):
                values.extend(value)
            else:
                values.append(value)
    return values


def primary_key_values(statement: Any) -> set[Any]:
    """Values a statement pins a primary-key column to (``= :p`` or ``IN (...)``).

    Only a primary key identifies one row. A caller-scoped lookup by
    ``courses.code`` proves the caller has *a* course with that code, not that
    every row carrying the code is theirs, so codes are never vetted.
    """
    found: set[Any] = set()
    for element in visitors.iterate(statement):
        if not isinstance(element, BinaryExpression):
            continue
        for column, other in ((element.left, element.right), (element.right, element.left)):
            if not getattr(column, "primary_key", False) or not isinstance(other, BindParameter):
                continue
            value = other.effective_value
            if isinstance(value, list | tuple | set | frozenset):
                found.update(value)
            elif value is not None:
                found.add(value)
    return found


def is_planted(value: Any) -> bool:
    """True if ``value`` is one the sweep planted in a request (see ``_payload``).

    A ``str`` slot with a ``max_length`` holds a truncated FOREIGN_ID, so any
    prefix of four characters or more counts.
    """
    from tests.safety._payload import FOREIGN_ID, FOREIGN_INT, FOREIGN_UUID

    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == FOREIGN_INT
    if value == FOREIGN_UUID:
        return True
    if isinstance(value, str):
        return value == str(FOREIGN_UUID) or (len(value) >= 4 and FOREIGN_ID.startswith(value))
    return False
