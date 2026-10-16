"""Floors 1 and 2: the app-image services run non-root and the AI pools give the CLI no reach.

M34-S2-SEC-006, option F (``docs/gates/M34/sec006-safety.md`` §5). Static parses of
every deployable stack -- ``docker-compose.yml`` alone and merged with each overlay
(``prod``, ``production``, ``selfhosted``, and ``selfhosted`` + ``production`` as
``production.yml`` documents) -- with YAML anchors and ``<<`` resolved and compose's
``!reset``/``!override`` honoured:

1. **Non-root.** Every service that runs the app image (the three worker pools,
   ``api``, ``beat``) has an effective ``user`` that is not uid or gid 0. An absent
   ``user`` falls back to the Dockerfile's final ``USER``, which must be
   ``studyaio``. Untrusted PDF/DOCX/PPTX is parsed in these processes.
2. **No drop configured on a pool that cannot drop.** ``CLAUDE_CLI_UID`` and
   ``CLAUDE_CLI_GID`` are absent from every app-image service: on a non-root
   worker the adapter refuses them (``test_floor2_cli_shared_uid_refusal``), and a
   value would read as isolation that does not exist. The operator's
   ``CLAUDE_CLI_SHARED_UID_ACCEPTED`` is never defaulted on by a compose file or
   ``.env.example``: accepting the shared uid is the operator's explicit act.
3. **HOME.** On every AI pool (``CLAUDE_LOGIN_SERVICES``) ``HOME`` is set, is not
   ``/``, ``/root``, ``/app``, nor under ``/app/data``, ``/run/claude-host``,
   ``/root/.claude`` or any other mount, and is a ``tmpfs`` owned by the pool's
   uid with mode ``0700``.
4. **The login dir is never widened.** ``scripts/preflight-check.sh`` and
   ``scripts/setup-claude-login.sh`` never suggest a ``chmod`` beyond ``0700``
   (dirs) / ``0600`` (files).

The merge here was cross-checked against ``docker compose config`` for all five
stacks when it was written (M34-S2): same ``user``, ``tmpfs`` and ``HOME``.
"""

from __future__ import annotations

import copy
import re

import pytest

from tests.safety._source import SERVICE_ROOT
from tests.safety.test_floor2_claude_login_mounts import (
    CLAUDE_LOGIN_SERVICES,
    REPO_ROOT,
    _live_lines,
    _load,
    _Tagged,
)

BASE = "docker-compose.yml"
#: Every deployable stack: overlays applied in order on top of BASE.
STACKS: dict[str, tuple[str, ...]] = {
    "base": (),
    "prod": ("docker-compose.prod.yml",),
    "production": ("docker-compose.production.yml",),
    "selfhosted": ("docker-compose.selfhosted.yml",),
    "selfhosted+production": ("docker-compose.selfhosted.yml", "docker-compose.production.yml"),
}
WORKER_POOLS = frozenset({"worker", "worker-ondemand", "worker-maintenance"})
APP_IMAGE_SERVICES = WORKER_POOLS | {"api", "beat"}
DOCKERFILE = SERVICE_ROOT / "Dockerfile"
#: uids of the image's named users. ``studyaio`` is ``useradd -r`` on
#: python:3.12-slim, the first system account, so SYS_UID_MAX = 999
#: (``test_floor2_image_user_uid_is_the_one_the_pins_assume`` holds that).
IMAGE_UIDS = {"studyaio": 999, "root": 0}
ROOTISH = {"0", "root"}
FORBIDDEN_HOMES = ("/", "/root", "/app")
FORBIDDEN_HOME_PARENTS = ("/app/data", "/run/claude-host", "/root/.claude", "/root")
OPT_IN = "CLAUDE_CLI_SHARED_UID_ACCEPTED"


# ── compose merge ────────────────────────────────────────────────────────


def _env_dict(raw: object) -> dict[str, object]:
    if isinstance(raw, list):
        return dict(item.split("=", 1) if "=" in item else (item, None) for item in raw)
    return dict(raw or {})


def _tmpfs_list(raw: object) -> list[str]:
    return [raw] if isinstance(raw, str) else list(raw or [])


