"""Floor 2 — the worker's long-lived Claude token (R-026) stays a secret.

User ruling (docs/decisions.md 2026-10-10, R-026): the claude_code worker logs
in with a long-lived ``claude setup-token`` token kept in
``<STUDYAIO_CLAUDE_LOGIN_DIR>/oauth-token``. The adapter reads the file named by
``CLAUDE_HOST_OAUTH_TOKEN_FILE`` per call and hands the token to the CLI only as
``CLAUDE_CODE_OAUTH_TOKEN`` in the child's environment. These pins hold the
token to that one channel:

* never on argv, never in the worker's own ``os.environ``;
* never in ``pipeline_runs``, a log, or a raised error and its cause chain,
  even when the CLI quotes it back;
* per-user Claude credentials win over it, and an auth failure on either is
  not retried on the operator's ``.credentials.json``;
* only the worker is told where the file is; no compose file or env template
  carries the token value itself;
* ``scripts/setup-claude-login.sh`` writes it 0600 in a 0700 dir and never
  prints it; the image pins the CLI version that receives it.

The CLI child is sandboxed (SAFETY-053, green since ai 31c1f28 and backend
def2701, confirmed SAFETY-057). ``claude -p`` reads
untrusted lecture text, and by default it may use its read-only tools
(Read/Glob/Grep need no approval, and outside ``--restricted`` they are not
confined to the working directory). A prompt-injected lecture can therefore ask
it to read ``/proc/self/environ``, ``/run/claude-host/oauth-token`` or
``/root/.claude/.credentials.json`` and write the contents into the summary the
uploader reads. That would hand the operator's token, the JWT secret (and with
it every other user's session, floor 1) and the instance AI keys to any
uploader. The child also inherits the worker's whole environment, and Sentry
ships the adapter's ``env`` local with every captured CLI failure.

* ``test_floor2_cli_runs_with_no_tools`` — ai passes ``--tools ""``.
* ``test_floor2_cli_environment_carries_no_worker_secret`` and
  ``..._is_exactly_the_reviewed_allowlist`` — the child env is built from an
  allowlist; widening it means editing ``CHILD_ENV_ALLOWED`` here.
* ``test_floor2_sentry_event_for_a_cli_failure_carries_no_credential`` — Sentry
  never ships frame locals. The allowlist alone is not enough: a short env dict
  falls inside Sentry's 10-item databag window, so the token would ship. Each
  of the two Sentry layers (``include_local_variables=False`` and the
  ``scrub_event`` frame-vars strip) is also pinned on its own.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from tests.safety._source import SERVICE_ROOT
from tests.safety.test_floor2_claude_login_mounts import (
    _as_non_root,
    _compose_files,
    _environment,
    _live_lines,
    _load,
)
from tests.safety.test_floor2_no_secrets import (
    HOST_SENTINEL,
    _host_credentials_file,
    _host_login_classify,
)

REPO_ROOT = SERVICE_ROOT.parents[1]
SETUP = REPO_ROOT / "scripts" / "setup-claude-login.sh"

TOKEN_SENTINEL = "floor2-sentinel-setup-token-c41d"
USER_SENTINEL = "floor2-sentinel-user-claude-token-8a27"
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"

# Planted in the worker's environment; none may reach the CLI child.
WORKER_SECRETS = {
    "JWT_SECRET_KEY": "floor2-sentinel-worker-jwt-secret-31aa",
    "DATABASE_URL": "postgresql+asyncpg://u:floor2-sentinel-worker-dbpass-31ab@db/x",
    "ANTHROPIC_API_KEY": "floor2-sentinel-worker-anthropic-31ac",
    "OPENAI_API_KEY": "floor2-sentinel-worker-openai-31ad",
    "ZAI_API_KEY": "floor2-sentinel-worker-zai-31ae",
    "STRIPE_API_KEY": "floor2-sentinel-worker-stripe-31af",
    # A name nobody lists: an allowlist drops it, a denylist would not.
    "FLOOR2_UNLISTED_INSTANCE_SECRET": "floor2-sentinel-worker-unlisted-31b0",
}


# ── fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def clean_home(tmp_path, monkeypatch):
    """No developer ``~/.claude`` login is read into the adapter's redaction set."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_HOST_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", raising=False)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    return home


