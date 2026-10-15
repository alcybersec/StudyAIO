"""Floor 2 — the worker's Claude login comes only from the dedicated service dir.

User ruling (docs/decisions.md 2026-10-10, R-025): the claude_code worker gets
its CLI login from ``STUDYAIO_CLAUDE_LOGIN_DIR`` (default
``/opt/studyaio/claude-login``), read-only, and never from the operator's
personal ``~/.claude``, whose session transcripts, history and plugins must not
be visible to a root process that feeds untrusted lecture text to ``claude -p``.

These are static checks over every tracked compose file, so a new service or
overlay that mounts a Claude directory fails here before it ships:

* only the AI worker pools in ``CLAUDE_LOGIN_SERVICES`` (``worker`` and, since the
  GL#51 queue split, ``worker-ondemand``) mount anything Claude-related; api, beat,
  ``worker-maintenance`` and the rest get nothing, and a new service fails until it
  is listed here with a reason (``test_floor2_worker_pool_credentials`` ties the
  list to the queues each pool consumes);
* every such mount is sourced from the dedicated-dir variable, read-only, onto
  one of three known targets (no directory overlay onto ``/root/.claude``);
* a file that pins ``.credentials.json`` is always paired with the directory
  mount at ``/run/claude-host`` and ``CLAUDE_HOST_CREDENTIALS_FILE`` pointing
  into it, so the GL#8 retry re-reads a path that tracks rename-over refreshes
  instead of the single-file mount's pinned inode;
* no compose file or ``.env.example`` line still names ``CLAUDE_CONFIG_DIR`` or
  ``~/.claude`` as a mount source.

The setup script is exercised for real: it must refuse root, create the dir
0700 with an empty ``settings.json``, and never copy credentials in.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest
import yaml

from tests.safety._source import SERVICE_ROOT

REPO_ROOT = SERVICE_ROOT.parents[1]

LOGIN_VAR = "${STUDYAIO_CLAUDE_LOGIN_DIR:-/opt/studyaio/claude-login}"
HOST_DIR_TARGET = "/run/claude-host"
ALLOWED_TARGETS = {
    HOST_DIR_TARGET: "",
    "/root/.claude/.credentials.json": "/.credentials.json",
    "/root/.claude/settings.json": "/settings.json",
}
BASE = "docker-compose.yml"

#: The only compose services that may see the Claude login (the mounts and the
#: ``CLAUDE_HOST_*`` paths). Exact names, so ``worker-maintenance``, ``api``,
#: ``beat``, ``ui`` and any service added later fail until listed here.
#: ``worker`` consumes ``pipeline`` (classify, summarize, assets and courseops
#: call the agent); ``worker-ondemand`` consumes ``ai_ondemand`` (targeted
#: generation and concept extraction call the agent). M33-S3-SAFETY-059, GL#51.
CLAUDE_LOGIN_SERVICES = frozenset({"worker", "worker-ondemand"})


class _Tagged:
    """A YAML node carrying a compose merge tag (``!override``, ``!reset``)."""

    def __init__(self, tag: str, value: object) -> None:
        self.tag = tag
        self.value = value


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that keeps compose's custom tags instead of failing on them."""


def _construct_tagged(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> _Tagged:
    if isinstance(node, yaml.SequenceNode):
        value: object = loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node, deep=True)
    else:
        value = loader.construct_scalar(node)
    return _Tagged(suffix, value)


_ComposeLoader.add_multi_constructor("!", _construct_tagged)


def _untag(value: object) -> object:
    return value.value if isinstance(value, _Tagged) else value


def _compose_files() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    files = [
        REPO_ROOT / p.decode()
        for p in out.split(b"\0")
        if p and re.search(r"(^|/)docker-compose[^/]*\.ya?ml$", p.decode())
    ]
    if not files:
        pytest.fail(f"Floor 2: no tracked compose file under {REPO_ROOT}; not a checkout?")
    return sorted(files)


def _load(path: pathlib.Path) -> dict:
    return yaml.load(path.read_text(), Loader=_ComposeLoader) or {}  # noqa: S506 - SafeLoader subclass


_SHORT = re.compile(r"^(?P<src>(?:\$\{[^}]*\}|[^:$])*):(?P<dst>[^:]+)(?::(?P<mode>[\w,]+))?$")


def _volumes(service: dict) -> list[tuple[str, str, str]]:
    """``(source, target, mode)`` for every bind/volume entry of a service."""
    result = []
    for entry in _untag(service.get("volumes")) or []:
        if isinstance(entry, dict):
            mode = "ro" if entry.get("read_only") else "rw"
            result.append((str(entry.get("source", "")), str(entry.get("target", "")), mode))
            continue
        m = _SHORT.match(str(entry))
        if not m:
            result.append(("", str(entry), "rw"))
            continue
        result.append((m["src"], m["dst"], m["mode"] or "rw"))
    return result


