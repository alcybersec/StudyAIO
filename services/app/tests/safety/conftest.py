"""Floor-tier fixtures that pin which Claude CLI spawn path a test exercises.

SEC-006 option F (``ensure_claude_cli_spawnable`` in ``agents/claude_code.py``)
refuses the CLI before anything is read or spawned when the worker is non-root,
the deployment is multi-user and the operator has not opted in. Whether a spawn
test reaches the CLI therefore depends on the uid pytest runs as: root in CI,
a developer's uid locally. A floor pin must not change meaning with that.

Neither fixture is autouse. A spawn test names the deployment it is about:

* ``cli_shared_uid_opt_in`` -- the F deployment that still spawns: a non-root
  AI pool (uid 999) whose operator set ``CLAUDE_CLI_SHARED_UID_ACCEPTED=true``.
  No uid drop, the child keeps the worker's uid. Every containment pin that is
  not about the drop (env allowlist, no tools, redaction, cwd, operator model)
  runs here, because this is the path prod reaches when it spawns at all.
* ``cli_root_worker`` -- a root worker, where ``CLAUDE_CLI_UID`` drops the child
  (AGENT-01, R-030). The opt-in is removed so the root path is proven without it.

The refusal itself is pinned in ``test_floor2_cli_shared_uid_refusal.py``.
"""

from __future__ import annotations

import os

import pytest

#: The AI pools' uid since SEC-006 (``studyaio`` in ``services/app/Dockerfile``).
NON_ROOT_POOL_UID = 999
OPT_IN = "CLAUDE_CLI_SHARED_UID_ACCEPTED"


def _deployment(monkeypatch: pytest.MonkeyPatch, *, euid: int, opt_in: bool) -> None:
    from app.agents import claude_code

    monkeypatch.setattr(os, "geteuid", lambda: euid)
    monkeypatch.setattr(claude_code.settings, "single_user_mode", False)
    if opt_in:
        monkeypatch.setenv(OPT_IN, "true")
    else:
        monkeypatch.delenv(OPT_IN, raising=False)


@pytest.fixture
def cli_shared_uid_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-root, multi-user, operator opted in: the guard lets the CLI spawn."""
    monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
    monkeypatch.delenv("CLAUDE_CLI_GID", raising=False)
    _deployment(monkeypatch, euid=NON_ROOT_POOL_UID, opt_in=True)


@pytest.fixture
def cli_root_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Root worker, multi-user, no opt-in: the uid-drop path, unchanged by SEC-006."""
    _deployment(monkeypatch, euid=0, opt_in=False)
