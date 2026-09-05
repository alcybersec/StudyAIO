"""Tests for the `embedding_backend` removal migration (issue #32).

The migration is loaded by path — Alembic version modules are not importable
as a package — and its row transform is exercised directly, which is the whole
of its behaviour.
"""

import importlib.util
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "a7b8c9d0e1f2_drop_embedding_backend_setting.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("embedding_backend_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


class TestStripEmbeddingBackend:
    """The dead key goes; everything else is left exactly as it was."""

    def test_key_is_removed(self, migration):
        assert migration.strip_embedding_backend({"embedding_backend": "openai"}) == {}

    def test_default_value_is_removed_too(self, migration):
        """Even the value that matched the default was doing nothing."""
        result = migration.strip_embedding_backend({"embedding_backend": "sentence_transformers"})
        assert result == {}

    def test_row_without_the_key_is_left_alone(self, migration):
        """No key, no write — the migration skips the row entirely."""
        assert migration.strip_embedding_backend({"agent_backend": "studyaio"}) is None

    def test_empty_settings_are_left_alone(self, migration):
        assert migration.strip_embedding_backend({}) is None

    def test_other_settings_survive(self, migration):
        """Only the one key is touched; the provider model from #31 is not."""
        row = {
            "embedding_backend": "ollama",
            "agent_backend": "zai",
            "zai_api_key": "<test-placeholder>-user-zai-key",
            "claude_model": "sonnet",
            "chunk_size_tokens": 500,
        }
        assert migration.strip_embedding_backend(row) == {
            "agent_backend": "zai",
            "zai_api_key": "<test-placeholder>-user-zai-key",
            "claude_model": "sonnet",
            "chunk_size_tokens": 500,
        }

    def test_input_is_not_mutated(self, migration):
        """The caller's dict is untouched — the transform returns a new one."""
        row = {"embedding_backend": "openai", "claude_model": "opus"}
        migration.strip_embedding_backend(row)
        assert row == {"embedding_backend": "openai", "claude_model": "opus"}


class TestRevisionChain:
    """The revision must sit on top of #31's, or neither applies."""

    def test_revision_identifiers(self, migration):
        assert migration.revision == "a7b8c9d0e1f2"
        assert migration.down_revision == "z6a7b8c9d0e1"

    def test_downgrade_is_a_documented_no_op(self, migration):
        """Nothing to restore: the key never changed any behaviour."""
        assert migration.downgrade() is None