@pytest.fixture
def token_file(tmp_path, monkeypatch, clean_home):
    path = tmp_path / "claude-host" / "oauth-token"
    path.parent.mkdir()
    path.write_text(TOKEN_SENTINEL + "\n")
    monkeypatch.setenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", str(path))
    return path


@pytest.fixture
def worker_secrets_first():
    """Put the planted worker secrets at the *front* of ``os.environ``.

    Sentry serialises at most 10 items of a dict local; production's
    ``env_file`` order puts real secrets anywhere, so the pin must not pass
    just because a test-appended variable fell past the window.
    """
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(WORKER_SECRETS)
    os.environ.update({k: v for k, v in saved.items() if k not in WORKER_SECRETS})
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


class _Cli:
    """Fake ``claude`` CLI that records argv and the environment it was given."""

    def __init__(self, returncode: int = 0, out: str = "ok", echo: bool = False) -> None:
        self.returncode = returncode
        self.out = out
        self.echo = echo
        self.calls: list[dict] = []

    async def __call__(self, *cmd, env=None, **_k):
        effective = dict(os.environ) if env is None else dict(env)
        self.calls.append(
            {
                "argv": [str(c) for c in cmd],
                "env": env,
                "effective": effective,
                "worker_environ_has_token": TOKEN_ENV in os.environ
                or TOKEN_SENTINEL in "".join(os.environ.values()),
            }
        )
        out = self.out
        if self.echo:
            out = f"{out} {effective.get(TOKEN_ENV, '')}"
        process = MagicMock()
        process.returncode = self.returncode
        process.communicate = AsyncMock(return_value=(out.encode(), b""))
        return process


def _adapter(credentials: dict | None = None):
    from app.agents.claude_code import ClaudeCodeAdapter

    with patch("app.agents.claude_code.get_effective_setting", return_value="claude"):
        return ClaudeCodeAdapter(credentials_json=credentials)


def _user_credentials() -> dict:
    return {"claudeAiOauth": {"accessToken": USER_SENTINEL, "refreshToken": USER_SENTINEL + "-r"}}


async def _run(adapter, cli: _Cli):
    with patch.object(asyncio, "create_subprocess_exec", cli):
        return await adapter._run_claude_code("lecture prompt")


# ── the token's one channel ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor2_setup_token_reaches_the_cli_only_through_its_environment(token_file):
    """Child env only: not argv (``ps``-visible), not the worker's ``os.environ``."""
    cli = _Cli()
    with structlog.testing.capture_logs() as events:
        await _run(_adapter(), cli)

    assert len(cli.calls) == 1
    call = cli.calls[0]
    assert call["env"] is not None and call["env"].get(TOKEN_ENV) == TOKEN_SENTINEL, (
        "the setup token was not handed to the CLI, so this test proves nothing"
    )
    assert not any(TOKEN_SENTINEL in a for a in call["argv"]), (
        f"Floor 2: the setup token is on the CLI's argv {call['argv']}"
    )
    assert not call["worker_environ_has_token"], (
        "Floor 2: the setup token was put in the worker's own os.environ during the call"
    )
    assert TOKEN_ENV not in os.environ and TOKEN_SENTINEL not in "".join(os.environ.values())
    assert TOKEN_SENTINEL not in repr(events), "Floor 2: the setup token was logged"


