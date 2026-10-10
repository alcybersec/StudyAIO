"""Smoke test: proves the suite is wired and runs on the supported interpreter."""

import sys


def test_suite_runs_on_supported_python() -> None:
    assert sys.version_info[:2] >= (3, 12)


def test_app_package_imports() -> None:
    import app  # noqa: F401
