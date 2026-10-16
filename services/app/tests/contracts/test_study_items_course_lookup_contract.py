"""Contract test for `api.study-items v2` (docs/CONTRACTS.md, M34-S3-BACKEND-012).

v2 changes one rule: ``course_code`` on ``POST /api/assets/flashcards`` and
``POST /api/assets/quiz`` is matched case-insensitively, the way upload
placement matches it. Pins:

1. ``course_service.get_course_by_code_ci(session, code, *, user_id)`` exists,
   async, ``user_id`` keyword-only and required.
2. The statement it runs compares ``upper(courses.code)`` with the trimmed,
   upper-cased code and filters on ``courses.user_id`` (floor 1).
3. ``asset_service`` resolves ``course_code`` through it and no longer calls the
   exact-match ``get_course_by_code``.
4. The exact-match ``get_course_by_code`` keeps its signature (course routes
   keyed on ``{code}`` keep their behaviour). **Green today.**

Red until ``backend`` lands the lookup (M34-S3-BACKEND-012). ``backend`` also
flips the unit test that pinned the v1 exact match.
"""

import ast
import inspect

import pytest
from sqlalchemy.dialects import postgresql

from tests.contracts._weakspot_docs import APP_ROOT

USER = "user-contract-1"


class _Result:
    """Answers every result accessor with "nothing found"."""

    def scalar_one_or_none(self):
        return None

    def scalar(self):
        return None

    def first(self):
        return None

    def one_or_none(self):
        return None

    def all(self):
        return []

    def scalars(self):
        return self

    def __iter__(self):
        return iter(())


class _Session:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return _Result()

    async def scalar(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return None

    async def scalars(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return _Result()


@pytest.fixture(scope="module")
def lookup():
    from app.services import course_service

    fn = getattr(course_service, "get_course_by_code_ci", None)
    assert fn is not None, "course_service.get_course_by_code_ci does not exist yet (`backend`)"
    return fn


def test_signature(lookup):
    assert inspect.iscoroutinefunction(lookup)
    params = inspect.signature(lookup).parameters
    assert list(params) == ["session", "code", "user_id"]
    assert params["user_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["user_id"].default is inspect.Parameter.empty


async def test_statement_is_case_insensitive_and_owner_scoped(lookup):
    session = _Session()
    assert await lookup(session, "  csit302 ", user_id=USER) is None
    assert session.statements, "the lookup ran no statement"
    compiled = [
        s.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        for s in session.statements
    ]
    raw = "\n".join(str(c) for c in compiled)
    sql = raw.lower()
    assert "upper(courses.code)" in sql, raw
    assert "'CSIT302'" in raw, f"code not trimmed and upper-cased:\n{raw}"
    assert "'  csit302 '" not in raw, f"the raw code reached the query:\n{raw}"
    assert "courses.user_id" in sql and f"'{USER}'" in raw, f"not filtered on the caller:\n{raw}"


def _calls(fn_name: str) -> set[str]:
    path = APP_ROOT / "app" / "services" / "asset_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith(fn_name)
    }


def test_asset_service_uses_the_case_insensitive_lookup():
    assert _calls("get_course_by_code_ci"), "asset_service does not call get_course_by_code_ci"
    exact = {c for c in _calls("get_course_by_code") if not c.endswith("_ci")}
    assert not exact, f"asset_service still matches course_code exactly: {exact}"


def test_exact_lookup_is_unchanged():
    from app.services import course_service

    params = inspect.signature(course_service.get_course_by_code).parameters
    assert list(params) == ["session", "code", "user_id"]
    assert params["user_id"].kind is inspect.Parameter.KEYWORD_ONLY
