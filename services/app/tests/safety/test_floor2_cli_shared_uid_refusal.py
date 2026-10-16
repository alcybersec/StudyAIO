"""Floors 1 and 2: a non-root AI pool refuses the Claude CLI unless the operator opts in.

M34-S2-SEC-006, option F (``docs/gates/M34/sec006-safety.md`` §3, §5.2). The AI
pools run as uid 999 so untrusted PDF/DOCX/PPTX is no longer parsed as root. A
uid-999 process cannot ``setuid``/``chown``, so the ``claude -p`` child can no
longer be dropped to ``claudecli`` (10001, AGENT-01, R-030). At the worker's uid
the child could read ``/proc/<worker>/environ`` (JWT secret, database URL,
``SETTINGS_ENCRYPTION_KEY``) and every tenant's ``data/``. Option F turns that
lost isolation into a refused configuration instead of a silent one:

* non-root, multi-user, no opt-in: ``ClaudeCliUnavailableError`` before the
  operator token, the host login or the user's credentials are read, written to
  a temp dir or handed to anything, and before ``create_subprocess_exec``. For
  the instance login (setup token, host ``.credentials.json``) and the per-user
  one alike, directly and through ``get_agent`` and a real pipeline stage;
* the refusal is a plain ``AgentError`` (never transient: retrying cannot help),
  counted on ``studyaio_claude_cli_spawn_refusals_total`` and logged once, with
  no credential in the message, the log or the metric;
* ``CLAUDE_CLI_UID`` on a non-root worker is refused in every mode, opt-in and
  ``SINGLE_USER_MODE`` included, as that configuration error and never as a
  mid-call ``PermissionError`` from ``os.chown``;
* ``CLAUDE_CLI_SHARED_UID_ACCEPTED`` (true/1/yes/on) or ``SINGLE_USER_MODE``
  (one tenant) spawns, at the worker's uid;
* a root worker is unchanged: it spawns without the opt-in and drops to
  ``CLAUDE_CLI_UID`` when set.

``os.geteuid`` is pinned in every test, so the tier means the same as root (CI)
and as a developer. The mutation check (guard call deleted in a scratch copy of
``app/``) turns the refusal pins red; see ``FLOORS.md``.
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import logging
import os
import pathlib
import tempfile
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from tests.safety._source import APP_ROOT, parse

OPT_IN = "CLAUDE_CLI_SHARED_UID_ACCEPTED"
TOKEN_SENTINEL = "floor2-sentinel-f-setup-token-6d01"
HOST_SENTINEL = "floor2-sentinel-f-host-login-6d02"
USER_SENTINEL = "floor2-sentinel-f-user-login-6d03"
CLI_UID = 54321
POOL_UID = 999

MODES = ["setup_token", "host_login", "per_user"]


def _oauth(token: str) -> dict:
    return {"claudeAiOauth": {"accessToken": token, "refreshToken": token + "-r"}}


class _Spy:
    """Records every CLI spawn, every file opened, every temp dir and chown."""

    def __init__(self) -> None:
        self.spawns: list[dict] = []
        self.opened: list[str] = []
        self.mkdtemp: list[str] = []
        self.chown: list[tuple] = []

    async def spawn(self, *cmd, env=None, **opts):
        self.spawns.append({"argv": [str(c) for c in cmd], "env": dict(env or {}), "opts": opts})
        process = MagicMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b'{"course_code": "CSIT302"}', b""))
        return process


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    """A worker with every instance login configured, and spies on what it touches.

    Returns a setter ``deploy(euid=..., opt_in=..., single_user=..., cli_uid=...)``.
    """
    from app.agents import claude_code

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".credentials.json").write_text(json.dumps(_oauth(HOST_SENTINEL)))
    host = tmp_path / "claude-host"
    host.mkdir()
    (host / ".credentials.json").write_text(json.dumps(_oauth(HOST_SENTINEL)))
    (host / "oauth-token").write_text(TOKEN_SENTINEL + "\n")
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(tmp))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    monkeypatch.setenv("CLAUDE_HOST_CREDENTIALS_FILE", str(host / ".credentials.json"))
    for name in ("CLAUDE_HOST_OAUTH_TOKEN_FILE", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CLI_GID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        claude_code,
        "get_effective_setting",
        lambda k: {"claude_code_path": "claude", "claude_model": "m"}.get(k, ""),
    )
    monkeypatch.setattr(claude_code, "_refusal_logged", set())

    spy = _Spy()
    real_open, real_mkdtemp = builtins.open, tempfile.mkdtemp

    def recording_open(file, *a, **k):
        spy.opened.append(os.fspath(file) if isinstance(file, str | os.PathLike) else str(file))
        return real_open(file, *a, **k)

    def recording_mkdtemp(*a, **k):
        path = real_mkdtemp(*a, **k)
        spy.mkdtemp.append(path)
        return path

    monkeypatch.setattr(builtins, "open", recording_open)
    monkeypatch.setattr(tempfile, "mkdtemp", recording_mkdtemp)
    monkeypatch.setattr(os, "chown", lambda *a: spy.chown.append(a))

    def deploy(
        *,
        euid: int,
        opt_in: str | None = None,
        single_user: bool = False,
        cli_uid: bool = False,
        mode: str = "host_login",
    ) -> _Spy:
        monkeypatch.setattr(os, "geteuid", lambda: euid)
        monkeypatch.setattr(claude_code.settings, "single_user_mode", single_user)
        if opt_in is None:
            monkeypatch.delenv(OPT_IN, raising=False)
        else:
            monkeypatch.setenv(OPT_IN, opt_in)
        if cli_uid:
            monkeypatch.setenv("CLAUDE_CLI_UID", str(CLI_UID))
        else:
            monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
        if mode == "setup_token":
            monkeypatch.setenv("CLAUDE_HOST_OAUTH_TOKEN_FILE", str(host / "oauth-token"))
        return spy

    deploy.tmp = tmp  # type: ignore[attr-defined]
    deploy.host = host  # type: ignore[attr-defined]
    return deploy


def _adapter(mode: str):
    from app.agents.claude_code import ClaudeCodeAdapter

    return ClaudeCodeAdapter(credentials_json=_oauth(USER_SENTINEL) if mode == "per_user" else None)


async def _call(adapter, spy: _Spy) -> str:
    with patch.object(asyncio, "create_subprocess_exec", spy.spawn):
        return await adapter._run_claude_code("lecture prompt")


def _refusals() -> float:
    from app.agents.claude_code import CLI_SPAWN_REFUSALS

    return CLI_SPAWN_REFUSALS.labels(
        stage="claude_cli_spawn", outcome="refused", error_class="ClaudeCliUnavailableError"
    )._value.get()


def _read_login_files(spy: _Spy) -> list[str]:
    secrets = {"oauth-token", ".credentials.json"}
    return [p for p in spy.opened if pathlib.Path(p).name in secrets]


# ── refusal: non-root, multi-user, no opt-in ─────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("opt_in", [None, "", "false", "0", "no", "off", "accepted"])
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_nonroot_multi_user_refuses_before_any_login_is_read_or_spawned(
    mode, opt_in, deployment, caplog
):
    """No spawn, no login file opened, no temp dir, no chown; a typed, non-transient error."""
    from app.agents.claude_code import ClaudeCliUnavailableError
    from app.agents.transient import TransientAgentError
    from app.core.exceptions import AgentError

    spy = deployment(euid=POOL_UID, opt_in=opt_in, mode=mode)
    before = _refusals()
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as events, pytest.raises(AgentError) as info:
        await _call(_adapter(mode), spy)

    assert isinstance(info.value, ClaudeCliUnavailableError), (
        f"refused with {type(info.value).__name__}, not the SEC-006 configuration error"
    )
    assert not isinstance(info.value, TransientAgentError), "a refusal must not be retried"
    assert spy.spawns == [], (
        f"Floor 1/2 (SEC-006, {mode}): a non-root multi-user worker spawned the Claude CLI at "
        "its own uid; the child can read the worker's environment and every tenant's data/"
    )
    assert _read_login_files(spy) == [], (
        f"{mode}: a login was read before the refusal: {_read_login_files(spy)}"
    )
    assert spy.mkdtemp == [] and spy.chown == [], (spy.mkdtemp, spy.chown)
    assert os.listdir(deployment.tmp) == [], "the refusal left a per-call dir behind"
    assert _refusals() == before + 1, "the refusal was not counted"
    chain = "".join(traceback.format_exception(info.value))
    for text in (chain, repr(events), caplog.text):
        for sentinel in (TOKEN_SENTINEL, HOST_SENTINEL, USER_SENTINEL):
            assert sentinel not in text, f"Floor 2: a credential is in the refusal ({mode})"
    assert "CLAUDE_CLI_SHARED_UID_ACCEPTED" in str(info.value), "the refusal names no remedy"


@pytest.mark.asyncio
async def test_floor2_refusal_is_logged_once_and_counted_every_time(deployment):
    spy = deployment(euid=POOL_UID)
    from app.core.exceptions import AgentError

    before = _refusals()
    with structlog.testing.capture_logs() as events:
        for _ in range(3):
            with pytest.raises(AgentError):
                await _call(_adapter("host_login"), spy)
    refused = [e for e in events if e.get("event") == "claude_cli_spawn_refused"]
    assert len(refused) == 1, f"claude_cli_spawn_refused logged {len(refused)} times"
    assert set(refused[0]) <= {"event", "reason", "log_level", "timestamp"}, refused[0]
    assert _refusals() == before + 3
    assert spy.spawns == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["host_login", "per_user"])
async def test_floor2_refusal_holds_through_get_agent(mode, deployment):
    """The factory's instance and per-user ``claude_code`` adapters both refuse."""
    from app.agents.claude_code import ClaudeCliUnavailableError
    from app.agents.factory import get_agent

    spy = deployment(euid=POOL_UID, mode=mode)
    config = None
    if mode == "per_user":
        from app.services.settings_service import _agent_config_from_overrides

        config = _agent_config_from_overrides(
            {
                "agent_backend": "claude_code",
                "claude_cli_credentials": json.dumps(_oauth(USER_SENTINEL)),
            }
        )
        assert config and config["agent_backend"] == "claude_code", config
    with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
        agent = get_agent(user_settings=config)
    with (
        patch.object(asyncio, "create_subprocess_exec", spy.spawn),
        pytest.raises(ClaudeCliUnavailableError),
    ):
        await agent.classify_lecture("CSIT302 week 1", "CSIT302_week1.pdf", [])
    assert spy.spawns == [], f"{mode}: get_agent's claude_code adapter spawned the CLI"