def _is_claude(source: str, target: str) -> bool:
    return "claude" in source.lower() or "claude" in target.lower()


def _environment(service: dict) -> tuple[dict[str, str], bool]:
    """The service's environment as a dict, and whether it is ``!override``-tagged."""
    raw = service.get("environment")
    overridden = isinstance(raw, _Tagged)
    raw = _untag(raw) or {}
    if isinstance(raw, list):
        raw = dict(item.split("=", 1) if "=" in item else (item, "") for item in raw)
    return {str(k): str(v) for k, v in raw.items()}, overridden


def _cases() -> list[tuple[str, str, tuple[str, str, str]]]:
    cases = []
    for path in _compose_files():
        for name, service in (_load(path).get("services") or {}).items():
            for vol in _volumes(service or {}):
                if _is_claude(vol[0], vol[1]):
                    cases.append((path.relative_to(REPO_ROOT).as_posix(), name, vol))
    return cases


def test_floor2_compose_volume_parser_reads_the_dedicated_dir_mounts():
    """Guard the guard: the parser sees each AI pool's three Claude mounts in base."""
    base = [c for c in _cases() if c[0] == BASE]
    for svc in sorted(CLAUDE_LOGIN_SERVICES):
        targets = sorted(vol[1] for _f, s, vol in base if s == svc)
        assert targets == sorted(ALLOWED_TARGETS), (
            f"expected {svc}'s three dedicated-dir mounts in {BASE}, parsed {base}"
        )


def test_floor2_only_the_ai_worker_pools_mount_a_claude_login():
    """api, beat, worker-maintenance, ui, db, redis and any new service see no login."""
    leaks = [
        f"{f}: {svc} mounts {vol}" for f, svc, vol in _cases() if svc not in CLAUDE_LOGIN_SERVICES
    ]
    assert not leaks, (
        f"Floor 2 (R-025): a service outside {sorted(CLAUDE_LOGIN_SERVICES)} mounts a "
        "Claude login:\n" + "\n".join(leaks)
    )


def test_floor2_claude_mounts_come_only_from_the_dedicated_dir_read_only():
    """Never ``~/.claude`` or ``CLAUDE_CONFIG_DIR``; never writable; never a dir overlay."""
    bad = []
    for f, svc, (src, dst, mode) in _cases():
        suffix = ALLOWED_TARGETS.get(dst)
        if suffix is None:
            bad.append(f"{f}: {svc} mounts onto unexpected target {dst!r}")
        elif src != LOGIN_VAR + suffix:
            bad.append(f"{f}: {svc} mounts {dst} from {src!r}, not {LOGIN_VAR + suffix!r}")
        if "ro" not in mode.split(","):
            bad.append(f"{f}: {svc} mounts {dst} writable ({mode!r})")
    assert not bad, "Floor 2 (R-025): Claude login mount outside the ruling:\n" + "\n".join(bad)


def test_floor2_pinned_credentials_file_is_paired_with_the_tracking_dir_mount():
    """GL#8: a single-file ``.credentials.json`` mount pins an inode.

    The host replaces the file by rename on refresh or re-login, so the
    container's copy goes stale for good. The adapter's one retry reads
    ``CLAUDE_HOST_CREDENTIALS_FILE``, which must point into the directory
    mount at ``/run/claude-host`` (a directory bind tracks renames), and the
    variable must survive every overlay's merge.
    """
    per_service: dict[tuple[str, str], set[str]] = {}
    for f, svc, (_src, dst, _mode) in _cases():
        per_service.setdefault((f, svc), set()).add(dst)
    for (f, svc), targets in per_service.items():
        if "/root/.claude/.credentials.json" in targets:
            assert HOST_DIR_TARGET in targets, (
                f"{f}: {svc} pins .credentials.json without the {HOST_DIR_TARGET} dir mount; "
                "the GL#8 retry would re-read the same stale inode"
            )

    want = f"{HOST_DIR_TARGET}/.credentials.json"
    base_services = _load(REPO_ROOT / BASE)["services"]
    for svc in sorted(CLAUDE_LOGIN_SERVICES):
        base_env, _ = _environment(base_services[svc])
        assert base_env.get("CLAUDE_HOST_CREDENTIALS_FILE") == want, (
            f"{BASE}: {svc} CLAUDE_HOST_CREDENTIALS_FILE must be {want!r}, "
            f"got {base_env.get('CLAUDE_HOST_CREDENTIALS_FILE')!r}"
        )
    for path in _compose_files():
        services = _load(path).get("services") or {}
        rel = path.relative_to(REPO_ROOT).as_posix()
        for svc in sorted(CLAUDE_LOGIN_SERVICES):
            worker = services.get(svc) or {}
            if "environment" not in worker:
                continue
            env, overridden = _environment(worker)
            if overridden or "CLAUDE_HOST_CREDENTIALS_FILE" in env:
                assert env.get("CLAUDE_HOST_CREDENTIALS_FILE") == want, (
                    f"{rel}: {svc} environment drops or repoints CLAUDE_HOST_CREDENTIALS_FILE"
                )


