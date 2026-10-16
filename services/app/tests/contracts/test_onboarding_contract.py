"""Contract test for `api.onboarding v1` (docs/CONTRACTS.md, M34-S3-BACKEND-012).

Server-side first-run status. Pins:

1. The entry's ``python`` block against ``app/services/onboarding_service.py``:
   the three constant tuples, the two frozen dataclasses field for field, and
   the three functions signature for signature (``user_id`` a required keyword).
2. The worked-examples table through the pure ``derive_status``, row by row.
3. The route table against ``app.main.app``; both routes resolve a caller;
   neither is consent-gated (neither spends AI).
4. ``users.onboarding_checklist`` is ``String(20)``, NOT NULL, server default
   ``'auto'``.
5. Floor 1 (safety review, ``docs/gates/M34/contracts-safety.md``): every
   statement ``get_status`` issues carries the caller's id; the
   ``quiz_attempts`` branch (that table has no ``user_id``) filters on
   ``courses.user_id``; ``set_checklist`` is one ``UPDATE users`` keyed on
   ``users.id == caller``; both routes hand the service the caller's id. The
   route tests patch ``app.services.onboarding_service.<fn>``, so the router
   imports the module (``from app.services import onboarding_service``), as
   the other routers do.

Red until ``backend`` lands the service and router and ``data`` the column
(M34-S3-BACKEND-012).
"""

import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import operators
from sqlalchemy.sql.dml import Update

from tests.contracts._weakspot_docs import (
    PACKAGE_ROOT,
    constants,
    contract_section,
    dataclass_decorator,
    dataclass_fields,
    python_block,
    signature,
    table_rows,
    top_level,
)

HEADING = "### api.onboarding v1"
SERVICE_PATH = PACKAGE_ROOT / "services" / "onboarding_service.py"
FUNCTIONS = ("derive_status", "get_status", "set_checklist")
DATACLASSES = ("SummaryTarget", "OnboardingStatus")
STEP_COLUMNS = ("phase", "upload", "summary", "check_in", "visible")


@pytest.fixture(scope="module")
def section() -> str:
    return contract_section(HEADING)


@pytest.fixture(scope="module")
def block(section) -> ast.Module:
    return python_block(section, HEADING)


@pytest.fixture(scope="module")
def service_tree() -> ast.Module:
    assert SERVICE_PATH.is_file(), f"{SERVICE_PATH.name} does not exist yet (`backend`)"
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def service():
    from app.services import onboarding_service

    return onboarding_service


# --- 1. the block --------------------------------------------------------------


def test_block_is_complete(block):
    defs = top_level(block)
    assert set(FUNCTIONS) | set(DATACLASSES) <= set(defs)


def test_constants_match(block, service_tree):
    want, got = constants(block), constants(service_tree)
    diff = {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v}
    assert not diff, f"constants differ from {HEADING}: {diff}"


def test_dataclasses_match(block, service_tree):
    want, got = top_level(block), top_level(service_tree)
    for name in DATACLASSES:
        assert name in got, f"{name} missing from onboarding_service"
        assert dataclass_fields(got[name]) == dataclass_fields(want[name]), name
        assert dataclass_decorator(got[name]) == dataclass_decorator(want[name]), name


def test_function_signatures_match(block, service_tree):
    want, got = top_level(block), top_level(service_tree)
    diff = {
        n: (signature(want[n]), signature(got[n]) if n in got else None)
        for n in FUNCTIONS
        if n not in got or signature(want[n]) != signature(got[n])
    }
    assert not diff, f"signatures differ from {HEADING}: {diff}"


def test_scoped_functions_take_user_id_as_a_required_keyword(block):
    defs = top_level(block)
    for name in ("get_status", "set_checklist"):
        kwonly = {
            a.arg: d
            for a, d in zip(defs[name].args.kwonlyargs, defs[name].args.kw_defaults, strict=True)
        }
        assert "user_id" in kwonly and kwonly["user_id"] is None, name


# --- 2. worked examples ---------------------------------------------------------


def _yes(cell: str) -> bool:
    assert cell in ("yes", "no"), cell
    return cell == "yes"


@pytest.fixture(scope="module")
def examples(section) -> list[list[str]]:
    rows = table_rows(section, "uploaded")
    assert len(rows) >= 8, f"{HEADING} has {len(rows)} worked examples; expected at least 8"
    return rows