def test_floor2_refusal_fails_a_real_stage_once_without_a_retry_or_a_spawn(
    deployment, monkeypatch, caplog
):
    """classify on the host login: one failed run, no CLI call, no login in the record."""
    from tests.safety.test_floor2_no_secrets import _host_login_classify

    spy = deployment(euid=POOL_UID, mode="setup_token")
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as events:
        raised, stored = _host_login_classify(spy.spawn)

    assert spy.spawns == [], "Floor 1/2 (SEC-006): classify spawned the CLI on a refused pool"
    assert raised is not None and len(stored) == 1, (raised, stored)
    assert "ClaudeCliUnavailableError" in [type(e).__name__ for e in _chain(raised)], (
        f"the stage failed for another reason ({raised!r}), so this test proves nothing"
    )
    assert "CLAUDE_CLI_SHARED_UID_ACCEPTED" in stored[0], "the run record hides the remedy"
    for text in ("\n".join(stored), repr(events), caplog.text):
        assert TOKEN_SENTINEL not in text and HOST_SENTINEL not in text


def _chain(exc: BaseException | None):
    while exc is not None:
        yield exc
        exc = exc.__cause__ or exc.__context__


# ── CLAUDE_CLI_UID on a non-root worker ──────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("opt_in", "single_user"),
    [(None, False), ("true", False), (None, True), ("true", True)],
    ids=["multi-user", "opted-in", "single-user", "both"],
)
async def test_floor2_cli_uid_on_a_nonroot_worker_is_refused_in_every_mode(
    opt_in, single_user, deployment
):
    """A drop that cannot happen is a configuration error, never a mid-call PermissionError."""
    from app.agents.claude_code import ClaudeCliUnavailableError

    spy = deployment(euid=POOL_UID, opt_in=opt_in, single_user=single_user, cli_uid=True)

    def chown_as_non_root(*_a):
        raise PermissionError("chown as non-root")

    with (
        patch.object(os, "chown", chown_as_non_root),
        pytest.raises(ClaudeCliUnavailableError) as info,
    ):
        await _call(_adapter("per_user"), spy)
    assert "CLAUDE_CLI_UID" in str(info.value)
    assert spy.spawns == [] and spy.mkdtemp == []