def _merge_service(base: dict, over: dict) -> dict:
    """One service, compose-style: overlay keys win; tags reset or replace."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, _Tagged):
            if value.tag == "reset":
                out.pop(key, None)
                continue
            out[key] = copy.deepcopy(value.value)  # !override
            if key == "environment":
                out[key] = _env_dict(out[key])
            continue
        if key == "environment":
            out[key] = {**_env_dict(out.get(key)), **_env_dict(value)}
        elif key == "tmpfs":
            # compose unions tmpfs entries; an overlay entry at the same path wins.
            merged = {e.split(":", 1)[0]: e for e in _tmpfs_list(out.get(key))}
            merged.update({e.split(":", 1)[0]: e for e in _tmpfs_list(value)})
            out[key] = list(merged.values())
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = copy.deepcopy(value)
    return out


def _untag_service(service: dict) -> dict:
    """A base-file service: tags have nothing to reset, so take their values."""
    out = {}
    for key, value in (service or {}).items():
        if isinstance(value, _Tagged):
            if value.tag == "reset":
                continue
            value = value.value
        out[key] = _env_dict(value) if key == "environment" else value
    return out


def stack_services(overlays: tuple[str, ...]) -> dict[str, dict]:
    services = {n: _untag_service(s) for n, s in _load(REPO_ROOT / BASE)["services"].items()}
    for name in overlays:
        for svc, over in (_load(REPO_ROOT / name).get("services") or {}).items():
            services[svc] = _merge_service(services.get(svc, {}), over or {})
    return services


@pytest.fixture(scope="module", params=sorted(STACKS))
def stack(request) -> tuple[str, dict[str, dict]]:
    return request.param, stack_services(STACKS[request.param])


def test_floor2_compose_merge_honours_reset_override_and_tmpfs_union():
    """Guard the merge on synthetic input, so a parser change cannot blind the pins."""
    base = {
        "user": "studyaio:studyaio",
        "environment": {"A": "1", "HOME": "/tmp/h"},
        "tmpfs": ["/tmp/h:uid=999,mode=0700"],
    }
    assert "user" not in _merge_service(base, {"user": _Tagged("reset", None)})
    assert _merge_service(base, {"user": "0:0"})["user"] == "0:0"
    env = _merge_service(base, {"environment": {"B": "2"}})["environment"]
    assert env == {"A": "1", "HOME": "/tmp/h", "B": "2"}
    env = _merge_service(base, {"environment": _Tagged("override", {"B": "2"})})["environment"]
    assert env == {"B": "2"}
    tmpfs = _merge_service(base, {"tmpfs": ["/tmp/p:mode=1777"]})["tmpfs"]
    assert tmpfs == ["/tmp/h:uid=999,mode=0700", "/tmp/p:mode=1777"]
    assert _merge_service(base, {"tmpfs": _Tagged("reset", None)}).get("tmpfs") is None


def test_floor2_every_stack_has_the_app_image_services():
    for name, overlays in STACKS.items():
        services = stack_services(overlays)
        missing = sorted(APP_IMAGE_SERVICES - set(services))
        assert not missing, f"{name}: no {missing}; update APP_IMAGE_SERVICES"


# ── 1. non-root ──────────────────────────────────────────────────────────


def _dockerfile_final_user() -> str | None:
    users = [
        line.split(None, 1)[1].strip()
        for line in DOCKERFILE.read_text().splitlines()
        if line.strip().upper().startswith("USER ")
    ]
    return users[-1] if users else None


def _uid_gid(user: str) -> tuple[str, str | None]:
    uid, _, gid = str(user).partition(":")
    return uid.strip(), (gid.strip() or None)


def effective_user(service: dict) -> str:
    return (
        str(service["user"]) if service.get("user") not in (None, "") else _dockerfile_final_user()
    )


def test_floor2_app_image_services_never_run_as_root(stack):
    """``user`` set and non-root, or absent with the image's ``USER studyaio``."""
    name, services = stack
    bad = []
    for svc in sorted(APP_IMAGE_SERVICES):
        user = effective_user(services[svc])
        uid, gid = _uid_gid(user or "")
        if not uid or uid in ROOTISH or gid in ROOTISH:
            bad.append(f"{svc}: user {user!r}")
    assert not bad, (
        f"Floor 1/2 (SEC-006, M32 N-3), stack {name}: an app-image service runs as root, "
        "so a parser RCE on an uploaded document owns the image and the host mounts:\n"
        + "\n".join(bad)
    )


def test_floor2_dockerfile_final_user_is_studyaio():
    """The fallback for a service with no ``user``: the runtime stage ends as studyaio."""
    assert _dockerfile_final_user() == "studyaio", (
        f"services/app/Dockerfile ends as {_dockerfile_final_user()!r}, not studyaio"
    )


