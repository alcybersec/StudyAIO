"""Root conftest — pins the whole test run to a throwaway storage root.

Why this file exists
--------------------
``settings.data_dir`` defaults to ``/app/data`` (``app/config.py``). That is the
right answer *inside the container*, which is why it never looked wrong. It is
the wrong answer on a developer machine, where ``/app/data/uploads`` may be a
real, populated directory — and issue #56 / PR #67 made the suite runnable on a
developer machine.

The consequence was that a test which reached ``get_storage()`` without a
fixture resolved to the real data directory. ``tests/integration/
test_account_deletion.py`` exercised ``purge_user_storage`` — a function whose
job is deleting files — against it. Nothing was lost, because the tests build
random UUIDs and the purge deletes by exact key and by prefix, so the keys it
computed matched nothing real. The safety came entirely from id randomness, not
from isolation (issue #100).

``LocalStorageBackend.__init__`` also does ``mkdir(parents=True,
exist_ok=True)``, so even a read-only test *creates* the real directory, and a
test that writes leaks state into it between runs.

How it is fixed
---------------
``DATA_DIR`` is put into ``os.environ`` here, at conftest import, and then the
resolved value is asserted to live under the system temp directory. Two
separate things, deliberately:

* **Redirect** (``_install_test_data_dir``) so that forgetting a fixture is
  harmless rather than dangerous.
* **Refuse** (``_assert_disposable_data_dir``) so that if the redirect ever
  stops working — a plugin that imports ``app`` too early, a ``.env`` that wins,
  a future fixture that repoints ``settings.data_dir`` at something real — the
  suite says so loudly instead of quietly operating on real files.

This is defence in depth *behind* PR #99's per-test ``tmp_path``-rooted storage
fixture, not a replacement for it. Per-test roots still give per-test isolation;
this only guarantees that the floor is never a real directory.

Why the ordering works, and why it is checked
---------------------------------------------
``app.config.settings`` is a module-level singleton that reads the environment
exactly once, at first import, and ``importlib.reload`` does not help: reloading
rebinds names in that module, not in the modules that already imported from it
(this is the whole subject of issue #56). So the environment has to be right
*before* the first ``import app.config``.

The root conftest is the earliest in-process hook that satisfies that. pytest
loads conftests from ``confcutdir`` (the rootdir, where ``pytest.ini`` lives)
downwards as *initial conftests*, during config creation — before test modules
are imported, before any other conftest, and before xdist forks its workers, so
workers inherit the same ``DATA_DIR`` through the environment. Nothing earlier
than this imports ``app``, and ``_refuse_late_override`` asserts exactly that
rather than trusting it.

There is intentionally **no opt-out.** Every candidate reason to point the test
suite at a real directory turned out to be either the hazard itself (running in
the container against ``/app/data``) or satisfiable with a temp directory of the
caller's own choosing, which ``DATA_DIR`` already allows.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

#: The environment variable ``Settings.data_dir`` is populated from.
_ENV_VAR = "DATA_DIR"

#: Directories that count as disposable. ``tempfile.gettempdir()`` honours
#: ``TMPDIR``, and is resolved as well as raw so that a symlinked temp root
#: (``/var`` -> ``/private/var`` on macOS) matches either way.
_TEMP_ROOTS = frozenset(
    {
        Path(tempfile.gettempdir()),
        Path(tempfile.gettempdir()).resolve(),
    }
)


def _is_disposable(path: str | os.PathLike[str]) -> bool:
    """True when *path* lives under a system temp root."""
    candidate = Path(path).resolve()
    return any(candidate == root or root in candidate.parents for root in _TEMP_ROOTS)


def _refuse_late_override(existing: str | None) -> None:
    """Fail if ``app`` was imported before we could set the environment.

    If any ``app`` module is already in ``sys.modules``, ``app.config.settings``
    has already read the environment and a value set now will never be seen —
    the exact failure mode of issue #56. Better to say so than to set an
    environment variable that no longer has any effect.
    """
    already = sorted(name for name in sys.modules if name == "app" or name.startswith("app."))
    if not already:
        return
    raise RuntimeError(
        "Cannot isolate the test storage root: app modules were imported before "
        "this conftest ran, so app.config.settings has already read the "
        f"environment.\n\n"
        f"  {_ENV_VAR} was   : {existing!r}\n"
        f"  already imported: {', '.join(already[:8])}"
        f"{' ...' if len(already) > 8 else ''}\n\n"
        "settings is a module-level singleton read once at import time, and "
        "importlib.reload does not propagate a new value to modules that already "
        f"imported from it (issue #56). Export {_ENV_VAR} to a temp directory "
        "before starting pytest, or stop whatever imports app that early."
    )


def _install_test_data_dir() -> str:
    """Point ``DATA_DIR`` at a throwaway directory for this process.

    An inherited value is kept when it is already disposable — that is how
    ``scripts/test-integration.sh`` and xdist workers hand the same root down,
    so pytest, Alembic and any subprocess agree on one location. Anything else
    is replaced.
    """
    existing = os.environ.get(_ENV_VAR) or None

    if existing is not None and _is_disposable(existing):
        Path(existing).mkdir(parents=True, exist_ok=True)
        return existing

    # Checked before minting the directory, so a refusal leaves nothing behind.
    _refuse_late_override(existing)
    replacement = tempfile.mkdtemp(prefix="studyaio-test-data-")

    if existing is not None:
        print(
            f"conftest: {_ENV_VAR}={existing!r} is not a temp directory; the test "
            f"suite has been redirected to {replacement!r} instead. Tests must "
            "never be able to write to, or delete from, a real data directory "
            "(issue #100).",
            file=sys.stderr,
        )

    os.environ[_ENV_VAR] = replacement
    atexit.register(_discard, replacement)
    return replacement


def _discard(path: str) -> None:
    """Remove a directory this process created under the temp root."""
    if _is_disposable(path):
        shutil.rmtree(path, ignore_errors=True)


def _assert_disposable_data_dir(when: str) -> None:
    """Refuse to let the suite run against a storage root that is not disposable."""
    from app.config import settings

    if _is_disposable(settings.data_dir):
        return

    raise RuntimeError(
        f"Refusing to run tests against a non-temporary data directory ({when}).\n\n"
        f"  app.config.settings.data_dir = {settings.data_dir!r}\n"
        f"  os.environ[{_ENV_VAR!r}]        = {os.environ.get(_ENV_VAR)!r}\n"
        f"  expected it under            = {sorted(str(p) for p in _TEMP_ROOTS)}\n\n"
        "get_storage() resolves settings.data_dir, LocalStorageBackend creates it "
        "on construction, and the account-deletion paths delete from it — so a "
        "real directory here means the suite can destroy real uploads (issue "
        "#100). There is no opt-out on purpose: point DATA_DIR at a temp "
        "directory of your choosing instead."
    )


#: Set before anything imports ``app``; see this module's docstring.
TEST_DATA_DIR = _install_test_data_dir()

# Collection-time refusal. This runs at conftest import, so it aborts before a
# single test module is imported — earlier than any fixture can.
_assert_disposable_data_dir("at conftest import")


@pytest.fixture(scope="session", autouse=True)
def _disposable_storage_root() -> None:
    """Re-check the storage root once the session is set up.

    The collection-time check above is the one that matters for ordering. This
    one catches a root that became non-disposable *after* import — a plugin or
    session fixture repointing ``settings.data_dir`` — and reports it as a test
    failure rather than a collection error.
    """
    _assert_disposable_data_dir("before the first test ran")
