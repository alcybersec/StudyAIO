"""Contract test for `pipeline.targeted_generation v1` (docs/CONTRACTS.md, ADR 0007 Decision 5).

Targeted generation is the weak-spot engine's only AI call, and ADR 0007 puts
it in the worker so that floor 3's request-time allowlist (ADR 0003) does not
grow. This file checks:

1. ``GenerationFocus`` in ``app/agents/base.py`` has the entry's fields.
2. ``AgentAdapter.generate_quiz`` / ``generate_flashcards`` have the entry's
   signatures (the additive ``focus`` keyword), and so does every backend's
   override (the backends are read from the ``agents.AgentAdapter`` entry).
3. The Celery task is registered under ``TARGETED_TASK_NAME``, its module calls
   ``get_agent``, and the two targeted templates exist.
4. The request side never obtains an adapter: ``app/api/weakspots.py`` and
   ``app/services/weakspot_service.py`` contain no ``get_agent``.
5. ADR 0003's allowlist still has exactly its five entries (green today; it
   turns red if anyone widens floor 3 to make this feature easier).

Red until ``ai`` lands the task, the keyword and the templates (M33-S2-AI-021).
"""

import ast
import importlib

import pytest

from tests.contracts._weakspot_docs import (
    ADR_0003_PATH,
    APP_ROOT,
    PACKAGE_ROOT,
    constants,
    contract_section,
    dataclass_decorator,
    dataclass_fields,
    python_block,
    require,
    signature,
    table_rows,
    top_level,
)

HEADING = "### pipeline.targeted_generation v1"
ADAPTER_HEADING = "### agents.AgentAdapter v2"
BASE_PATH = PACKAGE_ROOT / "agents" / "base.py"
TASK_PATH = PACKAGE_ROOT / "pipeline" / "targeted_task.py"
TASK_MODULE = "app.pipeline.targeted_task"
TEMPLATES = ("generate_targeted_quiz.txt", "generate_targeted_flashcards.txt")
METHODS = ("generate_flashcards", "generate_quiz")
REQUEST_SIDE = (
    PACKAGE_ROOT / "api" / "weakspots.py",
    PACKAGE_ROOT / "services" / "weakspot_service.py",
)

ADR_0003_ALLOWLIST = {
    ("app/api/qa.py", "ask_question"),
    ("app/api/settings.py", "test_ai_connection"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "extract_and_save_concepts"),
}


@pytest.fixture(scope="module")
def block() -> ast.Module:
    return python_block(contract_section(HEADING), HEADING)


@pytest.fixture(scope="module")
def block_defs(block: ast.Module) -> dict[str, ast.stmt]:
    return top_level(block)


@pytest.fixture(scope="module")
def block_methods(block_defs) -> dict[str, ast.AsyncFunctionDef]:
    adapter = block_defs["AgentAdapter"]
    return {n.name: n for n in adapter.body if isinstance(n, ast.AsyncFunctionDef)}


@pytest.fixture(scope="module")
def base_defs() -> dict[str, ast.stmt]:
    return top_level(ast.parse(BASE_PATH.read_text(encoding="utf-8")))


def _methods(cls: ast.ClassDef) -> dict[str, ast.AsyncFunctionDef | ast.FunctionDef]:
    return {n.name: n for n in cls.body if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))}