def test_floor2_setup_token_echoed_on_auth_failure_never_stores_or_logs_and_is_not_retried(
    token_file, tmp_path, monkeypatch, caplog
):
    """A revoked token, quoted back by the CLI, through the real classify task.

    The operator's ``.credentials.json`` fallback is configured and valid, and
    must not be spent: with a token configured, an auth failure is final.
    """
    monkeypatch.setenv("CLAUDE_HOST_CREDENTIALS_FILE", str(_host_credentials_file(tmp_path)))
    cli = _Cli(returncode=1, out="401 OAuth token has been revoked:", echo=True)
    caplog.set_level(logging.DEBUG)

    async def fake(*cmd, env=None, **kw):
        return await cli(*cmd, env=env, **kw)

    with structlog.testing.capture_logs() as events:
        raised, stored = _host_login_classify(fake)

    assert len(cli.calls) == 1, (
        f"an auth failure on the setup token was retried ({len(cli.calls)} CLI calls)"
    )
    assert not (cli.calls[0]["env"] or {}).get("CLAUDE_CONFIG_DIR")
    assert stored and raised is not None, "the task did not fail, so this test proves nothing"
    chain = "".join(traceback.format_exception(raised))
    assert "401" in chain, "the CLI's failure text was dropped, so this test proves nothing"
    for text, where in (
        ("\n".join(stored), "pipeline_runs.error_message"),
        (repr(events), "structlog events"),
        (caplog.text, "stdlib log records"),
        (chain, "the task's exception and its cause chain"),
    ):
        assert TOKEN_SENTINEL not in text, f"Floor 2: the setup token appears in {where}"
        assert HOST_SENTINEL not in text, f"Floor 2: the fallback host login appears in {where}"


@pytest.mark.asyncio
async def test_floor2_setup_token_echoed_on_any_failure_is_redacted(token_file):
    """A non-auth CLI failure that quotes the token raises a redacted AgentError."""
    from app.core.exceptions import AgentError

    cli = _Cli(returncode=1, out="error: request rejected for", echo=True)
    with structlog.testing.capture_logs() as events, pytest.raises(AgentError) as info:
        await _run(_adapter(), cli)

    chain = "".join(traceback.format_exception(info.value))
    assert "request rejected" in chain, "the failure text was dropped, so this proves nothing"
    assert TOKEN_SENTINEL not in chain, "Floor 2: the setup token is in the raised error"
    assert TOKEN_SENTINEL not in repr(events), "Floor 2: the setup token was logged"


@pytest.mark.asyncio
async def test_floor2_per_user_credentials_win_over_the_setup_token(token_file):
    """A user's own login runs alone: the operator's token is neither added nor handed back."""
    from app.core.exceptions import AgentError

    seen_files: list[str] = []

    class _Refreshing(_Cli):
        async def __call__(self, *cmd, env=None, **kw):
            process = await super().__call__(*cmd, env=env, **kw)
            config_dir = pathlib.Path((env or {}).get("CLAUDE_CONFIG_DIR", "/nonexistent"))
            if config_dir.is_dir():
                seen_files.extend(p.read_text() for p in config_dir.iterdir() if p.is_file())
                rotated = {"claudeAiOauth": {"accessToken": USER_SENTINEL + "-rotated"}}
                (config_dir / ".credentials.json").write_text(json.dumps(rotated))
            return process

    adapter = _adapter(_user_credentials())
    cli = _Refreshing()
    await _run(adapter, cli)

    env = cli.calls[0]["env"] or {}
    assert env.get("CLAUDE_CONFIG_DIR"), "the per-user run got no config dir; proves nothing"
    assert TOKEN_ENV not in env, (
        "Floor 1/2: a per-user-credential run was also handed the operator's setup token"
    )
    assert seen_files and not any(TOKEN_SENTINEL in s for s in seen_files)
    assert USER_SENTINEL in json.dumps(adapter.refreshed_credentials or {})
    assert TOKEN_SENTINEL not in json.dumps(adapter.refreshed_credentials or {})

    # The user's login is revoked: fail, do not fall back to the operator's token.
    revoked = _Cli(returncode=1, out="401 OAuth token has been revoked")
    with pytest.raises(AgentError):
        await _run(_adapter(_user_credentials()), revoked)
    assert len(revoked.calls) == 1, "a per-user auth failure was retried on the host login"
    assert TOKEN_ENV not in (revoked.calls[0]["env"] or {})


