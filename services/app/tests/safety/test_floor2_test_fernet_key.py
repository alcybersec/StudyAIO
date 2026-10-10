"""Floor 2: the committed all-zero Fernet key never encrypts real credentials.

M32-S4-SAFETY-029, review of 6b43cbb. The root conftest sets
``SETTINGS_ENCRYPTION_KEY`` to an all-zero Fernet key so the suite can start the
lifespan in multi-user mode. That key is in the tree, so per-user AI credentials
encrypted with it are readable by anyone who reads the repository: a deployment
running on it has no encryption at rest (SEC-06), and floor 2 ("per-user AI
credentials are never ... returned") then rests on the database never leaking.

``secret_box.check_startup`` refuses the key at multi-user startup unless
``_running_under_pytest()``, which is ``"pytest" in sys.modules``. Ruled
acceptable as a bypass signal because no environment variable, setting or
request can set it, and nothing in the runtime imports pytest. pytest *is*
installed in the runtime image (``requirements.txt``), so the second half is a
property of the code and its dependencies, not of the image, and is pinned
here both statically and in a fresh interpreter.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import os
import re
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from tests.safety._source import APP_ROOT, SERVICE_ROOT, app_modules, parse, rel

#: Top-level modules whose import at runtime would open the bypass.
TEST_RUNNER_MODULES = ("pytest", "_pytest")


def _start(*, single_user_mode: bool, key: str, under_pytest: bool) -> None:
    from app.config import settings
    from app.core import secret_box
    from app.main import app, lifespan

    with (
        patch.object(settings, "single_user_mode", single_user_mode),
        patch.object(settings, "bind_host", "127.0.0.1"),
        patch.object(settings, "settings_encryption_key", SecretStr(key)),
        # A real JWT secret, so the earlier default-JWT refusal is not what fires.
        patch.object(settings, "jwt_secret_key", SecretStr("j" * 64)),
        patch.object(secret_box, "_running_under_pytest", lambda: under_pytest),
        patch("app.main.configure_logging"),
        patch("app.main.warn_if_embedding_provider_unavailable"),
    ):

        async def _run() -> None:
            async with lifespan(app):
                pass

        asyncio.run(_run())


def test_floor2_multi_user_startup_refuses_the_committed_test_key():
    """Outside pytest, a multi-user lifespan with the conftest key does not start."""
    from app.core.secret_box import WELL_KNOWN_TEST_KEY

    with pytest.raises(RuntimeError, match="well-known"):
        _start(single_user_mode=False, key=WELL_KNOWN_TEST_KEY, under_pytest=False)


def test_floor2_committed_test_key_is_the_one_refused():
    """The key the root conftest installs is byte-for-byte the refused constant.

    Change one without the other and the suite keeps passing while production
    accepts the key the tree actually publishes.
    """
    from app.core.secret_box import WELL_KNOWN_TEST_KEY

    source = (SERVICE_ROOT / "conftest.py").read_text()
    match = re.search(r'SETTINGS_ENCRYPTION_KEY",\s*"([^"]+)"', source)
    assert match, "root conftest no longer sets SETTINGS_ENCRYPTION_KEY; re-pin this test"
    assert match.group(1) == WELL_KNOWN_TEST_KEY


def test_floor2_pytest_signal_reads_nothing_an_operator_can_set():
    """``_running_under_pytest`` reads ``sys.modules`` only: no env, setting or file.

    An env-var bypass (``TESTING=1``) is one a misconfigured ``.env`` turns on.
    """
    from app.core import secret_box

    tree = ast.parse(textwrap.dedent(inspect.getsource(secret_box._running_under_pytest)))
    body = tree.body[0].body  # the statements, not the ``-> bool`` annotation
    nodes = [n for stmt in body for n in ast.walk(stmt)]
    names = {n.id for n in nodes if isinstance(n, ast.Name)}
    attrs = {n.attr for n in nodes if isinstance(n, ast.Attribute)}
    assert attrs == {"modules"} and names <= {"sys"}, (
        f"_running_under_pytest reads {sorted(names | attrs)}; it may read sys.modules only"
    )


def test_floor2_no_runtime_module_imports_a_test_runner():
    """No module under ``app/`` imports pytest, at top level or lazily."""
    offenders = []
    for path in app_modules():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = [node.module]
            else:
                continue
            for mod in mods:
                if mod.split(".")[0] in TEST_RUNNER_MODULES:
                    offenders.append(f"{rel(path)}:{node.lineno} imports {mod}")
    assert not offenders, "\n".join(offenders)


#: Imports every ``app`` module, the evals runner (``cli evals``), and the
#: Celery task modules the worker loads, then reports any test runner loaded.
_RUNTIME_PROBE = """
import importlib, pkgutil, sys
import app
for info in pkgutil.walk_packages(app.__path__, "app."):
    importlib.import_module(info.name)
importlib.import_module("evals.runner")
from app.worker import celery_app
celery_app.loader.import_default_modules()
print(sorted(m for m in sys.modules if m.split(".")[0] in {mods!r}))
"""


def test_floor2_runtime_import_graph_never_loads_a_test_runner():
    """In a fresh interpreter, the whole runtime import graph leaves pytest unloaded.

    The static check above sees only our code; this one also sees a dependency
    that imports pytest (a plugin entry point, a test helper shipped in a wheel).
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST")}
    proc = subprocess.run(
        [sys.executable, "-c", _RUNTIME_PROBE.format(mods=set(TEST_RUNNER_MODULES))],
        cwd=SERVICE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    loaded = proc.stdout.strip().splitlines()[-1]
    assert loaded == "[]", (
        f"runtime import graph loads {loaded}: _running_under_pytest() is then true in "
        "production and the all-zero Fernet key is accepted"
    )
    assert APP_ROOT.is_dir()