def test_derive_status_reproduces_the_worked_examples(service, examples):
    target = service.SummaryTarget(course_id="c1", course_code="CSIT302", week=1)
    wrong = []
    for row in examples:
        uploaded, tgt, read, checked, checklist, *expected = row
        status = service.derive_status(
            uploaded=_yes(uploaded),
            summary_target=target if tgt == "set" else None,
            summary_read=_yes(read),
            check_in_done=_yes(checked),
            checklist=checklist,
        )
        got = [status.phase, status.upload, status.summary, status.check_in, status.visible]
        want = [*expected[:4], _yes(expected[4])]
        if got != want:
            wrong.append(f"{row[:5]}: got {got}, want {want}")
        assert status.summary_target == (target if tgt == "set" else None)
        assert status.checklist == checklist
    assert not wrong, "derive_status disagrees with the worked examples:\n" + "\n".join(wrong)


def test_status_values_are_from_the_declared_sets(service, examples):
    for row in examples:
        phase, upload, summary, check_in, _visible = row[5:]
        assert phase in service.ONBOARDING_PHASES
        assert {upload, summary, check_in} <= set(service.ONBOARDING_STEP_STATUSES)
        assert row[4] in service.ONBOARDING_CHECKLIST_STATES


def test_status_is_frozen(service):
    status = service.derive_status(
        uploaded=False,
        summary_target=None,
        summary_read=False,
        check_in_done=False,
        checklist="auto",
    )
    with pytest.raises(AttributeError):
        status.phase = "done"  # type: ignore[misc]


# --- 3. routes ----------------------------------------------------------------


@pytest.fixture(scope="module")
def app_routes() -> dict[tuple[str, str], APIRoute]:
    from app.main import app

    out: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                out[(method, route.path)] = route
    return out


@pytest.fixture(scope="module")
def contract_routes(section) -> set[tuple[str, str]]:
    rows = table_rows(section, "Method")
    return {(r[0].strip("`"), r[1].strip("`")) for r in rows}


def _dependency_calls(route: APIRoute) -> set[object]:
    calls: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is not None:
            calls.add(dep.call)
        stack.extend(dep.dependencies)
    return calls


def test_routes_exist_and_nothing_else_under_the_prefix(contract_routes, app_routes):
    assert contract_routes == {("GET", "/api/onboarding"), ("PATCH", "/api/onboarding")}
    missing = sorted(contract_routes - set(app_routes))
    assert not missing, f"routes in {HEADING} the app does not serve: {missing}"
    extra = sorted(
        k for k in app_routes if k[1].startswith("/api/onboarding") and k not in contract_routes
    )
    assert not extra, f"unlisted routes under /api/onboarding: {extra}"


def test_routes_require_a_caller_and_spend_nothing(contract_routes, app_routes):
    from app.api.deps import get_current_user, get_current_user_or_default, require_ai_consent

    for key in contract_routes:
        assert key in app_routes, f"{key} not served yet"
        calls = _dependency_calls(app_routes[key])
        assert calls & {get_current_user, get_current_user_or_default}, f"{key}: no caller"
        assert require_ai_consent not in calls, f"{key}: consent-gated but spends no AI"


# --- 4. storage ---------------------------------------------------------------


def test_users_column():
    import app.models  # noqa: F401
    from app.core.database import Base

    col = Base.metadata.tables["users"].columns.get("onboarding_checklist")
    assert col is not None, "users.onboarding_checklist missing (`data`)"
    assert isinstance(col.type, String) and col.type.length == 20
    assert col.nullable is False
    assert col.server_default is not None and "auto" in str(col.server_default.arg)


# --- 5. floor 1: the caller's rows only -----------------------------------------

CALLER = "user-onb-0001"


class _Checklist(str):
    """``'auto'`` whether the service selects the column or the whole user."""

    onboarding_checklist = "auto"