def _calls_get_agent(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "get_agent":
                return True
    return False


# ── the entry itself ───────────────────────────────────────────────────


def test_block_names_the_task_the_focus_and_the_two_methods(block, block_defs, block_methods):
    assert constants(block)["TARGETED_TASK_NAME"] == (
        "app.pipeline.targeted_task.generate_targeted_items"
    )
    assert {"GenerationFocus", "AgentAdapter", "generate_targeted_items"} <= set(block_defs)
    assert set(block_methods) == set(METHODS)
    for name, fn in block_methods.items():
        focus = fn.args.args[-1]
        assert focus.arg == "focus" and ast.unparse(fn.args.defaults[-1]) == "None", name


def test_adr_0003_allowlist_is_unchanged():
    """ADR 0007 adds no request-time site; the floor-3 list keeps its five entries."""
    text = require(ADR_0003_PATH)
    tree = python_block(text, "ADR 0003")
    sites = ast.literal_eval(tree.body[0].value)
    assert sites == ADR_0003_ALLOWLIST


# ── 1-2. the adapter ───────────────────────────────────────────────────


def test_generation_focus_matches(block_defs, base_defs):
    assert "GenerationFocus" in base_defs, "GenerationFocus missing from app/agents/base.py"
    mine, theirs = base_defs["GenerationFocus"], block_defs["GenerationFocus"]
    assert dataclass_decorator(mine) == dataclass_decorator(theirs)
    assert dataclass_fields(mine) == dataclass_fields(theirs)


def test_abc_methods_take_focus(block_methods, base_defs):
    base = _methods(base_defs["AgentAdapter"])
    wrong = {
        name: (signature(fn), signature(base[name]))
        for name, fn in block_methods.items()
        if signature(fn) != signature(base[name])
    }
    assert not wrong, f"AgentAdapter differs from {HEADING} (expected, actual): {wrong}"


def test_every_backend_override_takes_focus(block_methods):
    rows = table_rows(contract_section(ADAPTER_HEADING), "`agent_backend`")
    assert rows, "no backends listed in the agents.AgentAdapter entry"
    wrong: dict[str, object] = {}
    for _backend, cls_cell, module_cell in rows:
        cls_name = cls_cell.strip("`")
        path = APP_ROOT.parents[1] / module_cell.strip("`")
        cls = top_level(ast.parse(path.read_text(encoding="utf-8"))).get(cls_name)
        assert isinstance(cls, ast.ClassDef), f"{cls_name} not found in {path}"
        overrides = _methods(cls)
        for name, fn in block_methods.items():
            if name in overrides and signature(overrides[name]) != signature(fn):
                wrong[f"{cls_name}.{name}"] = signature(overrides[name])
    assert not wrong, f"backend overrides without the focus keyword: {wrong}"


# ── 3. the task ────────────────────────────────────────────────────────


def test_task_is_registered(block):
    assert TASK_PATH.is_file(), "app/pipeline/targeted_task.py does not exist yet: `ai` writes it"
    importlib.import_module(TASK_MODULE)
    from app.worker import celery_app

    assert constants(block)["TARGETED_TASK_NAME"] in celery_app.tasks


def test_task_signature_and_adapter_call(block_defs):
    assert TASK_PATH.is_file(), "app/pipeline/targeted_task.py does not exist yet: `ai` writes it"
    tree = ast.parse(TASK_PATH.read_text(encoding="utf-8"))
    task = top_level(tree).get("generate_targeted_items")
    assert task is not None, "generate_targeted_items missing from targeted_task.py"
    assert signature(task) == signature(block_defs["generate_targeted_items"])
    assert _calls_get_agent(tree), "targeted_task.py must obtain its adapter via get_agent"


@pytest.mark.parametrize("template", TEMPLATES)
def test_targeted_templates_exist(template):
    assert (APP_ROOT / "prompts" / template).is_file(), f"prompts/{template} missing"


# ── 4. the request side never obtains an adapter ──────────────────────


@pytest.mark.parametrize("path", REQUEST_SIDE, ids=lambda p: p.name)
def test_request_side_has_no_get_agent(path):
    # A guard, not a red pin: `backend` writes these files, so their absence is not
    # this provider's failure, and an absent file has no get_agent call in it.
    if not path.is_file():
        return
    assert not _calls_get_agent(ast.parse(path.read_text(encoding="utf-8"))), (
        f"{path.name} calls get_agent: a new request-time site needs ADR 0003 amended"
    )