def test_floor2_image_user_uid_is_the_one_the_pins_assume():
    """``studyaio`` is 999: pinned with ``-u 999``, or the image's first ``useradd -r``."""
    text = DOCKERFILE.read_text()
    runtime = text[text.rindex("\nFROM ") :]
    adds = re.findall(r"useradd\s+([^\n&;]*)", runtime)
    mine = [a for a in adds if re.search(r"(^|\s)studyaio\s*$", a.strip())]
    assert len(mine) == 1, f"expected one useradd for studyaio, found {adds}"
    explicit = re.search(r"(?:-u|--uid)\s+(\d+)", mine[0])
    if explicit:
        assert int(explicit[1]) == IMAGE_UIDS["studyaio"], mine[0]
        return
    assert re.search(r"(^|\s)(-r|--system)(\s|$)", mine[0]), mine[0]
    earlier_system = [a for a in adds[: adds.index(mine[0])] if re.search(r"(-r|--system)", a)]
    assert not earlier_system, f"a system user is allocated before studyaio: {earlier_system}"


def test_floor2_nonroot_pin_catches_a_root_pool():
    """Mutation, in memory: ``user: "0:0"`` on the shared anchor fails the pin."""
    services = stack_services(())
    for svc in WORKER_POOLS:
        services[svc]["user"] = "0:0"
    with pytest.raises(AssertionError):
        test_floor2_app_image_services_never_run_as_root(("mutant", services))
    services = stack_services(())
    services["worker"]["user"] = "studyaio:root"
    with pytest.raises(AssertionError):
        test_floor2_app_image_services_never_run_as_root(("mutant", services))


# ── 2. no drop on a pool that cannot drop; opt-in never defaulted ────────


def test_floor2_no_app_image_service_configures_a_cli_uid_drop(stack):
    name, services = stack
    bad = [
        f"{svc}: {var}={services[svc]['environment'][var]!r}"
        for svc in sorted(APP_IMAGE_SERVICES)
        for var in ("CLAUDE_CLI_UID", "CLAUDE_CLI_GID")
        if var in (services[svc].get("environment") or {})
    ]
    assert not bad, (
        f"SEC-006 option F, stack {name}: a non-root service is told to drop the CLI "
        "child, which it cannot do (the adapter refuses it):\n" + "\n".join(bad)
    )


_OFF = re.compile(r"^(|false|0|no|off|\$\{" + OPT_IN + r"(:?-(|false|0|no|off))?\})$", re.I)


def test_floor2_shared_uid_opt_in_is_never_defaulted_on():
    """Compose may pass the operator's choice through; it may not make it."""
    bad = []
    for name, overlays in STACKS.items():
        for svc, service in stack_services(overlays).items():
            env = service.get("environment") or {}
            if OPT_IN in env and not _OFF.match(str(env[OPT_IN] or "").strip()):
                bad.append(f"{name}: {svc} {OPT_IN}={env[OPT_IN]!r}")
    example = REPO_ROOT / ".env.example"
    for n, line in _live_lines(example):
        key, _, value = line.partition("=")
        if key.strip() == OPT_IN and not _OFF.match(value.split("#", 1)[0].strip()):
            bad.append(f".env.example:{n} {line.strip()}")
    assert not bad, (
        "Floor 1/2 (SEC-006): the shared-uid opt-in is switched on by default, so every "
        "deployment silently accepts the CLI at the worker's uid:\n" + "\n".join(bad)
    )


def test_floor2_cli_uid_is_not_set_in_env_example():
    """``.env`` reaches every pool through ``env_file``; a live line would be refused."""
    hits = [
        f".env.example:{n} {line.strip()}"
        for n, line in _live_lines(REPO_ROOT / ".env.example")
        if re.match(r"\s*CLAUDE_CLI_(UID|GID)\s*=", line)
    ]
    assert not hits, hits


# ── 3. HOME ──────────────────────────────────────────────────────────────


def _tmpfs_entry(service: dict, path: str) -> dict[str, str] | None:
    for entry in _tmpfs_list(service.get("tmpfs")):
        target, _, opts = entry.partition(":")
        if target.rstrip("/") == path.rstrip("/"):
            return dict(o.split("=", 1) if "=" in o else (o, "") for o in opts.split(",") if o)
    return None


def _mount_targets(service: dict) -> list[str]:
    from tests.safety.test_floor2_claude_login_mounts import _volumes

    return [dst for _src, dst, _mode in _volumes(service)]


def _under(path: str, parent: str) -> bool:
    path, parent = path.rstrip("/") or "/", parent.rstrip("/") or "/"
    return path == parent or path.startswith(parent + "/")


def _pool_uid(service: dict) -> int | None:
    uid, _ = _uid_gid(effective_user(service) or "")
    return int(uid) if uid.isdigit() else IMAGE_UIDS.get(uid)