def _live_lines(path: pathlib.Path) -> list[tuple[int, str]]:
    return [
        (n, line)
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if line.strip() and not line.lstrip().startswith("#")
    ]


_PERSONAL = re.compile(r"CLAUDE_CONFIG_DIR|~/\.claude|\$\{?HOME\}?/\.claude")


def test_floor2_no_compose_or_env_example_line_points_at_the_personal_claude_dir():
    """Comments may explain the ruling; no live line may revive the old source."""
    hits = []
    for path in [*_compose_files(), REPO_ROOT / ".env.example"]:
        for n, line in _live_lines(path):
            if _PERSONAL.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{n}  {line.strip()}")
    assert not hits, "Floor 2 (R-025): personal Claude dir referenced:\n" + "\n".join(hits)


SETUP = REPO_ROOT / "scripts" / "setup-claude-login.sh"
SCRIPT_SENTINEL = "floor2-sentinel-personal-claude-token-51e0"


def _as_non_root() -> list[str]:
    """Command prefix that drops root; CI's test-floor job runs as root."""
    if os.geteuid() != 0:
        return []
    return ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups"]


def test_floor2_setup_script_creates_a_private_empty_dir_and_copies_no_login():
    """Run the real script with a personal login planted where it might look."""
    base = pathlib.Path(tempfile.mkdtemp(prefix="floor2-setup-"))
    base.chmod(0o777)  # reachable by the unprivileged uid when the suite runs as root
    home = base / "home"
    (home / ".claude").mkdir(parents=True)
    personal = home / ".claude" / ".credentials.json"
    personal.write_text(f'{{"claudeAiOauth": {{"accessToken": "{SCRIPT_SENTINEL}"}}}}')
    target = base / "claude-login"
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    env["CLAUDE_CONFIG_DIR"] = str(home / ".claude")

    try:
        run = subprocess.run(
            [*_as_non_root(), "bash", str(SETUP), str(target)],
            env=env,
            stdin=subprocess.DEVNULL,  # no token offered; a tty would block on the prompt
            capture_output=True,
            text=True,
            check=False,
        )
        listing = sorted(p.name for p in target.iterdir()) if target.is_dir() else None
        mode = target.stat().st_mode & 0o777 if target.exists() else None
        settings = target / "settings.json"
        settings_text = settings.read_text() if settings.exists() else None
        settings_mode = settings.stat().st_mode & 0o077 if settings.exists() else None
        placeholder = target / ".credentials.json"
        placeholder_text = placeholder.read_text().strip() if placeholder.exists() else "{}"
        placeholder_mode = placeholder.stat().st_mode & 0o077 if placeholder.exists() else 0
    finally:
        shutil.rmtree(base, ignore_errors=True)

    assert run.returncode == 0, run.stderr
    assert mode == 0o700, f"login dir mode {oct(mode) if mode else mode}, want 0o700"
    assert (settings_text or "").strip() == "{}"
    assert settings_mode == 0, "settings.json is group/other readable"
    # SAFETY-053: an empty, private ``.credentials.json`` placeholder is allowed (and
    # recommended): without it ``compose up`` makes Docker create a root-owned dir there.
    assert set(listing or []) <= {"settings.json", ".credentials.json"}, (
        f"the setup script left {listing} in the login dir; it must copy no credentials"
    )
    assert placeholder_text == "{}" and placeholder_mode == 0, (
        ".credentials.json is more than a private '{}' placeholder"
    )
    assert SCRIPT_SENTINEL not in run.stdout + run.stderr, "the script printed a credential"


@pytest.mark.skipif(os.geteuid() != 0, reason="behavioural root check needs root (CI)")
def test_floor2_setup_script_refuses_to_run_as_root(tmp_path):
    """As root the script exits non-zero and creates nothing."""
    target = tmp_path / "claude-login"
    run = subprocess.run(
        ["bash", str(SETUP), str(target)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert not target.exists(), "the script created the login dir as root"


def test_floor2_setup_script_has_its_root_guard_before_mkdir():
    """Static: the root guard is present and exits non-zero before touching the dir."""
    text = SETUP.read_text()
    guard = text.find('"$(id -u)" -eq 0')
    assert guard != -1, "setup-claude-login.sh lost its refuse-root guard"
    assert "exit 1" in text[guard : guard + 200]
    assert guard < text.find("mkdir"), "the root guard runs after the dir is created"
