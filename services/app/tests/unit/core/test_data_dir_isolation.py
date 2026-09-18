"""The test suite must never be able to reach a real data directory.

``settings.data_dir`` defaults to ``/app/data``. That is correct inside the
container and dangerous on a developer machine, where it can be a real,
populated upload directory — and the account-deletion tests call
``purge_user_storage``, whose job is deleting files. Nothing was ever lost only
because those tests build random UUIDs, so the keys the purge computed never
matched anything real (issue #100).

The root ``conftest.py`` fixes that in two independent ways: it redirects
``DATA_DIR`` to a throwaway directory before anything imports ``app.config``,
and it refuses to let the suite run if ``settings.data_dir`` is not disposable.
These tests assert both halves — including, deliberately, that the refusal
fires — without ever writing to or deleting from a real directory.
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from app.config import settings
from app.core.storage import LocalStorageBackend, get_storage, reset_storage

#: ``services/app``, the pytest rootdir — the directory holding the conftest
#: under test.
ROOTDIR = Path(__file__).resolve().parents[3]

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


def _under_temp_root(path: str | os.PathLike[str]) -> bool:
    resolved = Path(path).resolve()
    return resolved == TEMP_ROOT or TEMP_ROOT in resolved.parents


def _root_conftest() -> ModuleType:
    """Load the rootdir conftest by path, to test its guard helpers directly.

    Importing it a second time under its own name is side-effect free: by the
    time these tests run ``DATA_DIR`` is already a temp path, so
    ``_install_test_data_dir`` honours it and returns without minting a new
    directory. Loading by path rather than trusting pytest's module naming keeps
    this test independent of the import mode in use.
    """
    cached = sys.modules.get("_studyaio_root_conftest")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "_studyaio_root_conftest", ROOTDIR / "conftest.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_studyaio_root_conftest"] = module
    spec.loader.exec_module(module)
    return module


class TestStorageRootIsRedirected:
    """The environment half: no test can resolve the real data directory."""

    def test_data_dir_env_var_is_set(self):
        """`DATA_DIR` is populated, so `Settings` never falls back to its default."""
        assert os.environ.get("DATA_DIR"), (
            "DATA_DIR is unset inside the test run. The rootdir conftest is "
            "supposed to set it before app.config is first imported."
        )

    def test_settings_data_dir_is_a_temp_path(self):
        """The value the app actually resolved — not just the environment."""
        assert _under_temp_root(settings.data_dir), (
            f"settings.data_dir is {settings.data_dir!r}, which is not under "
            f"{TEMP_ROOT}. The redirect in the rootdir conftest did not take "
            "effect before app.config was imported (issue #56 ordering)."
        )

    def test_settings_data_dir_is_not_the_container_default(self):
        assert Path(settings.data_dir).resolve() != Path("/app/data")

    def test_settings_data_dir_matches_the_environment(self):
        """Proof the value came from our export, not from a fixture patch."""
        assert Path(settings.data_dir).resolve() == Path(os.environ["DATA_DIR"]).resolve()

    def test_derived_directories_inherit_the_redirect(self):
        for derived in (settings.uploads_dir, settings.extractions_dir, settings.summaries_dir):
            assert _under_temp_root(derived), derived

    def test_unfixtured_storage_backend_roots_under_temp(self):
        """The case the issue is about: `get_storage()` with no fixture at all.

        `LocalStorageBackend.__init__` calls `mkdir(parents=True,
        exist_ok=True)`, so before the redirect this call *created* `/app/data`
        even in a read-only test.
        """
        reset_storage()
        try:
            backend = get_storage()
            assert isinstance(backend, LocalStorageBackend)
            assert _under_temp_root(backend.base_dir), backend.base_dir
            assert backend.resolve_path("uploads/x.pdf") != Path("/app/data/uploads/x.pdf")
        finally:
            reset_storage()


class TestStorageRootGuard:
    """The refusal half: if the redirect ever fails, the suite says so."""

    def test_guard_accepts_the_current_root(self):
        """No exception for the root the suite is actually running on."""
        _root_conftest()._assert_disposable_data_dir("in a test")

    def test_guard_refuses_the_container_default(self):
        """Repointing settings at a real directory must abort, loudly.

        This only reads `settings.data_dir` — nothing is created, written or
        deleted under `/app/data`.
        """
        root = _root_conftest()
        with patch("app.config.settings.data_dir", "/app/data"):
            with pytest.raises(RuntimeError, match="Refusing to run tests"):
                root._assert_disposable_data_dir("in a test")

    def test_guard_message_names_the_offending_path(self):
        root = _root_conftest()
        with patch("app.config.settings.data_dir", "/app/data"):
            with pytest.raises(RuntimeError) as excinfo:
                root._assert_disposable_data_dir("in a test")
        assert "/app/data" in str(excinfo.value)

    @pytest.mark.parametrize(
        "path",
        ["/app/data", "/app/data/uploads", "/var/lib/studyaio", "/home/someone/studyaio-data"],
    )
    def test_is_disposable_rejects_real_paths(self, path):
        assert _root_conftest()._is_disposable(path) is False

    def test_is_disposable_accepts_temp_paths(self, tmp_path):
        is_disposable = _root_conftest()._is_disposable
        assert is_disposable(tmp_path) is True
        assert is_disposable(TEMP_ROOT) is True
        assert is_disposable(settings.data_dir) is True

    def test_is_disposable_rejects_traversal_out_of_temp(self):
        """A path that only *looks* temporary is resolved before it is judged.

        With the default temp root this spells `/tmp/../app/data`, i.e. the very
        directory the guard exists to keep the suite away from.
        """
        escaped = TEMP_ROOT / ".." / "app" / "data"
        assert TEMP_ROOT.parts[0] in str(escaped)
        assert _root_conftest()._is_disposable(escaped) is False

    def test_guard_is_installed_as_a_session_autouse_fixture(self):
        """The fixture exists and is autouse, so it cannot be forgotten."""
        marker = _root_conftest()._disposable_storage_root._pytestfixturefunction
        assert marker.autouse is True
        assert marker.scope == "session"

    def test_there_is_no_opt_out(self):
        """The guard takes no flag, marker or environment escape hatch.

        Every candidate reason to aim the suite at a real directory was either
        the hazard itself or satisfiable by pointing `DATA_DIR` at a temp
        directory of the caller's choosing. If a legitimate case turns up, add
        it here first so the exemption is visible.
        """
        root = _root_conftest()
        source = (ROOTDIR / "conftest.py").read_text()
        for escape in ("ALLOW_REAL_DATA_DIR", "SKIP_DATA_DIR_CHECK", "getoption"):
            assert escape not in source, (
                f"{escape!r} appeared in the root conftest. If an exemption is "
                "genuinely needed, write down the case it serves here and in the "
                "conftest docstring — a silent escape hatch turns this guard back "
                "into the hazard it replaced."
            )
        # The guard takes only its `when` label: no config, no request, no marker.
        assert root._assert_disposable_data_dir.__code__.co_argcount == 1
