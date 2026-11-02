"""Floor 1 — ``review_items`` and ``quiz_attempts`` are owned by their own ``user_id``.

R-010 (M35-R010). Until migration ``d4f6b8c0e2a3`` both tables were scoped only
through joins: ``review_items`` through the polymorphic ``entity_type`` +
``entity_id`` pair (``review_service._owned_by``), ``quiz_attempts`` through
``quiz_questions`` -> ``courses.user_id``. A join-scoped table is one dropped
join away from a leak, and the route sweep accepts a ``user_id`` comparison
*anywhere* in the statement, so it cannot tell a direct predicate from one on a
joined parent. These pins hold the tables to the stricter rule:

* the column exists, is ``NOT NULL`` in the model and is a ``CASCADE`` FK to
  ``users.id`` (``test_floor1_r010_tables_carry_their_own_user_id``);
* every ``select``/``update``/``delete`` in ``app/`` that names either model
  carries a predicate on *that model's own* ``user_id`` compared to a value, in
  the statement itself or in a ``.where`` on the variable it was assigned to
  (``test_floor1_r010_every_statement_filters_its_own_user_id``);
* every constructor call sets ``user_id`` (an insert always has an owner);
* no raw SQL string reads or writes either table.

Legacy ``review_items`` rows the migration could not attribute keep a NULL
``user_id``. ``user_id = :caller`` never matches NULL, so they are invisible to
every user: fail-closed, pinned behaviourally in
``tests/integration/test_user_id_ownership.py``.
"""

from __future__ import annotations

import ast
import re

import pytest

from tests.safety._source import app_modules, parse, rel, walk_with_scope
from tests.safety._tenant import POLYMORPHIC_OWNED, all_tables, user_owned_tables

#: Table name -> model class name.
R010_TABLES = {"review_items": "ReviewItem", "quiz_attempts": "QuizAttempt"}

#: Statement builders called by bare name (``from sqlalchemy import select``) or
#: through a module alias (``sa.select``).
BUILDERS = frozenset({"select", "update", "delete", "sa_delete", "sa_update"})
BUILDER_MODULES = frozenset({"sa", "sqlalchemy"})

#: Chain methods that continue a statement stored in a variable.
CONTINUATIONS = frozenset({"where", "filter", "join", "outerjoin"})

#: Below this many statement sites the scan has stopped seeing the code.
MIN_SITES = 15

#: The model modules define the tables; nothing there queries them.
EXCLUDED = ("app/models/",)


# ── schema ─────────────────────────────────────────────────────────────


def test_floor1_r010_tables_carry_their_own_user_id():
    """Both tables have ``user_id`` NOT NULL, FK ``users.id`` ON DELETE CASCADE."""
    tables = all_tables()
    for name in R010_TABLES:
        table = tables[name]
        assert "user_id" in table.c, f"{name} lost its user_id column (R-010)"
        column = table.c.user_id
        assert column.nullable is False, f"{name}.user_id is nullable in the model"
        targets = {
            (fk.column.table.name, fk.column.name, fk.ondelete) for fk in column.foreign_keys
        }
        assert targets == {("users", "id", "CASCADE")}, f"{name}.user_id FK: {targets}"
        assert any([c.name for c in ix.columns] == ["user_id"] for ix in table.indexes), (
            f"{name}.user_id has no index; every read filters on it"
        )


def test_floor1_r010_tables_are_directly_owned_not_polymorphic():
    """The sweep classifies both tables by their own column, not a hand-kept list."""
    owned = user_owned_tables()
    for name in R010_TABLES:
        assert name in owned
        assert name not in POLYMORPHIC_OWNED, (
            f"{name} has its own user_id; drop it from POLYMORPHIC_OWNED"
        )
    tables = all_tables()
    stale = sorted(n for n in POLYMORPHIC_OWNED if "user_id" in tables[n].c)
    assert not stale, f"POLYMORPHIC_OWNED names tables that carry user_id: {stale}"


# ── static scan ────────────────────────────────────────────────────────


def _aliases(tree: ast.Module) -> dict[str, str]:
    """Local name -> R-010 model name, through ``from app.models... import X as Y``."""
    models = set(R010_TABLES.values())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.models"):
            for alias in node.names:
                if alias.name in models:
                    found[alias.asname or alias.name] = alias.name
    return found