# ── allowed: opt-in, single-user, root ───────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("opt_in", ["true", "TRUE", "1", "yes", " on "])
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_operator_opt_in_spawns_at_the_worker_uid(mode, opt_in, deployment):
    spy = deployment(euid=POOL_UID, opt_in=opt_in, mode=mode)
    await _call(_adapter(mode), spy)
    assert len(spy.spawns) == 1, f"opt-in {opt_in!r} did not spawn"
    assert "user" not in spy.spawns[0]["opts"], "a non-root worker tried to drop"
    assert spy.chown == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_single_user_mode_spawns_without_the_opt_in(mode, deployment):
    """One tenant: no other user's data or session for the child to reach."""
    spy = deployment(euid=POOL_UID, single_user=True, mode=mode)
    await _call(_adapter(mode), spy)
    assert len(spy.spawns) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_root_worker_is_unchanged_without_the_opt_in(mode, deployment):
    spy = deployment(euid=0, mode=mode)
    await _call(_adapter(mode), spy)
    assert len(spy.spawns) == 1
    assert "user" not in spy.spawns[0]["opts"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", MODES)
async def test_floor2_root_worker_still_drops_to_the_cli_uid(mode, deployment):
    """AGENT-01 / R-030 on a root worker: the child runs as CLAUDE_CLI_UID, not root."""
    spy = deployment(euid=0, cli_uid=True, mode=mode)
    await _call(_adapter(mode), spy)
    opts = spy.spawns[0]["opts"]
    assert opts.get("user") == CLI_UID and opts.get("group") == CLI_UID, opts
    assert opts.get("extra_groups") == []
    assert spy.spawns[0]["env"].get("HOME") == opts["cwd"]


# ── structure: the guard leads every spawn path ──────────────────────────


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Attribute) and n.func.attr == name)
            or (isinstance(n.func, ast.Name) and n.func.id == name)
        )
    ]


