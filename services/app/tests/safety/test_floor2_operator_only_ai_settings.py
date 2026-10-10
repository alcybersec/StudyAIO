"""Floor 2: no user setting picks the executable, the model or an internal endpoint.

SEC-01 (GL#11, R-029): ``claude_code_path`` is the program the worker runs.
Running a user-chosen path runs arbitrary code inside the worker, which holds
the JWT secret, the database URL and the instance AI keys (floor 2) and every
user's files (floor 1). ``claude_model`` rides with it. Both are operator-only
since backend ``a5f3255``:

* a ``PUT /api/settings`` naming either is a 422 and stores nothing;
* a value stored before the rule never reaches the CLI's argv[0] or
  ``--model`` (nor the Anthropic API model), through the settings service's
  agent config **or** through the factory, the single choke point every AI call
  passes (``agents/factory.py`` docstring), whoever built the dict;
* ``GET /api/settings`` never echoes the stored value.

SEC-03 (GL#14, R-032): ``zai_base_url`` / ``ollama_base_url`` make the worker
fetch a URL on a user's behalf. Not self-hosted, they are operator-only like the
keys above. Self-hosted, ``core/url_safety`` refuses anything that is not a
public http(s) address, at PUT time and again whenever a stored value is turned
into an agent config. These pins try the known bypass spellings.

Still open, owned by ai (M32-S4-AI-024): re-validating at connect time in the
adapters (DNS rebinding between config build and connect) and refusing
redirects. ``url_safety``'s own docstring says the consumer must do both; they
are tracked in ``FLOORS.md`` and in R-032, not pinned here.
"""

from __future__ import annotations

import asyncio
import json
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

EVIL_PATH = "/tmp/floor2-sentinel-user-chosen-binary"
EVIL_MODEL = "floor2-sentinel-user-chosen-model"
OPERATOR_CLI = "/usr/local/bin/floor2-operator-claude"
OPERATOR_MODEL = "floor2-operator-model"


def _row(stored: dict) -> SimpleNamespace:
    return SimpleNamespace(
        settings_json=dict(stored),
        theme="system",
        language="en",
        content_language=False,
        dashboard_layout=None,
        timezone="UTC",
        updated_at=None,
    )


def _claude_login() -> str:
    return json.dumps({"claudeAiOauth": {"accessToken": "floor2-u", "refreshToken": "floor2-r"}})


def _legacy_overrides(backend: str = "claude_code") -> dict:
    """A row written before SEC-01: the user chose the binary and the model."""
    stored = {
        "agent_backend": backend,
        "claude_code_path": EVIL_PATH,
        "claude_model": EVIL_MODEL,
    }
    if backend == "claude_code":
        stored["claude_cli_credentials"] = _claude_login()
    if backend == "anthropic_api":
        stored["anthropic_api_key"] = "floor2-sentinel-anthropic-user-key"
    return stored


@pytest.fixture
def operator_cli(monkeypatch):
    """The operator's ``CLAUDE_CODE_PATH`` / ``CLAUDE_MODEL``."""
    from app.config import settings

    monkeypatch.setattr(settings, "claude_code_path", OPERATOR_CLI)
    monkeypatch.setattr(settings, "claude_model", OPERATOR_MODEL)
    for name in ("CLAUDE_HOST_OAUTH_TOKEN_FILE", "CLAUDE_HOST_CREDENTIALS_FILE", "CLAUDE_CLI_UID"):
        monkeypatch.delenv(name, raising=False)


async def _argv_of(adapter) -> list[str]:
    seen: list[list[str]] = []

    async def fake(*cmd, **_kw):
        seen.append([str(c) for c in cmd])
        process = MagicMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"ok", b""))
        return process

    with patch.object(asyncio, "create_subprocess_exec", fake):
        await adapter._run_claude_code("lecture prompt")
    return seen[0]


def _model_flag(argv: list[str]) -> str | None:
    return argv[argv.index("--model") + 1] if "--model" in argv else None


# ── SEC-01: PUT ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "value"),
    [("claude_code_path", EVIL_PATH), ("claude_model", "opus"), ("claude_model", EVIL_MODEL)],
)
async def test_floor2_put_operator_only_ai_key_is_422_and_stores_nothing(key, value, async_client):
    """Naming the executable or the model in a PUT is refused, alone or with valid keys."""
    row = _row({})
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new=AsyncMock(return_value=row),
    ):
        response = await async_client.put(
            "/api/settings", json={"agent_backend": "claude_code", key: value}
        )
    assert response.status_code == 422, (
        f"Floor 2 (SEC-01): PUT {key} answered {response.status_code}; the worker would run "
        "a user-chosen binary/model"
    )
    assert row.settings_json == {}, f"a rejected PUT still stored {row.settings_json}"


