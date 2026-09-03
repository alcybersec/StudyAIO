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
    "JWT_SECRET_KEY": "<test-placeholder>",
    "POSTGRES_PASSWORD": "<test-placeholder>",
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


def _write_raw_env(tmp_path: Path, text: str) -> Path:
    """Write a literal .env body verbatim — for fixtures that need quoting
    _write_env can't produce (single- or double-quoted values, comments
    placed outside the quotes), e.g. reproducing
    `infisical export --format=dotenv` output.
    """
    path = tmp_path / ".env"
    path.write_text(text)
    return path


# Same shape as BASE_ENV, but every value is single-quoted — the format
# `infisical export --format=dotenv` actually emits on the host this script
# runs against.
QUOTED_BASE_ENV = {
    "JWT_SECRET_KEY": "<test-placeholder>",
    "POSTGRES_PASSWORD": "<test-placeholder>",
    "CORS_ORIGINS": "https://studyaio.example.com",
    "SELF_HOSTED": "false",
    "REGISTRATION_MODE": "invite",
    "SMTP_HOST": "smtp.resend.com",
    "SMTP_FROM_EMAIL": "beta@example.com",
    "COOKIE_SECURE": "true",
    "OPENAPI_ENABLED": "false",
    "GLOBAL_MAX_AI_CALLS_PER_DAY": "300",
    "AGENT_BACKEND": "claude_code",
}


def _quoted_env_text(**overrides) -> str:
    """Render QUOTED_BASE_ENV plus overrides as single-quoted KEY='value'
    lines. A None value omits the key. For fixtures needing double quotes or
    a comment outside the quotes, build the literal text by hand instead and
    pass it straight to _write_raw_env.
    """
    values = {**QUOTED_BASE_ENV, **overrides}
    return "".join(f"{k}='{v}'\n" for k, v in values.items() if v is not None)


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
        result = _run(_write_env(tmp_path, AGENT_BACKEND="zai", ZAI_API_KEY="<test-placeholder>"))
        assert result.returncode == 0, result.stdout
        assert "AGENT_BACKEND=zai with ZAI_API_KEY set" in result.stdout

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
        assert "mounted ~/.claude" in result.stdout

    def test_ollama_needs_no_key(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="ollama"))
        assert result.returncode == 0, result.stdout
        assert "no API key required" in result.stdout

    def test_unset_backend_defaults_to_claude_code(self, tmp_path):
        """An operator who never set AGENT_BACKEND is on the CLI default."""
        result = _run(_write_env(tmp_path, AGENT_BACKEND=None))
        assert result.returncode == 0, result.stdout
        assert "AGENT_BACKEND=claude_code" in result.stdout

    def test_an_unknown_backend_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="gpt5-turbo-max"))
        assert result.returncode == 1
        assert "[FAIL]" in result.stdout
        assert "is not one of" in result.stdout

    def test_a_trailing_inline_comment_does_not_break_a_valid_backend(self, tmp_path):
        """.env.example ships AGENT_BACKEND commented out with a trailing
        `# claude_code | anthropic_api | ...` hint; uncommenting it as-is is
        the obvious operator action and must not be read as part of the value.
        """
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="claude_code   # claude_code | anthropic_api | openai | zai | ollama",
            )
        )
        assert result.returncode == 0, result.stdout
        assert "AGENT_BACKEND=claude_code" in result.stdout


class TestSpendCeiling:
    """SaaS mode without a ceiling is a warning, not an error."""

    def test_warns_when_both_ceilings_are_unset(self, tmp_path):
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
                GLOBAL_MAX_AI_CALLS_PER_DAY=None,
            )
        )
        assert result.returncode == 0, result.stdout
        assert any("[WARN]" in ln and "GLOBAL_MAX_AI" in ln for ln in result.stdout.splitlines())

    def test_warns_when_both_ceilings_are_zero(self, tmp_path):
        """0 means unlimited, which is the same exposure as unset."""
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
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
                ZAI_API_KEY="<test-placeholder>",
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
        assert result.returncode == 0, result.stdout
        assert "GLOBAL_MAX_AI" not in result.stdout
        assert "Spend ceiling not enforced" in result.stdout

    def test_an_inline_comment_on_zero_still_warns(self, tmp_path):
        """A whitespace-preceded inline comment must not defeat the "0 counts
        as unlimited" comparison — this is the exact failure mode the fix in
        get_val exists to close.
        """
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
                GLOBAL_MAX_AI_CALLS_PER_DAY="0   # 0 = unlimited",
                GLOBAL_MAX_AI_TOKENS_PER_DAY="0   # 0 = unlimited",
            )
        )
        assert result.returncode == 0, result.stdout
        assert any("[WARN]" in ln and "GLOBAL_MAX_AI" in ln for ln in result.stdout.splitlines())


