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