# ── SEC-01: stored legacy values on every read path ─────────────────────


@pytest.mark.asyncio
async def test_floor2_stored_legacy_path_and_model_never_reach_the_cli(operator_cli):
    """settings row → agent config → factory → argv: argv[0] and --model are the operator's."""
    from app.agents.factory import get_agent
    from app.services.settings_service import _agent_config_from_overrides

    config = _agent_config_from_overrides(_legacy_overrides())
    assert config and config["agent_backend"] == "claude_code", "control: own provider expected"
    assert EVIL_PATH not in json.dumps(config) and EVIL_MODEL not in json.dumps(config), (
        f"Floor 2 (SEC-01): the agent config carries a stored executable/model: {config}"
    )
    argv = await _argv_of(get_agent(user_settings=config))
    assert argv[0] == OPERATOR_CLI, f"Floor 2 (SEC-01): the worker runs {argv[0]!r}"
    assert _model_flag(argv) == OPERATOR_MODEL, f"--model is {_model_flag(argv)!r}"


@pytest.mark.asyncio
async def test_floor2_get_user_ai_context_drops_stored_path_and_model(operator_cli):
    """The one-query path every AI call site uses drops them too."""
    from app.services import settings_service

    session = AsyncMock()
    with patch.object(
        settings_service, "_get_row", new=AsyncMock(return_value=_row(_legacy_overrides()))
    ):
        config, _lang = await settings_service.get_user_ai_context(session, "u1")
        config2 = await settings_service.get_user_agent_config(session, "u1")
    for c in (config, config2):
        assert EVIL_PATH not in json.dumps(c) and EVIL_MODEL not in json.dumps(c), c


def test_floor2_stored_legacy_model_never_reaches_the_anthropic_api(operator_cli, monkeypatch):
    """``claude_model`` also names the Anthropic API model; a stored one is ignored there too."""
    from app.agents import anthropic_api
    from app.agents.factory import get_agent
    from app.services.settings_service import _agent_config_from_overrides

    monkeypatch.setattr(anthropic_api, "get_effective_setting", lambda k: OPERATOR_MODEL)
    config = _agent_config_from_overrides(_legacy_overrides("anthropic_api"))
    adapter = get_agent(user_settings=config)
    models = [v for v in vars(adapter).values() if isinstance(v, str)]
    assert EVIL_MODEL not in models, f"Floor 2 (SEC-01): the API adapter uses {EVIL_MODEL}"


@pytest.mark.asyncio
async def test_floor2_factory_never_runs_a_user_supplied_executable_or_model(operator_cli):
    """The factory ignores ``claude_code_path`` / ``claude_model`` in any user_settings dict.

    The factory is the single choke point every AI call passes. Today only
    ``_agent_config_from_overrides`` builds its input and drops the keys, but
    the factory still forwards ``cli_path=user_settings.get("claude_code_path")``
    and the adapter honours it. One new builder (a test-AI form, an import, a
    copied dict) and the worker execs a user's path again. Fix (ai): stop
    forwarding both keys in ``agents/factory.py`` and drop the adapter's
    ``cli_path`` override, as ``ff90277`` already did for ``model``.
    """
    from app.agents.factory import get_agent

    adapter = get_agent(user_settings=_legacy_overrides())
    argv = await _argv_of(adapter)
    assert argv[0] == OPERATOR_CLI, (
        f"Floor 2 (SEC-01): the factory hands a user-supplied executable to the CLI: {argv[0]!r}"
    )
    assert _model_flag(argv) == OPERATOR_MODEL


@pytest.mark.asyncio
async def test_floor2_get_settings_never_echoes_stored_path_or_model(async_client):
    """``GET /api/settings`` shows what the operator runs, never the stored legacy values."""
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new=AsyncMock(return_value=_row(_legacy_overrides())),
    ):
        response = await async_client.get("/api/settings")
    assert response.status_code == 200, response.text
    assert EVIL_PATH not in response.text and EVIL_MODEL not in response.text


# ── SEC-03: user endpoints ───────────────────────────────────────────────