class TestQuotedValues:
    """`infisical export --format=dotenv` — the standard secret-management
    pattern on the host this script runs against — single-quotes every
    value. get_val must strip both quote styles, or every SaaS-mode branch
    below silently takes the self-hosted path instead.
    """

    def test_self_hosted_false_single_quoted_with_no_smtp_is_a_hard_fail(self, tmp_path):
        """The headline case: SELF_HOSTED='false' must still read as SaaS
        mode, so a missing SMTP config is a [FAIL], not a [WARN].
        """
        text = _quoted_env_text(SMTP_HOST=None, SMTP_FROM_EMAIL=None)
        result = _run(_write_raw_env(tmp_path, text))
        assert any("[FAIL]" in ln and "SMTP" in ln for ln in result.stdout.splitlines())
        assert result.returncode == 1

    def test_self_hosted_false_single_quoted_with_no_ceilings_is_a_warn(self, tmp_path):
        """SaaS mode with both spend ceilings absent must be the
        GLOBAL_MAX_AI [WARN], not the "not enforced (self-hosted...)" [ OK ]
        line that only applies to self-hosted installs.
        """
        text = _quoted_env_text(GLOBAL_MAX_AI_CALLS_PER_DAY=None)
        result = _run(_write_raw_env(tmp_path, text))
        assert any("[WARN]" in ln and "GLOBAL_MAX_AI" in ln for ln in result.stdout.splitlines())
        assert "not enforced (self-hosted" not in result.stdout

    def test_jwt_default_single_quoted_in_saas_mode_is_a_fail(self, tmp_path):
        text = _quoted_env_text(JWT_SECRET_KEY="changeme-in-production-use-a-real-secret")
        result = _run(_write_raw_env(tmp_path, text))
        assert any("[FAIL]" in ln and "JWT_SECRET_KEY" in ln for ln in result.stdout.splitlines())
        assert result.returncode == 1

    def test_postgres_password_default_single_quoted_is_a_warn(self, tmp_path):
        text = _quoted_env_text(POSTGRES_PASSWORD="studyaio")
        result = _run(_write_raw_env(tmp_path, text))
        assert any(
            "[WARN]" in ln and "POSTGRES_PASSWORD" in ln for ln in result.stdout.splitlines()
        )

    def test_registration_mode_open_single_quoted_is_recognised_and_warned(self, tmp_path):
        """Before the fix, `cut`+sed left the literal quotes in the value,
        so the case statement fell through to the `*)` branch and reported
        REGISTRATION_MODE as an invalid value instead of recognising 'open'.
        """
        text = _quoted_env_text(REGISTRATION_MODE="open")
        result = _run(_write_raw_env(tmp_path, text))
        assert any(
            "[WARN]" in ln and "REGISTRATION_MODE=open" in ln for ln in result.stdout.splitlines()
        )
        assert "is not one of" not in result.stdout

    def test_double_quoted_self_hosted_false_behaves_like_single_quoted(self, tmp_path):
        """Double quotes must parse the same way as single quotes."""
        text = (
            "JWT_SECRET_KEY='<test-placeholder>'\n"
            "POSTGRES_PASSWORD='<test-placeholder>'\n"
            "CORS_ORIGINS='https://studyaio.example.com'\n"
            'SELF_HOSTED="false"\n'
            "REGISTRATION_MODE='invite'\n"
            "COOKIE_SECURE='true'\n"
            "OPENAPI_ENABLED='false'\n"
            "GLOBAL_MAX_AI_CALLS_PER_DAY='300'\n"
            "AGENT_BACKEND='claude_code'\n"
        )
        result = _run(_write_raw_env(tmp_path, text))
        assert any("[FAIL]" in ln and "SMTP" in ln for ln in result.stdout.splitlines())
        assert result.returncode == 1

    def test_a_hash_inside_quotes_is_kept_as_part_of_the_value(self, tmp_path):
        """A `#` inside quotes is not a comment marker — python-dotenv (and
        now get_val) treats it as literal value content. Must not be
        truncated into something that happens to equal the default, and
        must not leave stray quote/hash fragments in the output.
        """
        text = _quoted_env_text(POSTGRES_PASSWORD="ab#cd")
        result = _run(_write_raw_env(tmp_path, text))
        assert any(
            "[ OK ]" in ln and "POSTGRES_PASSWORD is set to a custom value" in ln
            for ln in result.stdout.splitlines()
        )
        assert not any(
            "[WARN]" in ln and "POSTGRES_PASSWORD" in ln for ln in result.stdout.splitlines()
        )
        assert "cd'" not in result.stdout
        assert "'ab" not in result.stdout

    def test_unquoted_inline_comment_still_strips_no_regression(self, tmp_path):
        """Not a new scenario (TestSpendCeiling already covers this) — a
        cheap guard here that the quote-handling rewrite didn't regress the
        unquoted path.
        """
        text = _quoted_env_text(AGENT_BACKEND=None)
        text += (
            "AGENT_BACKEND=claude_code   # claude_code | anthropic_api | openai | zai | ollama\n"
        )
        result = _run(_write_raw_env(tmp_path, text))
        assert any(
            "[ OK ]" in ln and "AGENT_BACKEND=claude_code" in ln
            for ln in result.stdout.splitlines()
        )

    def test_quoted_value_with_trailing_comment_outside_the_quotes(self, tmp_path):
        """A comment placed after the closing quote (not inside it) must
        still be discarded, and the quoted value read correctly.
        """
        text = (
            "JWT_SECRET_KEY='<test-placeholder>'\n"
            "POSTGRES_PASSWORD='<test-placeholder>'\n"
            "CORS_ORIGINS='https://studyaio.example.com'\n"
            "SELF_HOSTED='false'   # SaaS\n"
            "REGISTRATION_MODE='invite'\n"
            "COOKIE_SECURE='true'\n"
            "OPENAPI_ENABLED='false'\n"
            "GLOBAL_MAX_AI_CALLS_PER_DAY='300'\n"
            "AGENT_BACKEND='claude_code'\n"
        )
        result = _run(_write_raw_env(tmp_path, text))
        assert any("[FAIL]" in ln and "SMTP" in ln for ln in result.stdout.splitlines())
        assert result.returncode == 1