# ── where the token lives ────────────────────────────────────────────────

TOKEN_FILE_TARGET_DIR = "/run/claude-host/"


def test_floor2_only_the_worker_is_told_where_the_setup_token_is():
    """``CLAUDE_HOST_OAUTH_TOKEN_FILE`` is worker-only and points into the ro login mount."""
    base_env, _ = _environment(_load(REPO_ROOT / "docker-compose.yml")["services"]["worker"])
    assert base_env.get("CLAUDE_HOST_OAUTH_TOKEN_FILE", "").startswith(TOKEN_FILE_TARGET_DIR), (
        "docker-compose.yml: worker has no CLAUDE_HOST_OAUTH_TOKEN_FILE under "
        f"{TOKEN_FILE_TARGET_DIR}; this pin would prove nothing"
    )
    bad = []
    for path in _compose_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        for name, service in (_load(path).get("services") or {}).items():
            env, _ = _environment(service or {})
            value = env.get("CLAUDE_HOST_OAUTH_TOKEN_FILE")
            if value is None:
                continue
            if name != "worker":
                bad.append(f"{rel}: {name} is told where the setup token is")
            elif not value.startswith(TOKEN_FILE_TARGET_DIR):
                bad.append(f"{rel}: worker reads the setup token from {value!r}")
    assert not bad, "Floor 2 (R-026):\n" + "\n".join(bad)


_TOKEN_VALUE_VARS = re.compile(r"\b(CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_AUTH_TOKEN)\b")


def test_floor2_no_compose_or_env_template_carries_the_token_value():
    """The token never sits in a compose ``environment`` (``docker inspect``) or ``.env``."""
    hits = []
    for path in [*_compose_files(), REPO_ROOT / ".env.example"]:
        for n, line in _live_lines(path):
            if _TOKEN_VALUE_VARS.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{n}  {line.strip()}")
    assert not hits, "Floor 2 (R-026): token value variable set in config:\n" + "\n".join(hits)


def test_floor2_worker_image_pins_the_claude_cli_version():
    """The binary that receives the operator's token is a fixed, reviewed release."""
    text = (SERVICE_ROOT / "Dockerfile").read_text()
    installs = re.findall(r"@anthropic-ai/claude-code(@\S+)?", text)
    assert installs, "services/app/Dockerfile no longer installs the Claude CLI; update this pin"
    floating = [i for i in installs if not re.fullmatch(r"@\d+\.\d+\.\d+", i or "")]
    assert not floating, f"Floor 2: the Claude CLI install is not pinned to a version: {installs}"


# ── setup-claude-login.sh, run for real ──────────────────────────────────


def _script_sandbox() -> pathlib.Path:
    base = pathlib.Path(tempfile.mkdtemp(prefix="floor2-token-"))
    base.chmod(0o777)  # reachable by the unprivileged uid when the suite runs as root
    (base / "home").mkdir()
    return base


def _chown_for_script(base: pathlib.Path) -> None:
    if os.geteuid() == 0:
        for p in [base, *base.rglob("*")]:
            os.chown(p, 65534, 65534)


def _setup(base: pathlib.Path, *args: str, token: str = "") -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(base / "home")}
    return subprocess.run(
        [*_as_non_root(), "bash", str(SETUP), *args],
        env=env,
        input=token,
        capture_output=True,
        text=True,
        check=False,
    )