PUBLIC_IP = "93.184.216.34"

#: name -> what the resolver answers. Real glibc resolves a numeric name with a
#: trailing dot to the literal, and ``localhost`` to loopback; the fake does too.
DNS = {
    "public.example": [PUBLIC_IP],
    "public.example.": [PUBLIC_IP],
    "internal.example": ["10.1.2.3"],
    "mixed.example": [PUBLIC_IP, "192.168.0.10"],
    "rebind.example": ["127.0.0.1"],
    "v6only.example": ["fd12::1"],
    "mapped.example": ["::ffff:169.254.169.254"],
    "localhost": ["127.0.0.1", "::1"],
    "localhost.": ["127.0.0.1"],
    "127.0.0.1.": ["127.0.0.1"],
    "metadata.google.internal": ["169.254.169.254"],
}


def _fake_getaddrinfo(host, port, *args, **kwargs):
    if host in DNS:
        answers = DNS[host]
    else:
        # glibc parses inet_aton spellings (2130706433, 0x7f.1, 0177.0.0.1) itself.
        try:
            answers = [socket.inet_ntoa(socket.inet_aton(host))]
        except OSError:
            raise socket.gaierror(f"unknown host {host!r}") from None
    out = []
    for ip in answers:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sockaddr = (ip, port or 0, 0, 0) if family == socket.AF_INET6 else (ip, port or 0)
        out.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
    return out


@pytest.fixture
def dns():
    with patch("app.core.url_safety.socket.getaddrinfo", side_effect=_fake_getaddrinfo) as m:
        yield m


@pytest.fixture
def self_hosted(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "self_hosted", True)


@pytest.fixture
def hosted(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "self_hosted", False)


INTERNAL_TARGETS = [
    # schemes
    "file:///etc/passwd",
    "gopher://public.example/",
    "ftp://public.example/",
    "//public.example/",
    "public.example",
    # loopback, unspecified, private, link-local / metadata, CGNAT, benchmark
    "http://127.0.0.1:11434/",
    "http://0.0.0.0:6379/",
    "http://[::]/",
    "http://[::1]/",
    "http://10.0.0.1/",
    "http://172.16.0.1/",
    "http://192.168.10.20/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[fd00:ec2::254]/",
    "http://100.64.0.1/",
    "http://198.18.0.1/",
    "http://224.0.0.1/",
    "http://255.255.255.255/",
    # IPv6 wrappers of IPv4 and zone ids
    "http://[::ffff:127.0.0.1]/",
    "http://[::ffff:a9fe:a9fe]/",
    "http://[2002:a9fe:a9fe::1]/",
    "http://[64:ff9b::a9fe:a9fe]/",
    "http://[fe80::1%25eth0]/",
    "http://[::1%25lo]/",
    # numeric spellings
    "http://2130706433/",
    "http://0x7f000001/",
    "http://0177.0.0.1/",
    "http://127.1/",
    "http://0/",
    "http://017700000001/",
    "http://１２７.０.０.１/",
    # trailing dots, names
    "http://127.0.0.1./",
    "http://localhost:11434/",
    "http://localhost./",
    "http://metadata.google.internal/",
    "http://internal.example/",
    "http://mixed.example/",
    "http://v6only.example/",
    "http://mapped.example/",
    "http://does-not-resolve.example/",
    # userinfo and parser confusion
    "http://user:pw@public.example/",
    "http://public.example@127.0.0.1/",
    "http://public.example:80@127.0.0.1/",
    "http://127.0.0.1#@public.example/",
    "http://127.0.0.1\\@public.example/",
    "http://public.example:99999/",
]


@pytest.mark.parametrize("key", ["zai_base_url", "ollama_base_url"])
@pytest.mark.parametrize("url", INTERNAL_TARGETS)
def test_floor2_self_hosted_user_endpoint_refuses_internal_targets(url, key, self_hosted, dns):
    """A self-hosted user cannot point the worker at the host's own network."""
    from app.services.settings_service import validate_setting

    with pytest.raises(ValueError):
        accepted = validate_setting(key, url)
        pytest.fail(f"Floor 2 (SEC-03): {key}={url!r} accepted as {accepted!r}")


