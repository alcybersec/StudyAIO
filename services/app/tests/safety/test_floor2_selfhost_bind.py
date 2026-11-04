"""Floor 2 -- the self-host single-user stack publishes only where BIND_HOST says.

M35-W1-03, audit finding RL-01 (S1). ``scripts/setup-selfhosted.sh`` offers a
single-user (no login) mode and writes ``BIND_HOST=127.0.0.1``. That value
satisfies the startup guard ``app.main.check_single_user_mode``. The compose
stack, though, still published the base file's ``8000:8000`` (api) and
``${UI_PORT:-3001}:3000`` (ui) on every host interface. So the no-login admin was
reachable from the network while the guard checked a declared value, not the
real bind.

These checks render the stack an operator actually runs,
``docker-compose.yml`` + ``docker-compose.selfhosted.yml``, in its single-user
form: no profile active, ``BIND_HOST``/``UI_PORT`` unset unless a test sets them.
The render is pure Python: YAML anchors and ``<<`` resolved, compose's
``!override``/``!reset`` honoured, ``${VAR:-default}`` interpolated. A plain
overlay ``ports:`` list is *appended* to the base, as compose does, so an overlay
that forgets ``!override`` still sees the base's all-interfaces publish.
When docker is available, ``test_floor2_selfhost_render_matches_docker_compose_config``
checks this render against ``docker compose config``. Otherwise it skips.

Pinned:

* the api publishes no host port (the ui's nginx reaches it over the compose
  network);
* every ui port is bound to ``BIND_HOST``, the variable the guard reads, and
  with ``BIND_HOST`` unset that is ``127.0.0.1``;
* no service publishes on an empty host, ``0.0.0.0`` or ``::``.

Out of scope (later tasks): the TLS proxy and its profile, container hardening
and the setup script's multi-user branch.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.safety.test_floor2_claude_login_mounts import REPO_ROOT, _load, _Tagged

BASE = "docker-compose.yml"
OVERLAY = "docker-compose.selfhosted.yml"
#: The single-user stack: overlays applied in order on top of BASE.
SELFHOST_STACK = (OVERLAY,)
ALL_INTERFACES = frozenset({"", "0.0.0.0", "::"})
#: Same notion of loopback as ``app.main.check_single_user_mode``.
LOOPBACK_DEFAULT = "127.0.0.1"
#: A second loopback address, so "follows BIND_HOST" is shown without leaving loopback.
OTHER_LOOPBACK = "127.0.0.9"


@dataclass(frozen=True, order=True)
class Published:
    """One host publish: ``host_ip`` empty means every interface."""

    host_ip: str
    published: str
    target: str


# ── interpolation ────────────────────────────────────────────────────────

_VAR = re.compile(
    r"\$(?:\$|\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)(?:(?P<op>:?[-?])(?P<arg>[^}]*))?\}"
    r"|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


def interpolate(text: str, env: dict[str, str]) -> str:
    """Compose-style ``$VAR``, ``${VAR}``, ``${VAR:-d}``, ``${VAR-d}``, ``${VAR:?e}``, ``$$``."""

    def sub(m: re.Match[str]) -> str:
        if m.group(0) == "$$":
            return "$"
        name = m.group("braced") or m.group("bare")
        op, arg = m.group("op"), m.group("arg") or ""
        value = env.get(name)
        if op == ":-":
            return value if value else arg
        if op == "-":
            return arg if value is None else value
        if op in (":?", "?"):
            if value is None or (op == ":?" and not value):
                raise ValueError(f"required variable {name} unset: {arg}")
            return value
        return value or ""

    return _VAR.sub(sub, text)


# ── port parsing ─────────────────────────────────────────────────────────


def parse_port(entry: object, env: dict[str, str]) -> Published:
    """Short (``[host:]published:target[/proto]``) or long-syntax port, interpolated."""
    if isinstance(entry, dict):
        return Published(
            host_ip=interpolate(str(entry.get("host_ip") or ""), env),
            published=interpolate(str(entry.get("published") or ""), env),
            target=interpolate(str(entry["target"]), env),
        )
    text = interpolate(str(entry), env).split("/", 1)[0]
    if text.startswith("["):
        host, _, rest = text[1:].partition("]")
        published, _, target = rest.lstrip(":").partition(":")
        return Published(host, published, target)
    parts = text.split(":")
    if len(parts) == 1:
        return Published("", "", parts[0])
    if len(parts) == 2:
        return Published("", parts[0], parts[1])
    return Published(":".join(parts[:-2]), parts[-2], parts[-1])


# ── render ───────────────────────────────────────────────────────────────


def _raw_ports(value: object) -> list:
    if isinstance(value, _Tagged):
        return [] if value.tag == "reset" else list(value.value or [])
    return list(value or [])


def merge_ports(base: list, over: object) -> list:
    """Compose port merge: ``!override`` replaces, ``!reset`` clears, a plain list appends."""
    if isinstance(over, _Tagged):
        return [] if over.tag == "reset" else list(over.value or [])
    return list(base) + list(over or [])


def render_ports(
    overlays: tuple[str, ...], env: dict[str, str], profiles: frozenset[str] = frozenset()
) -> dict[str, list[Published]]:
    """Every active service's published ports for BASE + ``overlays``."""
    services: dict[str, dict] = {}
    for name in (BASE, *overlays):
        for svc, spec in (_load(REPO_ROOT / name).get("services") or {}).items():
            spec = spec or {}
            entry = services.setdefault(svc, {"ports": [], "profiles": None})
            if "ports" in spec:
                entry["ports"] = merge_ports(entry["ports"], spec["ports"])
            if "profiles" in spec:
                entry["profiles"] = _raw_ports(spec["profiles"]) or None
    return {
        svc: [parse_port(p, env) for p in entry["ports"]]
        for svc, entry in services.items()
        if not entry["profiles"] or set(entry["profiles"]) & profiles
    }