def test_floor2_setup_script_stores_the_token_private_and_never_prints_it():
    base = _script_sandbox()
    target = base / "claude-login"
    _chown_for_script(base)
    try:
        first = _setup(base, str(target), token=TOKEN_SENTINEL + "\n")
        dir_mode = target.stat().st_mode & 0o777
        token_path = target / "oauth-token"
        token_mode = token_path.stat().st_mode & 0o777 if token_path.exists() else None
        stored = token_path.read_text().strip() if token_path.exists() else None
        listing = sorted(p.name for p in target.iterdir())
        placeholder = target / ".credentials.json"
        placeholder_text = placeholder.read_text().strip() if placeholder.exists() else "{}"
        placeholder_mode = placeholder.stat().st_mode & 0o077 if placeholder.exists() else 0

        kept = _setup(base, str(target), token="floor2-sentinel-second-token-77\n")
        after_keep = token_path.read_text().strip()
        rotated = _setup(base, "--rotate", str(target), token="floor2-sentinel-rotated-88\n")
        after_rotate = token_path.read_text().strip()
        token_mode_after = token_path.stat().st_mode & 0o777
        leftovers = [p.name for p in target.iterdir() if p.name.startswith(".oauth-token")]
    finally:
        shutil.rmtree(base, ignore_errors=True)

    assert first.returncode == 0, first.stderr
    assert dir_mode == 0o700, f"login dir mode {oct(dir_mode)}, want 0o700"
    assert stored == TOKEN_SENTINEL, "the script did not store the token it was given"
    assert token_mode == 0o600, f"oauth-token mode {oct(token_mode or 0)}, want 0o600"
    assert set(listing) <= {"settings.json", ".credentials.json", "oauth-token"}, listing
    assert placeholder_text == "{}" and placeholder_mode == 0, (
        ".credentials.json is more than a private '{}' placeholder"
    )
    for run in (first, kept, rotated):
        assert TOKEN_SENTINEL not in run.stdout + run.stderr, "the script printed the token"
        assert "floor2-sentinel-second-token-77" not in run.stdout + run.stderr
        assert "floor2-sentinel-rotated-88" not in run.stdout + run.stderr
    assert kept.returncode == 0 and after_keep == TOKEN_SENTINEL, (
        "a re-run without --rotate replaced the stored token"
    )
    assert rotated.returncode == 0 and after_rotate == "floor2-sentinel-rotated-88"
    assert token_mode_after == 0o600 and not leftovers, (token_mode_after, leftovers)


def test_floor2_setup_script_refuses_the_personal_claude_dir():
    """Pointed at ``$HOME/.claude`` it writes nothing there and changes no mode."""
    base = _script_sandbox()
    personal = base / "home" / ".claude"
    personal.mkdir()
    personal.chmod(0o755)
    (personal / "history.jsonl").write_text("{}\n")
    _chown_for_script(base)
    try:
        run = _setup(base, str(personal), token=TOKEN_SENTINEL + "\n")
        listing = sorted(p.name for p in personal.iterdir())
        mode = personal.stat().st_mode & 0o777
    finally:
        shutil.rmtree(base, ignore_errors=True)

    assert run.returncode != 0, "the script accepted the personal ~/.claude as the login dir"
    assert listing == ["history.jsonl"], f"the script wrote into the personal ~/.claude: {listing}"
    assert mode == 0o755, f"the script changed the personal ~/.claude mode to {oct(mode)}"
    assert TOKEN_SENTINEL not in run.stdout + run.stderr


# ── SAFETY-053: the CLI child is sandboxed (green since SAFETY-057) ───────

MODES = ["setup_token", "per_user", "host_login"]


