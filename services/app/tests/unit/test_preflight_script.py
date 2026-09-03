"""Tests for scripts/preflight-check.sh.

The script is the last gate before a beta deploy, so its checks are worth
guarding. It is bash, so these run it as a subprocess against generated .env
fixtures and assert on exit code and output.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[4] / "scripts" / "preflight-check.sh"

BASE_ENV = {
    "JWT_SECRET_KEY": "a-real-secret-value-not-the-default-one",
    "POSTGRES_PASSWORD": "not-studyaio",
    "CORS_ORIGINS": "https://studyaio.example.com",
    "SELF_HOSTED": "false",
    "REGISTRATION_MODE": "invite",
    "SMTP_HOST": "smtp.resend.com",
    "SMTP_FROM_EMAIL": "beta@example.com",
    "COOKIE_SECURE": "true",
    "OPENAPI_ENABLED": "false",
    "GLOBAL_MAX_AI_CALLS_PER_DAY": "300",
}


def _write_env(tmp_path: Path, **overrides) -> Path:
    """Write a .env fixture: BASE_ENV plus overrides. A None value omits a key."""
    values = {**BASE_ENV, **overrides}
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items() if v is not None))
    return path


def _run(env_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(env_file)],
        capture_output=True,
        text=True,
    )


@pytest.fixture(autouse=True)
def _requires_bash():
    if shutil.which("bash") is None:  # pragma: no cover - CI always has bash
        pytest.skip("bash not available")


class TestProviderCredential:
    """The selected AGENT_BACKEND must have the key it needs."""

    def test_zai_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="zai"))
        assert result.returncode == 1
        assert "ZAI_API_KEY" in result.stdout

    def test_zai_with_a_key_passes(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="zai", ZAI_API_KEY="zk-live-x"))
        assert result.returncode == 0, result.stdout

    def test_openai_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="openai"))
        assert result.returncode == 1
        assert "OPENAI_API_KEY" in result.stdout

    def test_anthropic_api_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="anthropic_api"))
        assert result.returncode == 1
        assert "ANTHROPIC_API_KEY" in result.stdout

    def test_claude_code_needs_no_key(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="claude_code"))
        assert result.returncode == 0, result.stdout

    def test_ollama_needs_no_key(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="ollama"))
        assert result.returncode == 0, result.stdout

    def test_unset_backend_defaults_to_claude_code(self, tmp_path):
        """An operator who never set AGENT_BACKEND is on the CLI default."""
        result = _run(_write_env(tmp_path, AGENT_BACKEND=None))
        assert result.returncode == 0, result.stdout

    def test_an_unknown_backend_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="gpt5-turbo-max"))
        assert result.returncode == 1
        assert "AGENT_BACKEND" in result.stdout


class TestSpendCeiling:
    """SaaS mode without a ceiling is a warning, not an error."""

    def test_warns_when_both_ceilings_are_unset(self, tmp_path):
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="zk-live-x",
                GLOBAL_MAX_AI_CALLS_PER_DAY=None,
            )
        )
        assert result.returncode == 0, result.stdout
        assert "WARN" in result.stdout
        assert "GLOBAL_MAX_AI" in result.stdout

    def test_warns_when_both_ceilings_are_zero(self, tmp_path):
        """0 means unlimited, which is the same exposure as unset."""
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="zk-live-x",
                GLOBAL_MAX_AI_CALLS_PER_DAY="0",
                GLOBAL_MAX_AI_TOKENS_PER_DAY="0",
            )
        )
        assert result.returncode == 0, result.stdout
        assert "GLOBAL_MAX_AI" in result.stdout

    def test_a_token_ceiling_alone_is_enough(self, tmp_path):
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="zk-live-x",
                GLOBAL_MAX_AI_CALLS_PER_DAY="0",
                GLOBAL_MAX_AI_TOKENS_PER_DAY="2000000",
            )
        )
        assert result.returncode == 0, result.stdout
        assert "Spend ceiling set" in result.stdout

    def test_self_hosted_is_not_warned(self, tmp_path):
        """A single-user box paying its own bill needs no ceiling."""
        result = _run(
            _write_env(
                tmp_path,
                SELF_HOSTED="true",
                AGENT_BACKEND="claude_code",
                SMTP_HOST=None,
                SMTP_FROM_EMAIL=None,
                GLOBAL_MAX_AI_CALLS_PER_DAY=None,
            )
        )
        assert "GLOBAL_MAX_AI" not in result.stdout
