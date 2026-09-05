"""Tests for the provider-default backfill migration (issue #30).

The migration is loaded by path — Alembic version modules are not importable
as a package — and its row transform is exercised directly, which is the whole
of its behaviour.
"""

import importlib.util
import json
import time
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "z6a7b8c9d0e1_default_provider_studyaio.py"
)

OWN_KEY = "<test-placeholder>-user-zai-key"


def _load():
    spec = importlib.util.spec_from_file_location("provider_backfill_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


def _creds(expires_at_ms: int) -> str:
    return json.dumps(
        {
            "claudeAiOauth": {
                "accessToken": "<test-placeholder>-access",
                "refreshToken": "<test-placeholder>-refresh",
                "expiresAt": expires_at_ms,
            }
        }
    )


class TestRewriteSettings:
    """Credential-less overrides become "StudyAIO provided"; real ones survive."""

    def test_credential_less_override_becomes_studyaio(self, migration):
        result = migration.rewrite_settings({"agent_backend": "zai"})
        assert result == {"agent_backend": "studyaio"}

    def test_user_with_own_key_keeps_their_provider(self, migration):
        row = {"agent_backend": "zai", "zai_api_key": OWN_KEY}
        assert migration.rewrite_settings(row) is None

    def test_unknown_backend_becomes_studyaio(self, migration):
        result = migration.rewrite_settings({"agent_backend": "gemini"})
        assert result == {"agent_backend": "studyaio"}

    def test_no_backend_is_left_alone(self, migration):
        assert migration.rewrite_settings({"theme_hint": "x"}) is None

    def test_already_studyaio_is_left_alone(self, migration):
        assert migration.rewrite_settings({"agent_backend": "studyaio"}) is None

    def test_ollama_needs_its_own_endpoint(self, migration):
        assert migration.rewrite_settings({"agent_backend": "ollama"}) == {
            "agent_backend": "studyaio"
        }
        assert (
            migration.rewrite_settings(
                {"agent_backend": "ollama", "ollama_base_url": "http://mine:11434"}
            )
            is None
        )


class TestStaleCredentialStripping:
    """Dead credential material is removed rather than carried forward."""

    def test_empty_secret_is_dropped(self, migration):
        result = migration.rewrite_settings({"zai_api_key": "", "ollama_model": "llama3.2"})
        assert result == {"ollama_model": "llama3.2"}

    def test_expired_cli_credentials_are_dropped(self, migration):
        expired = _creds(int((time.time() - 86400) * 1000))
        result = migration.rewrite_settings(
            {"agent_backend": "claude_code", "claude_cli_credentials": expired}
        )
        assert result == {"agent_backend": "studyaio"}

    def test_unexpired_cli_credentials_survive(self, migration):
        live = _creds(int((time.time() + 86400) * 1000))
        row = {"agent_backend": "claude_code", "claude_cli_credentials": live}
        assert migration.rewrite_settings(row) is None

    def test_unparseable_cli_credentials_are_dropped(self, migration):
        result = migration.rewrite_settings(
            {"agent_backend": "claude_code", "claude_cli_credentials": "not json {{{"}
        )
        assert result == {"agent_backend": "studyaio"}