async def _run_mode(mode: str, tmp_path: pathlib.Path, monkeypatch, cli: _Cli):
    if mode == "setup_token":
        path = tmp_path / "claude-host" / "oauth-token"
        path.parent.mkdir(exist_ok=True)
        path.write_text(TOKEN_SENTINEL + "\n")
        monkeypatch.setenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", str(path))
    adapter = _adapter(_user_credentials() if mode == "per_user" else None)
    return adapter, await _run(adapter, cli)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_cli_runs_with_no_tools(mode, tmp_path, monkeypatch, clean_home):
    """``claude -p`` over untrusted lecture text gets no tools.

    With its default tools the CLI can Read ``/proc/self/environ``, the
    mounted ``oauth-token`` / ``.credentials.json`` or a user's temp config
    dir, and a prompt-injected lecture can have it write them into the
    summary the uploader reads. The adapter only ever wants text back, so the
    fix is ``--tools ""`` (supported by the pinned 2.1.286) on every call.
    """
    cli = _Cli()
    await _run_mode(mode, tmp_path, monkeypatch, cli)
    argv = cli.calls[0]["argv"]
    no_tools = "--tools=" in argv or (
        "--tools" in argv
        and argv.index("--tools") + 1 < len(argv)
        and argv[argv.index("--tools") + 1] == ""
    )
    assert no_tools, (
        f"Floor 2 ({mode}): the CLI runs with its default tools ({argv}); a prompt-injected "
        "lecture can make it read the worker's environment or the mounted Claude login"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_cli_environment_carries_no_worker_secret(
    mode, tmp_path, monkeypatch, clean_home, worker_secrets_first
):
    """The CLI child gets an allowlisted env, not ``{**os.environ}``.

    ``env=None`` inherits everything, so it counts as a leak too. The login
    the mode needs must still be there.
    """
    cli = _Cli()
    await _run_mode(mode, tmp_path, monkeypatch, cli)
    effective = cli.calls[0]["effective"]
    if mode == "setup_token":
        assert effective.get(TOKEN_ENV) == TOKEN_SENTINEL, "the fix dropped the setup token"
    if mode == "per_user":
        assert effective.get("CLAUDE_CONFIG_DIR"), "the fix dropped the per-user config dir"
    leaked = sorted(k for k, v in WORKER_SECRETS.items() if v in effective.values())
    assert not leaked, (
        f"Floor 2 ({mode}): the CLI child, which reads untrusted lecture text, "
        f"inherits worker secrets {leaked}"
    )


# The only names the CLI child may see (SAFETY-057). The sentinel pin above
# catches the secrets it plants; this one catches a name nobody planted, e.g.
# ``REDIS_URL`` (password-bearing) added to the adapter's allowlist. Widening
# it is a floor-2 decision: change this set in the same review.
CHILD_ENV_ALLOWED = {"PATH", "HOME", "LANG", "LC_ALL", "CLAUDE_CONFIG_DIR", TOKEN_ENV}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_cli_environment_is_exactly_the_reviewed_allowlist(
    mode, tmp_path, monkeypatch, clean_home, worker_secrets_first
):
    """The child's env names are a subset of ``CHILD_ENV_ALLOWED``, in every mode.

    ``REDIS_URL`` and ``SENTRY_DSN`` are set so a widened allowlist has
    something to pass through; ``env=None`` / ``{**os.environ}`` fail here too.
    """
    monkeypatch.setenv("REDIS_URL", "redis://:floor2-redis-pass@redis:6379/0")
    monkeypatch.setenv("SENTRY_DSN", "https://k@sentry.invalid/1")
    monkeypatch.setenv("LANG", "C.UTF-8")
    cli = _Cli()
    await _run_mode(mode, tmp_path, monkeypatch, cli)
    effective = cli.calls[0]["effective"]
    extra = sorted(set(effective) - CHILD_ENV_ALLOWED)
    assert not extra, (
        f"Floor 2 ({mode}): the CLI child, which reads untrusted lecture text, gets "
        f"unreviewed variables {extra}"
    )
    if mode != "setup_token":
        assert TOKEN_ENV not in effective, f"{mode}: the operator token reached a non-token run"


@pytest.fixture
def sentry_events(monkeypatch):
    """Initialise Sentry through the app's own ``init_sentry`` into a capturing transport."""
    import sentry_sdk
    from sentry_sdk.transport import Transport

    from app.core import observability

    events: list[dict] = []

    class _Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.payload.json:
                    events.append(item.payload.json)

    real_init = sentry_sdk.init

    def init(*args, **kwargs):
        kwargs["transport"] = _Capture
        return real_init(*args, **kwargs)

    monkeypatch.setattr(sentry_sdk, "init", init)
    monkeypatch.setattr(observability, "_initialized", False)
    monkeypatch.setattr(observability, "_build_integrations", lambda _c: [])
    monkeypatch.setattr(observability.settings, "sentry_dsn", "https://k@sentry.invalid/1")
    assert observability.init_sentry("worker")
    try:
        yield events
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)
        observability._initialized = False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_sentry_event_for_a_cli_failure_carries_no_credential(
    mode, tmp_path, monkeypatch, clean_home, worker_secrets_first, sentry_events
):
    """A captured CLI failure ships no secret to Sentry.

    Sentry attaches each frame's locals; ``_run_once`` holds ``env`` (the
    child's environment) and ``credentials``. The default scrubber only
    filters top-level names like ``token``/``credentials``, not keys nested in
    ``env``, and the app's ``scrub_event`` does not touch frames. Fix in
    ``core/observability.py``: ``include_local_variables=False``.
    """
    import sentry_sdk

    from app.core.exceptions import AgentError

    cli = _Cli(returncode=1, out="error: overloaded")
    with pytest.raises(AgentError) as info:
        await _run_mode(mode, tmp_path, monkeypatch, cli)
    sentry_sdk.capture_exception(info.value)
    sentry_sdk.flush()

    assert sentry_events, "no Sentry event was captured, so this test proves nothing"
    blob = json.dumps(sentry_events)
    secrets = {**WORKER_SECRETS, "setup token": TOKEN_SENTINEL, "user token": USER_SENTINEL}
    leaked = sorted(k for k, v in secrets.items() if v in blob)
    assert not leaked, f"Floor 2 ({mode}): a captured CLI failure sends {leaked} to Sentry"