def _recording_session():
    """A session that records every statement and answers 'nothing found'."""
    statements: list[object] = []
    gets: list[tuple[object, object]] = []

    def _result(stmt) -> MagicMock:
        statements.append(stmt)
        result = MagicMock()
        hit = _Checklist("auto") if "onboarding_checklist" in str(stmt) else None
        result.scalar.return_value = hit if hit is not None else 0
        result.scalar_one.return_value = hit if hit is not None else 0
        result.scalar_one_or_none.return_value = hit
        result.first.return_value = None
        result.one_or_none.return_value = None
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalars.return_value.first.return_value = hit
        result.scalars.return_value.one_or_none.return_value = hit
        return result

    async def execute(stmt, *_args, **_kwargs):
        return _result(stmt)

    async def scalar(stmt, *_args, **_kwargs):
        return _result(stmt).scalar()

    async def get(entity, ident, *_args, **_kwargs):
        gets.append((entity, ident))
        return SimpleNamespace(id=ident, onboarding_checklist="auto")

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute)
    session.scalar = AsyncMock(side_effect=scalar)
    session.get = AsyncMock(side_effect=get)
    return session, statements, gets


def _sql_and_params(stmt) -> tuple[str, list[object]]:
    compiled = stmt.compile(dialect=postgresql.dialect())
    return " ".join(str(compiled).split()), list(compiled.params.values())


async def test_get_status_scopes_every_statement_to_the_caller(service):
    session, statements, gets = _recording_session()
    await service.get_status(session, user_id=CALLER)

    assert statements or gets, "get_status issued no query"
    unscoped = [
        sql[:160] for sql, params in map(_sql_and_params, statements) if CALLER not in params
    ]
    assert not unscoped, "get_status statements without the caller's id (floor 1):\n" + "\n".join(
        unscoped
    )
    assert all(ident == CALLER for _entity, ident in gets), gets


async def test_quiz_attempts_branch_is_scoped_through_courses(service):
    session, statements, _gets = _recording_session()
    await service.get_status(session, user_id=CALLER)

    quiz = [sql for sql, _p in map(_sql_and_params, statements) if "quiz_attempts" in sql]
    assert quiz, "no statement reads quiz_attempts: the check-in branch is missing"
    for sql in quiz:
        assert "courses.user_id" in sql, (
            "quiz_attempts has no user_id; the branch must join quiz_questions to courses and "
            f"filter on courses.user_id (floor 1): {sql[:200]}"
        )


async def test_set_checklist_updates_only_the_callers_users_row(service):
    session, statements, _gets = _recording_session()
    sentinel = service.derive_status(
        uploaded=False,
        summary_target=None,
        summary_read=False,
        check_in_done=False,
        checklist="dismissed",
    )
    with patch.object(service, "get_status", new=AsyncMock(return_value=sentinel)) as status:
        out = await service.set_checklist(session, user_id=CALLER, checklist="dismissed")

    updates = [s for s in statements if isinstance(s, Update)]
    assert len(updates) == 1, f"expected one UPDATE, got {len(updates)}"
    update = updates[0]
    assert update.table.name == "users", update.table
    where = update.whereclause
    assert where is not None, "UPDATE users without a WHERE clause"
    assert getattr(where, "operator", None) is operators.eq, str(where)
    assert getattr(where.left, "table", None) is not None
    assert where.left.table.name == "users" and where.left.key == "id", (
        f"keyed on {where.left}, not users.id"
    )
    assert where.right.value == CALLER, "the UPDATE is not keyed on the caller (floor 1)"
    params = update.compile(dialect=postgresql.dialect()).params
    assert params.get("onboarding_checklist") == "dismissed", params
    assert status.await_args.kwargs.get("user_id") == CALLER
    assert out is sentinel


@pytest.mark.parametrize(
    ("method", "fn", "body"),
    [("get", "get_status", None), ("patch", "set_checklist", {"checklist": "dismissed"})],
)
async def test_routes_hand_the_service_the_callers_id(
    async_client, default_test_user, service, method, fn, body
):
    status = service.derive_status(
        uploaded=False,
        summary_target=None,
        summary_read=False,
        check_in_done=False,
        checklist="auto",
    )
    with patch.object(service, fn, new=AsyncMock(return_value=status)) as mock:
        kwargs = {"json": body} if body is not None else {}
        response = await getattr(async_client, method)("/api/onboarding", **kwargs)

    assert response.status_code == 200, response.text
    assert mock.await_args is not None, f"{fn} was not called"
    assert mock.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing
