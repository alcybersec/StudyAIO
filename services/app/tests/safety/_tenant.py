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
from sqlalchemy.sql.elements import BinaryExpression, BindParameter

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


def filters_on_user(statement: Any, user_id: str) -> bool:
    """True if some ``<table>.user_id`` is compared to a bind carrying ``user_id``.

    Accepts ``= :p`` and ``IN (:p, ...)`` whose value includes the caller. A
    comparison to some *other* user's id does not count — that is the bug.
    """
    for element in visitors.iterate(statement):
        if not isinstance(element, BinaryExpression):
            continue
        for column, other in ((element.left, element.right), (element.right, element.left)):
            if getattr(column, "name", None) != "user_id":
                continue
            if not isinstance(other, BindParameter):
                continue
            value = other.effective_value
            if value == user_id:
                return True
            if isinstance(value, list | tuple | set | frozenset) and user_id in value:
                return True
    return False


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