def home_problems(service: dict) -> list[str]:
    env = service.get("environment") or {}
    home = str(env.get("HOME") or "")
    if not home.startswith("/"):
        return [f"HOME is {home!r}, not an absolute path the pool owns"]
    out = []
    if home.rstrip("/") in {h.rstrip("/") or "/" for h in FORBIDDEN_HOMES} or home == "/":
        out.append(f"HOME is {home}")
    out += [f"HOME {home} is under {p}" for p in FORBIDDEN_HOME_PARENTS if _under(home, p)]
    out += [
        f"HOME {home} is under the mount {t}" for t in _mount_targets(service) if _under(home, t)
    ]
    entry = _tmpfs_entry(service, home)
    if entry is None:
        return [*out, f"no tmpfs at HOME {home}"]
    uid = _pool_uid(service)
    if uid is None or entry.get("uid") != str(uid):
        out.append(f"tmpfs {home} uid={entry.get('uid')!r}, pool uid {uid}")
    if entry.get("mode", "").lstrip("0") != "700":
        out.append(f"tmpfs {home} mode={entry.get('mode')!r}, want 0700")
    return out


def test_floor2_ai_pool_home_is_a_private_tmpfs(stack):
    name, services = stack
    bad = [
        f"{svc}: {p}" for svc in sorted(CLAUDE_LOGIN_SERVICES) for p in home_problems(services[svc])
    ]
    assert not bad, (
        f"Floor 1/2 (SEC-006), stack {name}: the CLI child's HOME is not a private tmpfs "
        "the pool owns:\n" + "\n".join(bad)
    )


@pytest.mark.parametrize(
    ("home", "tmpfs", "why"),
    [
        ("/root", ["/root:uid=999,mode=0700"], "root"),
        ("/app", ["/app:uid=999,mode=0700"], "app"),
        ("/", ["/:uid=999,mode=0700"], "slash"),
        ("/app/data/h", ["/app/data/h:uid=999,mode=0700"], "data"),
        ("/run/claude-host/h", ["/run/claude-host/h:uid=999,mode=0700"], "login"),
        ("/tmp/claude-home", [], "no-tmpfs"),
        ("/tmp/claude-home", ["/tmp/claude-home:uid=0,mode=0700"], "uid"),
        ("/tmp/claude-home", ["/tmp/claude-home:uid=999,mode=0755"], "mode"),
        ("", [], "unset"),
    ],
)
def test_floor2_home_detector_rejects(home, tmpfs, why):
    service = copy.deepcopy(stack_services(())["worker"])
    service["environment"]["HOME"] = home
    service["tmpfs"] = tmpfs
    assert home_problems(service), f"{why}: HOME {home!r} with {tmpfs} was accepted"


# ── 4. preflight and setup never widen the login dir ─────────────────────

LOGIN_SCRIPTS = (
    REPO_ROOT / "scripts" / "preflight-check.sh",
    REPO_ROOT / "scripts" / "setup-claude-login.sh",
)
_CHMOD = re.compile(r"\bchmod\s+(?:-[A-Za-z]+\s+)*([^\s\"'`;).]+)")


def chmod_widens(mode: str) -> bool:
    """True when ``mode`` grants anything beyond the owner (or is unreadable)."""
    if re.fullmatch(r"0?[0-7]{3,4}", mode):
        return int(mode, 8) & 0o077 != 0 or int(mode, 8) & 0o7000 != 0
    clauses = mode.split(",")
    for clause in clauses:
        m = re.fullmatch(r"([ugoa]*)([-+=])([rwxXst]*)", clause)
        if not m:
            return True
        who, op, _perms = m.groups()
        if op != "-" and (who == "" or set(who) - {"u"}):
            return True
    return False


def test_floor2_login_scripts_never_suggest_a_widening_chmod():
    seen, bad = 0, []
    for path in LOGIN_SCRIPTS:
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for mode in _CHMOD.findall(line):
                seen += 1
                if chmod_widens(mode):
                    bad.append(f"{path.relative_to(REPO_ROOT)}:{n} chmod {mode}  ({line.strip()})")
    assert seen >= 3, "the chmod scan found almost nothing; the pin is blind"
    assert not bad, (
        "Floor 2 (SEC-006 §5.4): a login-dir script suggests a mode beyond 0700/0600:\n"
        + "\n".join(bad)
    )


@pytest.mark.parametrize(
    ("mode", "widens"),
    [
        ("700", False),
        ("0700", False),
        ("600", False),
        ("0600", False),
        ("go-rwx", False),
        ("u+rwx,go-rwx", False),
        ("750", True),
        ("0755", True),
        ("644", True),
        ("777", True),
        ("4700", True),
        ("a+r", True),
        ("g+rx", True),
        ("o=r", True),
        ("+r", True),
        ("$MODE", True),
    ],
)
def test_floor2_chmod_detector(mode, widens):
    assert chmod_widens(mode) is widens