# Each Sentry layer alone (SAFETY-057): the end-to-end pin above goes red only
# when BOTH are gone, so a regression of one would pass silently.


def test_floor2_sentry_is_initialised_without_frame_locals(monkeypatch):
    """Layer 1: ``init_sentry`` passes ``include_local_variables=False``."""
    import sentry_sdk

    from app.core import observability

    seen: dict = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: seen.update(k))
    monkeypatch.setattr(sentry_sdk, "set_tag", lambda *a, **k: None)
    monkeypatch.setattr(observability, "_initialized", False)
    monkeypatch.setattr(observability, "_build_integrations", lambda _c: [])
    monkeypatch.setattr(observability.settings, "sentry_dsn", "https://k@sentry.invalid/1")
    observability.init_sentry("worker")
    assert seen, "init_sentry never reached sentry_sdk.init, so this test proves nothing"
    assert seen.get("include_local_variables") is False, (
        "Floor 2: Sentry ships frame locals, e.g. _run_once's env holding the Claude token"
    )


@pytest.mark.parametrize("container", ["exception", "threads"])
def test_floor2_scrub_event_drops_frame_locals(container):
    """Layer 2: ``scrub_event`` strips ``vars`` from every frame, whatever the SDK sent."""
    from app.core.observability import scrub_event

    frame = {"function": "_run_once", "vars": {"env": {TOKEN_ENV: TOKEN_SENTINEL}}}
    event = {container: {"values": [{"stacktrace": {"frames": [frame]}}]}}
    out = scrub_event(event, {})
    assert out is not None
    assert TOKEN_SENTINEL not in json.dumps(out), (
        f"Floor 2: scrub_event leaves frame locals in {container} frames"
    )