@pytest.mark.parametrize("key", ["zai_base_url", "ollama_base_url"])
@pytest.mark.parametrize(
    "url", ["https://public.example/v1/", "http://public.example:11434", f"https://{PUBLIC_IP}/"]
)
def test_floor2_self_hosted_user_endpoint_accepts_a_public_url(url, key, self_hosted, dns):
    """Control: the validator is not refusing everything."""
    from app.services.settings_service import validate_setting

    assert validate_setting(key, url) == url


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["zai_base_url", "ollama_base_url"])
async def test_floor2_hosted_user_endpoint_put_is_422_and_stores_nothing(
    key, async_client, hosted, dns
):
    """Not self-hosted, even a public URL is the operator's to set."""
    row = _row({})
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new=AsyncMock(return_value=row),
    ):
        response = await async_client.put("/api/settings", json={key: "https://public.example/"})
    assert response.status_code == 422, response.text
    assert row.settings_json == {}


@pytest.mark.parametrize("backend", ["zai", "ollama"])
@pytest.mark.parametrize("mode", ["hosted", "self_hosted_rebound"])
def test_floor2_stored_user_endpoint_is_revalidated_when_the_config_is_built(
    backend, mode, monkeypatch, dns
):
    """A stored URL is dropped when the deployment is hosted, or when it now resolves inward.

    ``rebind.example`` passed at PUT time and resolves to loopback now; the
    config must not carry it, so the adapter falls back to the operator's
    endpoint (zai) or refuses the selection (ollama, whose endpoint is the
    credential).
    """
    from app.config import settings
    from app.services.settings_service import _agent_config_from_overrides, _public_view

    monkeypatch.setattr(settings, "self_hosted", mode != "hosted")
    key = f"{backend}_base_url"
    url = "http://rebind.example:11434/" if mode != "hosted" else "https://public.example/"
    stored = {"agent_backend": backend, key: url, "zai_api_key": "floor2-zai-user-key"}

    config = _agent_config_from_overrides(stored)
    assert config is not None and config[key] == "", (
        f"Floor 2 (SEC-03, {mode}): the agent config keeps the stored {key}={config[key]!r}"
    )
    assert _public_view(stored).get(key, "") != url


def test_floor2_url_validator_checks_every_resolved_address_not_the_first(self_hosted, dns):
    """``mixed.example`` answers public first, private second; any private answer refuses."""
    from app.core.url_safety import UnsafeURLError, validate_outbound_url

    with pytest.raises(UnsafeURLError):
        validate_outbound_url("http://mixed.example/")
    assert dns.called, "the validator never resolved the name, so this proves nothing"


# ── SEC-03 at use time (ai AI-024, ee6b441) ──────────────────────────────


def _user_config(backend: str, url: str) -> dict:
    key = f"{backend}_base_url"
    return {"agent_backend": backend, key: url, f"{backend}_api_key": "floor2-k", "zai_model": ""}


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["zai", "ollama"])
async def test_floor2_user_endpoint_rebound_after_config_is_refused_before_connecting(backend, dns):
    """A user URL that resolves inward by call time is refused before any client exists.

    The config-time check passed (public then); the name now answers loopback.
    Neither the OpenAI SDK client nor the Ollama client may be constructed.
    """
    from app.agents.factory import get_agent
    from app.core.exceptions import AgentError

    agent = get_agent(user_settings=_user_config(backend, "http://rebind.example:11434/"))
    built = MagicMock(side_effect=AssertionError("client built for a refused URL"))
    with (
        patch("app.agents.openai_adapter.AsyncOpenAI", built),
        patch("app.agents.ollama_adapter.AsyncClient", built),
        pytest.raises(AgentError),
    ):
        await agent.classify_lecture("text", "f.pdf", [])
    assert built.call_count == 0, f"Floor 2 (SEC-03): {backend} connected to a rebound URL"


@pytest.mark.parametrize("backend", ["zai", "ollama"])
def test_floor2_user_endpoint_clients_never_follow_redirects(backend, dns):
    """A validated host cannot bounce the worker to a private one with a 3xx."""
    from app.agents.factory import get_agent

    agent = get_agent(user_settings=_user_config(backend, "https://public.example/"))
    if backend == "zai":
        client = agent._client()
        assert client._client.follow_redirects is False
        return
    seen: list[dict] = []

    def capture(*_a, **kw):
        seen.append(kw)
        raise RuntimeError("stop after construction")

    with patch("app.agents.ollama_adapter.AsyncClient", capture):
        with pytest.raises(Exception):  # noqa: B017 - we only need the constructor kwargs
            asyncio.run(agent._call_api("p"))
    assert seen and seen[0].get("follow_redirects") is False
