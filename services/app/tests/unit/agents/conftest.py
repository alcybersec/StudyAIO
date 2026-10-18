"""Agent unit tests run as whatever uid pytest has; accept the shared uid by default.

SEC-006 refuses the Claude CLI on a non-root multi-user worker. The guard's own
tests (test_claude_code_spawn_guard.py) remove this default.
"""

import pytest


@pytest.fixture(autouse=True)
def _accept_shared_cli_uid(monkeypatch):
    monkeypatch.setenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", "true")