def test_floor2_every_cli_spawn_in_the_adapter_is_preceded_by_the_guard():
    """Each function in ``claude_code.py`` that spawns calls the guard as its first statement.

    The behavioural pins above cover ``_run_once``; this one catches a spawn path
    added later (a version probe, a login check) that skips the guard.
    """
    tree = parse(APP_ROOT / "agents" / "claude_code.py")
    spawners = [
        fn
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
        and _calls(fn, "create_subprocess_exec") + _calls(fn, "create_subprocess_shell")
    ]
    assert spawners, "claude_code.py no longer spawns the CLI; this pin is blind"
    bad = []
    for fn in spawners:
        body = [
            s
            for s in fn.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        ]
        first = body[0] if body else None
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Call)
            and _calls(first, "ensure_claude_cli_spawnable")
        ):
            bad.append(fn.name)
    assert not bad, f"Floor 1/2 (SEC-006): spawn without the leading guard in {bad}"


def test_floor2_refusal_error_is_a_plain_agent_error():
    from app.agents.claude_code import ClaudeCliUnavailableError
    from app.agents.transient import TransientAgentError
    from app.core.exceptions import AgentError

    assert issubclass(ClaudeCliUnavailableError, AgentError)
    assert not issubclass(ClaudeCliUnavailableError, TransientAgentError)