def single_user_render(env: dict[str, str] | None = None) -> dict[str, list[Published]]:
    """The single-user self-host stack: no profile active."""
    return render_ports(SELFHOST_STACK, env or {})


# ── the parser cannot be blinded ─────────────────────────────────────────


def test_floor2_selfhost_render_helpers_on_synthetic_input():
    """Guard the interpolation, port parsing and merge, so a helper bug cannot pass the pins."""
    assert interpolate("${BIND_HOST:-127.0.0.1}", {}) == "127.0.0.1"
    assert interpolate("${BIND_HOST:-127.0.0.1}", {"BIND_HOST": ""}) == "127.0.0.1"
    assert interpolate("${BIND_HOST-127.0.0.1}", {"BIND_HOST": ""}) == ""
    assert interpolate("${BIND_HOST}:$UI_PORT", {"UI_PORT": "1"}) == ":1"
    assert interpolate("$$X", {}) == "$X"

    assert parse_port("8000:8000", {}) == Published("", "8000", "8000")
    assert parse_port("3000", {}) == Published("", "", "3000")
    assert parse_port("0.0.0.0:80:80/tcp", {}) == Published("0.0.0.0", "80", "80")
    assert parse_port("[::1]:3001:3000", {}) == Published("::1", "3001", "3000")
    assert parse_port("${BIND_HOST:-127.0.0.1}:${UI_PORT:-3001}:3000", {}) == Published(
        "127.0.0.1", "3001", "3000"
    )
    assert parse_port({"target": 3000, "published": 3001}, {}) == Published("", "3001", "3000")

    base = ["8000:8000"]
    assert merge_ports(base, ["127.0.0.1:1:1"]) == ["8000:8000", "127.0.0.1:1:1"]
    assert merge_ports(base, _Tagged("override", [])) == []
    assert merge_ports(base, _Tagged("override", ["127.0.0.1:1:1"])) == ["127.0.0.1:1:1"]
    assert merge_ports(base, _Tagged("reset", None)) == []


def test_floor2_selfhost_stack_has_ui_and_api():
    services = single_user_render()
    missing = sorted({"ui", "api"} - set(services))
    assert not missing, f"single-user self-host render has no {missing}"