def _base(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _is_builder(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in BUILDERS
    return (
        isinstance(func, ast.Attribute)
        and func.attr in BUILDERS
        and isinstance(func.value, ast.Name)
        and func.value.id in BUILDER_MODULES
    )


def _models_in(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    return {aliases[n.id] for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in aliases}


def _own_user_id(node: ast.AST, alias_of: dict[str, str], model: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "user_id"
        and isinstance(node.value, ast.Name)
        and alias_of.get(node.value.id) == model
    )


def _is_model_column(node: ast.AST, all_models: set[str]) -> bool:
    return isinstance(node, ast.Attribute) and _base(node) in all_models


def _has_predicate(
    tree: ast.AST, alias_of: dict[str, str], model: str, all_models: set[str]
) -> bool:
    """``Model.user_id == <value>`` / ``.in_(<value>)`` somewhere under ``tree``.

    The other side must not be another model's column: ``QuizAttempt.user_id ==
    Course.user_id`` is a join condition, not a filter.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if not isinstance(node.ops[0], ast.Eq | ast.In):
                continue
            left, right = node.left, node.comparators[0]
            for col, other in ((left, right), (right, left)):
                if _own_user_id(col, alias_of, model) and not _is_model_column(other, all_models):
                    return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "in_"
            and _own_user_id(node.func.value, alias_of, model)
            and node.args
            and not _is_model_column(node.args[0], all_models)
        ):
            return True
    return False


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _chain_root(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST:
    """Climb ``select(...).join(...).where(...)`` to the outermost call of the chain."""
    while True:
        parent = parents.get(id(node))
        attribute_of = isinstance(parent, ast.Attribute) and parent.value is node
        called = isinstance(parent, ast.Call) and parent.func is node
        if not (attribute_of or called):
            return node
        node = parent


def _continuations(function: ast.AST, name: str) -> list[ast.AST]:
    """``name.where(...)`` / ``.filter`` / ``.join`` calls on a statement variable."""
    found = []
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in CONTINUATIONS
            and _base(node.func) == name
        ):
            found.append(node)
    return found


def _all_model_names() -> set[str]:
    from app.core.database import Base

    all_tables()  # registers every model
    return {mapper.class_.__name__ for mapper in Base.registry.mappers}


def scan_tree(
    tree: ast.Module, module: str, all_models: set[str]
) -> tuple[list[str], list[str], int]:
    """Return (unscoped statements, constructors without user_id, statements seen)."""
    alias_of = _aliases(tree)
    if not alias_of:
        return [], [], 0
    model_names = all_models | set(alias_of)
    parents = _parents(tree)
    unscoped: list[str] = []
    ownerless: list[str] = []
    seen = 0
    functions = [
        (node, scope)
        for node, scope in walk_with_scope(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    for function, scope in functions:
        qualname = f"{scope}.{function.name}" if scope != "<module>" else function.name
        roots: dict[int, ast.AST] = {}
        for node in ast.walk(function):
            if _is_builder(node):
                root = _chain_root(node, parents)
                roots[id(root)] = root
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in alias_of
                and not any(k.arg == "user_id" for k in node.keywords)
            ):
                ownerless.append(
                    f"{module}:{node.lineno} in {qualname}(): {alias_of[node.func.id]}(...)"
                )
        for root in roots.values():
            for model in sorted(_models_in(root, alias_of)):
                seen += 1
                if _has_predicate(root, alias_of, model, model_names):
                    continue
                parent = parents.get(id(root))
                target = (
                    parent.targets[0]
                    if isinstance(parent, ast.Assign) and len(parent.targets) == 1
                    else None
                )
                if isinstance(target, ast.Name) and any(
                    _has_predicate(c, alias_of, model, model_names)
                    for c in _continuations(function, target.id)
                ):
                    continue
                unscoped.append(
                    f"{module}:{root.lineno} in {qualname}(): {model} with no {model}.user_id filter"
                )
    return unscoped, ownerless, seen


def _scan() -> tuple[list[str], list[str], int]:
    all_models = _all_model_names()
    unscoped: list[str] = []
    ownerless: list[str] = []
    seen = 0
    for path in app_modules(exclude=EXCLUDED):
        u, o, s = scan_tree(parse(path), rel(path), all_models)
        unscoped += u
        ownerless += o
        seen += s
    return unscoped, ownerless, seen


def test_floor1_r010_every_statement_filters_its_own_user_id():
    """No select/update/delete over either table without a direct ``user_id`` predicate.

    A predicate on a joined parent (``courses.user_id``) does not count: that
    is the join-scoping R-010 removed.
    """
    unscoped, _ownerless, seen = _scan()
    assert seen >= MIN_SITES, f"only {seen} statement sites found; the scan went blind"
    assert not unscoped, (
        "Floor 1 (R-010): statements over review_items / quiz_attempts must filter on "
        "the table's own user_id:\n  " + "\n  ".join(unscoped)
    )


def test_floor1_r010_every_insert_names_its_owner():
    """Every ``ReviewItem(...)`` / ``QuizAttempt(...)`` in ``app/`` passes ``user_id=``."""
    _unscoped, ownerless, _seen = _scan()
    assert not ownerless, "rows constructed without user_id:\n  " + "\n  ".join(ownerless)


_RAW_SQL = re.compile(r"\b(from|join|update|into)\s+(review_items|quiz_attempts)\b", re.IGNORECASE)


def test_floor1_r010_no_raw_sql_over_the_tables():
    """No string literal in ``app/`` is raw SQL over either table; the scan cannot read SQL."""
    hits = []
    for path in app_modules(exclude=EXCLUDED):
        for node in ast.walk(parse(path)):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _RAW_SQL.search(node.value)
            ):
                hits.append(f"{rel(path)}:{node.lineno}")
    assert not hits, f"raw SQL over review_items/quiz_attempts: {hits}"


# ── behaviour: legacy NULL-owner review items fail closed ──────────────

USER_A = "r010-user-a"
USER_B = "r010-user-b"


def _review_world():
    from app.models.review_item import ReviewItem
    from tests.safety._minidb import MiniDB

    db = MiniDB()
    for rid, owner in (("ri-a", USER_A), ("ri-b", USER_B), ("ri-legacy", None)):
        db.add(
            ReviewItem(
                id=rid,
                user_id=owner,
                review_type="classification",
                entity_type="lecture_artifact",
                entity_id=f"art-{rid}",
                status="pending",
                payload_json={},
                suggested_values={},
            )
        )
    return db


@pytest.mark.asyncio
async def test_floor1_r010_null_owner_review_item_is_invisible_to_every_user():
    """A legacy row with ``user_id IS NULL`` is listed, counted and opened for nobody.

    Positive control: each user still sees exactly their own item, so the pin
    cannot pass on a query that returns nothing.
    """
    from app.services import review_service
    from tests.safety._minidb import MiniSession

    db = _review_world()
    for caller, own in ((USER_A, "ri-a"), (USER_B, "ri-b")):
        session = MiniSession(db)
        listed = await review_service.list_pending_reviews(session, user_id=caller)
        assert [r.id for r in listed] == [own]
        assert await review_service.count_pending_reviews(session, user_id=caller) == 1
        assert (await review_service.get_review_item(session, own, user_id=caller)).id == own
        for foreign in ("ri-legacy", "ri-b" if caller == USER_A else "ri-a"):
            assert await review_service.get_review_item(session, foreign, user_id=caller) is None
            with pytest.raises(ValueError, match="not found"):
                await review_service.dismiss_review_item(session, foreign, user_id=caller)
    assert {r.id: r.status for r in db.rows["review_items"]}["ri-legacy"] == "pending"


# ── the scan is not vacuous ────────────────────────────────────────────

_SAMPLE = """
from sqlalchemy import delete, select, update
from app.models.course import Course
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.review_item import ReviewItem as RI


async def scoped(session, user_id):
    await session.execute(select(RI).where(RI.user_id == user_id))


async def scoped_later(session, user_id):
    q = select(RI).where(RI.status == "pending")
    q = q.where(RI.user_id == user_id)
    await session.execute(q)


async def outer_scoped(session, user_id):
    await session.execute(
        select(QuizQuestion).outerjoin(
            QuizAttempt, (QuizAttempt.quiz_question_id == QuizQuestion.id)
            & (QuizAttempt.user_id == user_id)
        )
    )


async def join_scoped(session, user_id):
    await session.execute(
        select(QuizAttempt.id)
        .join(QuizQuestion, QuizQuestion.id == QuizAttempt.quiz_question_id)
        .join(Course, Course.id == QuizQuestion.course_id)
        .where(Course.user_id == user_id)
    )


async def unscoped_delete(session, ids):
    await session.execute(delete(RI).where(RI.entity_id.in_(ids)))


async def join_condition_only(session, user_id):
    await session.execute(
        update(QuizAttempt).where(QuizAttempt.user_id == Course.user_id, Course.user_id == user_id)
    )


async def scoped_other_statement(session, user_id):
    await session.execute(select(RI).where(RI.user_id == user_id))
    await session.execute(select(RI.id))


def ownerless():
    return RI(id="x", entity_id="y")
"""


def test_floor1_r010_scan_flags_what_it_must():
    """Join-scoped, unscoped, join-condition-only and second statements are each caught."""
    unscoped, ownerless, seen = scan_tree(
        ast.parse(_SAMPLE), "sample.py", {"Course", "QuizQuestion"}
    )
    flagged = {line.split(" in ")[1].split("()")[0] for line in unscoped}
    assert flagged == {
        "join_scoped",
        "unscoped_delete",
        "join_condition_only",
        "scoped_other_statement",
    }, unscoped
    assert seen == 8
    assert len(ownerless) == 1 and "ownerless()" in ownerless[0]