# ── the floor ────────────────────────────────────────────────────────────


def test_floor2_selfhost_api_publishes_no_host_port():
    """The api is reached over the compose network only; a host port bypasses BIND_HOST."""
    ports = single_user_render()["api"]
    assert ports == [], (
        f"Floor 2 (RL-01): in {BASE} + {OVERLAY} the api publishes {ports} on the host. "
        f"Set `ports: !override []` on api in {OVERLAY}."
    )


def test_floor2_selfhost_ui_publishes_only_on_loopback_by_default():
    """With BIND_HOST unset, every ui publish is on 127.0.0.1."""
    ports = single_user_render()["ui"]
    assert ports, "the ui must publish one port for the operator"
    bad = [p for p in ports if p.host_ip != LOOPBACK_DEFAULT]
    assert not bad, (
        f"Floor 2 (RL-01): with BIND_HOST unset the ui publishes {bad}, not only on "
        f'{LOOPBACK_DEFAULT}. Use `ports: !override ["${{BIND_HOST:-127.0.0.1}}:..."]`.'
    )


def test_floor2_selfhost_ui_bind_follows_bind_host():
    """The published address is BIND_HOST itself, the value check_single_user_mode reads."""
    ports = single_user_render({"BIND_HOST": OTHER_LOOPBACK})["ui"]
    assert ports, "the ui must publish one port for the operator"
    bad = [p for p in ports if p.host_ip != OTHER_LOOPBACK]
    assert not bad, (
        f"Floor 2 (RL-01): with BIND_HOST={OTHER_LOOPBACK} the ui publishes {bad}. "
        "The address the startup guard checks must be the address compose publishes."
    )


@pytest.mark.parametrize("bind_host", [None, LOOPBACK_DEFAULT], ids=["unset", "loopback"])
def test_floor2_selfhost_nothing_publishes_on_all_interfaces(bind_host):
    env = {} if bind_host is None else {"BIND_HOST": bind_host}
    bad = [
        f"{svc}: {p}"
        for svc, ports in sorted(single_user_render(env).items())
        for p in ports
        if p.host_ip.strip("[]") in ALL_INTERFACES
    ]
    assert not bad, (
        "Floor 2 (RL-01): the single-user self-host stack publishes on every interface:\n"
        + "\n".join(bad)
    )


# ── cross-check against compose itself ───────────────────────────────────


def _docker_compose() -> list[str] | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    probe = subprocess.run(
        [docker, "compose", "version"], capture_output=True, text=True, check=False
    )
    return [docker, "compose"] if probe.returncode == 0 else None


def test_floor2_selfhost_render_matches_docker_compose_config():
    """The pure-YAML render agrees with ``docker compose config`` on every published port.

    Runs in a scratch copy with an empty ``.env`` (the real one is never read), with
    BIND_HOST and UI_PORT unset. Skips when docker compose is not installed.
    """
    compose = _docker_compose()
    if compose is None:
        pytest.skip("docker compose not available; the pure-YAML render is the check")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "DOCKER_HOST")}
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        for name in (BASE, *SELFHOST_STACK):
            shutil.copy(REPO_ROOT / name, work / name)
        (work / ".env").write_text("")
        args = [*compose, "--project-directory", str(work), "-f", str(work / BASE)]
        for name in SELFHOST_STACK:
            args += ["-f", str(work / name)]
        result = subprocess.run(
            [*args, "config", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=work,
        )
    if result.returncode != 0:
        pytest.skip(f"docker compose config failed here: {result.stderr.strip()[:300]}")
    rendered = json.loads(result.stdout)["services"]
    theirs = {
        svc: sorted(
            Published(str(p.get("host_ip") or ""), str(p.get("published") or ""), str(p["target"]))
            for p in spec.get("ports") or []
        )
        for svc, spec in rendered.items()
    }
    ours = {svc: sorted(ports) for svc, ports in single_user_render().items()}
    assert ours == theirs, f"pure-YAML render {ours} != docker compose config {theirs}"
