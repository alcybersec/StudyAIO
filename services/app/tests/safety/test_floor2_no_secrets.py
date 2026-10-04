"""Floor 2 — no secrets in the tree.

    no plaintext credentials, tokens or keys committed, and per-user AI
    credentials are never logged or returned by the API

Two halves:

* **Returned or logged** — every surface that can carry a stored per-user AI
  credential back out: ``GET``/``PUT /api/settings``, the account export, and
  structured logs on the write path and the adapter factory. Each test plants
  a unique sentinel per credential key and asserts it never appears.
  ``tests/unit/api/test_settings_secrets.py`` (#30) covers the instance key;
  these cover the user's own.
* **Committed** — a high-confidence scan of tracked files (formats with a
  fixed, unmistakable prefix, so near-zero false positives), no tracked
  ``.env``, and the detect-secrets baseline wired into pre-commit with nothing
  in it marked as a real secret. A generic entropy scan is deliberately not
  attempted here: detect-secrets already does that against an audited
  baseline, and a second, unaudited one would be noise.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
import yaml

from tests.safety._source import SERVICE_ROOT

REPO_ROOT = SERVICE_ROOT.parents[1]


def _sentinel(key: str) -> str:
    # Unlike any real credential format, so the repository scan below and
    # detect-secrets both stay quiet about this file.
    return f"floor2-sentinel-{key}-7f3a9c"


def _claude_creds(token: str) -> str:
    return json.dumps({"claudeAiOauth": {"accessToken": token, "refreshToken": token + "-r"}})


def _stored_credentials() -> dict[str, str]:
    from app.services.settings_service import SECRET_KEYS

    stored = {}
    for key in SECRET_KEYS:
        if key == "claude_cli_credentials":
            stored[key] = _claude_creds(_sentinel(key))
        else:
            stored[key] = _sentinel(key)
    return stored


def _all_sentinels() -> list[str]:
    from app.services.settings_service import SECRET_KEYS

    return [_sentinel(k) for k in SECRET_KEYS]


def _assert_no_sentinel(text: str, where: str) -> None:
    leaked = [s for s in _all_sentinels() if s in text]
    assert not leaked, f"Floor 2: stored per-user credential(s) {leaked} appear in {where}"


def _settings_row(overrides: dict) -> SimpleNamespace:
    return SimpleNamespace(
        settings_json=dict(overrides),
        theme="system",
        language="en",
        content_language=False,
        dashboard_layout=None,
        updated_at=None,
    )


# ── returned by the API ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor2_settings_get_never_returns_a_stored_credential(async_client):
    """GET /api/settings reports `<key>_configured`, never the value."""
    row = _settings_row({"agent_backend": "openai", **_stored_credentials()})
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new=AsyncMock(return_value=row),
    ):
        response = await async_client.get("/api/settings")

    assert response.status_code == 200
    _assert_no_sentinel(response.text, "GET /api/settings")
    body = response.json()
    from app.services.settings_service import SECRET_KEYS

    for key in SECRET_KEYS:
        assert body[f"{key}_configured"] is True


@pytest.mark.asyncio
async def test_floor2_settings_put_never_echoes_a_credential(async_client):
    """PUT /api/settings stores the credential and answers without it."""
    row = _settings_row({})
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new=AsyncMock(return_value=row),
    ):
        response = await async_client.put(
            "/api/settings", json={"agent_backend": "openai", **_stored_credentials()}
        )

    assert response.status_code == 200, response.text
    _assert_no_sentinel(response.text, "PUT /api/settings response")
    # And it really was stored — otherwise the absence above proves nothing.
    assert row.settings_json["openai_api_key"] == _sentinel("openai_api_key")


def test_floor2_settings_schemas_carry_no_credential_value():
    """The response model has no credential field; every credential input is a SECRET_KEY.

    A new credential added to ``SettingsUpdateRequest`` but not to
    ``SECRET_KEYS`` would be stored and then echoed by ``_public_view``.
    """
    from app.api.schemas import SettingsResponse, SettingsUpdateRequest
    from app.services.settings_service import SECRET_KEYS

    # `_token` as a suffix only: `chunk_size_tokens` is a count, not a credential.
    secretish = re.compile(r"(api_key|secret|_token$|credential|password)")
    response_fields = set(SettingsResponse.model_fields)
    assert not response_fields & SECRET_KEYS
    for name, field in SettingsResponse.model_fields.items():
        if secretish.search(name):
            assert name.endswith("_configured") and field.annotation is bool, name

    request_secretish = {n for n in SettingsUpdateRequest.model_fields if secretish.search(n)} - {
        "clear_secrets"
    }
    assert request_secretish <= SECRET_KEYS, (
        f"credential-shaped inputs missing from SECRET_KEYS: {request_secretish - SECRET_KEYS}"
    )


@pytest.mark.asyncio
async def test_floor2_account_export_never_returns_a_stored_credential(
    async_client, default_test_user
):
    """GET /api/auth/account/export must not hand back stored AI credentials.

    The export filters credential *columns* (``EXPORT_EXCLUDED_COLUMNS``), but
    the per-user AI credentials live as keys inside ``user_settings.settings_json``,
    which is exported whole.
    """
    from app.api.deps import get_current_user
    from app.main import app
    from app.services import account_service

    settings_row = {
        "id": "settings-1",
        "user_id": default_test_user.id,
        "settings_json": {"agent_backend": "openai", **_stored_credentials()},
        "theme": "system",
    }

    class _Row:
        def __init__(self, mapping):
            self._mapping = mapping

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    async def execute(statement, *_a, **_k):
        from tests.safety._tenant import tables_in

        if "user_settings" in tables_in(statement):
            return _Result([_Row(settings_row)])
        return _Result([])

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute)

    from app.core.database import get_session

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: default_test_user
    with patch.object(
        account_service,
        "collect_owned_ids",
        new=AsyncMock(return_value=account_service.OwnedIds.empty()),
    ):
        response = await async_client.get("/api/auth/account/export")

    assert response.status_code == 200, response.text
    assert "user_settings" in response.json()["tables"], "export did not reach user_settings"
    _assert_no_sentinel(response.text, "GET /api/auth/account/export")


# ── logged ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor2_credentials_never_logged(async_client, caplog):
    """Saving, rejecting and using a credential logs none of it.

    Covers structlog (captured as event dicts, before rendering) and stdlib
    logging, on: a successful save, a rejected save, the agent-config read,
    and adapter construction for every backend.
    """
    from app.agents.factory import get_agent
    from app.services.settings_service import _agent_config_from_overrides

    stored = _stored_credentials()
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as events:
        row = _settings_row({})
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new=AsyncMock(return_value=row),
        ):
            ok = await async_client.put("/api/settings", json=stored)
            bad = await async_client.put(
                "/api/settings",
                json={
                    "claude_cli_credentials": json.dumps(
                        {"claudeAiOauth": {"accessToken": _sentinel("claude_cli_credentials")}}
                    )
                },
            )
        assert ok.status_code == 200, ok.text
        assert bad.status_code == 422, bad.text

        for backend in ("anthropic_api", "openai", "zai", "claude_code"):
            config = _agent_config_from_overrides({"agent_backend": backend, **stored})
            assert config is not None
            get_agent(user_settings=config)

    _assert_no_sentinel(repr(events), "structlog events")
    _assert_no_sentinel(caplog.text, "stdlib log records")
    _assert_no_sentinel(bad.text, "the 422 error body")


# ── provider errors at the request-time AI call sites (R-008) ──────────
#
# A provider SDK can echo the credential it was sent ("invalid key sk-...").
# Adapters wrap SDK error text verbatim into ``AgentError``, so whatever a
# request-time call site does with ``str(e)`` (log it, put it in a response)
# carries the user's key unless something redacts it. These tests make every
# adapter call raise an error that quotes each stored credential, including
# the token nested inside ``claude_cli_credentials``, and check the response
# and both log streams. They do not care where the redaction happens: at the
# call site, in a shared helper, or at the adapter boundary.


def _echoing_error():
    from app.core.exceptions import AgentError

    return AgentError("provider rejected credentials: " + " | ".join(_all_sentinels()))


def _echoing_agent() -> MagicMock:
    agent = MagicMock()
    agent.classify_lecture = AsyncMock(side_effect=_echoing_error())
    agent.answer_question = AsyncMock(side_effect=_echoing_error())

    async def stream_answer(*_a, **_k):
        raise _echoing_error()
        yield  # pragma: no cover  (makes this an async generator)

    agent.stream_answer = MagicMock(side_effect=stream_answer)
    return agent


def _db_with_stored_credentials(extra=None):
    """A fake ``session.execute`` whose ``user_settings`` row holds every credential.

    ``extra`` maps a table name to the row a lookup on it returns (e.g. the
    chat session); every other statement finds nothing.
    """
    from tests.safety._tenant import tables_in

    settings_row = SimpleNamespace(settings_json=_stored_credentials())

    def execute(statement, *_a, **_k):
        result = MagicMock()
        tables = tables_in(statement)
        row = None
        if "user_settings" in tables:
            row = settings_row
        for table, value in (extra or {}).items():
            if table in tables:
                row = value
        result.scalar_one_or_none.return_value = row
        result.scalars.return_value.all.return_value = []
        result.scalars.return_value.first.return_value = row
        result.first.return_value = row
        result.all.return_value = []
        result.scalar_one.return_value = 0
        result.scalar.return_value = 0
        return result

    return AsyncMock(side_effect=execute)


def _user_agent_config() -> dict:
    return {"agent_backend": "openai", **_stored_credentials()}


async def _site_test_ai(agent, async_client, mock_session) -> str:
    mock_session.execute = _db_with_stored_credentials()
    with (
        patch(
            "app.services.settings_service.get_user_agent_config",
            new=AsyncMock(return_value=_user_agent_config()),
        ),
        patch("app.agents.factory.get_agent", return_value=agent),
    ):
        response = await async_client.post("/api/settings/test-ai")
    assert response.status_code == 502, response.text
    return response.text


async def _site_qa_ask(agent, async_client, mock_session) -> str:
    mock_session.execute = _db_with_stored_credentials()
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.0, 0.0, 0.0]]
    chunk = {
        "chunk_id": "c1",
        "artifact_id": "a1",
        "content": "text",
        "score": 0.9,
        "course_code": "CSIT302",
        "week": 1,
        "filename": "w1.pdf",
    }
    with (
        patch("app.api.qa.quota_service.check_ai_quota", new=AsyncMock()),
        patch("app.api.qa.get_embedding_provider", return_value=provider),
        patch("app.api.qa.search_service.search_chunks", new=AsyncMock(return_value=[chunk])),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new=AsyncMock(return_value=(_user_agent_config(), "en")),
        ),
        patch("app.api.qa.get_agent", return_value=agent),
    ):
        response = await async_client.post("/api/qa/ask", json={"question": "what is X?"})
    assert response.status_code >= 400, response.text
    return response.text


def _chat_patches(agent):
    no_embeddings = MagicMock(side_effect=RuntimeError("embeddings offline"))
    return (
        patch("app.services.chat_service.get_embedding_provider", new=no_embeddings),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new=AsyncMock(return_value=(_user_agent_config(), "en")),
        ),
        patch("app.services.chat_service.get_agent", return_value=agent),
    )


def _chat_session():
    session = AsyncMock()
    session.add = MagicMock()
    chat = SimpleNamespace(
        id="chat-1", user_id="u1", course_id=None, title="t", message_count=0, updated_at=None
    )
    session.execute = _db_with_stored_credentials({"chat_sessions": chat})
    return session


async def _site_chat_send(agent, async_client, mock_session) -> str:
    from app.services import chat_service

    p1, p2, p3 = _chat_patches(agent)
    with p1, p2, p3:
        _user_msg, reply = await chat_service.send_message(
            session=_chat_session(), session_id="chat-1", user_id="u1", content="hi"
        )
    return str(reply.content)


async def _site_chat_stream(agent, async_client, mock_session) -> str:
    from app.services import chat_service

    p1, p2, p3 = _chat_patches(agent)
    events = []
    with p1, p2, p3:
        async for event in chat_service.stream_message(
            session=_chat_session(), session_id="chat-1", user_id="u1", content="hi"
        ):
            events.append(event)
    return repr(events)


#: Every request-time ``get_agent`` call site that turns a provider failure
#: into a response or a log line (floor 3's ADR 0003 allowlist, minus
#: ``concept_service``, whose failure propagates unhandled to a generic 500).
REQUEST_TIME_AI_ERROR_SITES = {
    "POST /api/settings/test-ai": _site_test_ai,
    "POST /api/qa/ask": _site_qa_ask,
    "chat_service.send_message": _site_chat_send,
    "chat_service.stream_message": _site_chat_stream,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("site", sorted(REQUEST_TIME_AI_ERROR_SITES))
async def test_floor2_provider_error_never_echoes_a_stored_credential(
    site, async_client, mock_session, caplog
):
    """A provider error quoting the user's key is neither returned nor logged.

    Covers R-008. ``test-ai`` was fixed in M31-S1-BACKEND-008 (7eecbac); the
    other request-time AI call sites share the same ``str(e)`` handling.
    """
    agent = _echoing_agent()
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as events:
        returned = await REQUEST_TIME_AI_ERROR_SITES[site](agent, async_client, mock_session)

    assert agent.mock_calls, (
        f"{site}: the adapter was never called, so no provider error was raised and "
        "this test proves nothing"
    )
    _assert_no_sentinel(returned, f"{site} response")
    _assert_no_sentinel(repr(events), f"{site} structlog events")
    _assert_no_sentinel(caplog.text, f"{site} stdlib log records")


# ── committed ──────────────────────────────────────────────────────────

#: Formats with a fixed prefix and fixed shape. Each has essentially no
#: innocent lookalike, which is what lets this run over every tracked file.
HIGH_CONFIDENCE_SECRETS = {
    "private key block": re.compile(
        rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "AWS access key id": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Anthropic API key": re.compile(rb"\bsk-ant-(?:api|admin|oat)\d{2}-[A-Za-z0-9_-]{20,}"),
    "OpenAI API key": re.compile(
        rb"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}"
    ),
    "GitHub token": re.compile(
        rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}"
    ),
    "GitLab token": re.compile(rb"\bglpat-[A-Za-z0-9_-]{20,}"),
    "Slack token": re.compile(rb"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Stripe live key": re.compile(rb"\b(?:sk|rk)_live_[A-Za-z0-9]{24,}"),
    "Telegram bot token": re.compile(rb"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
}

MAX_SCAN_BYTES = 2_000_000


def _tracked_files() -> list[pathlib.Path]:
    """Files git tracks; outside a checkout, the service tree minus build dirs."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
        files = [REPO_ROOT / p.decode() for p in out.split(b"\0") if p]
        if files:
            return files
    except (OSError, subprocess.SubprocessError):
        pass
    skip = {".venv", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache"}
    return [
        p
        for p in SERVICE_ROOT.rglob("*")
        if p.is_file() and not (skip & set(p.relative_to(SERVICE_ROOT).parts))
    ]


def test_floor2_no_high_confidence_secret_in_tracked_files():
    """No tracked file contains a credential in a fixed, unmistakable format."""
    files = _tracked_files()
    assert len(files) > 100, f"scan found only {len(files)} files — it has gone blind"
    hits = []
    for path in files:
        try:
            if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue  # binary
        for label, pattern in HIGH_CONFIDENCE_SECRETS.items():
            for match in pattern.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(REPO_ROOT)}:{line}  {label}")
    assert not hits, "Floor 2: credential committed to the tree:\n" + "\n".join(
        f"  {h}" for h in hits
    )


def test_floor2_no_env_file_tracked():
    """Only templates of .env files are tracked."""
    tracked = [p.relative_to(REPO_ROOT).as_posix() for p in _tracked_files()]
    env_like = [
        p
        for p in tracked
        if re.search(r"(^|/)\.env(\.[^/]*)?$", p)
        and not re.search(r"\.(example|sample|template|dist)$", p)
    ]
    assert not env_like, f"Floor 2: environment file(s) committed: {env_like}"


def test_floor2_detect_secrets_baseline_is_wired_and_clean():
    """pre-commit runs detect-secrets against the baseline, and no entry is a real secret."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text())
    hooks = [
        (repo.get("repo", ""), hook)
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
    ]
    detect = [
        h for repo, h in hooks if "detect-secrets" in repo and h.get("id") == "detect-secrets"
    ]
    assert detect, "detect-secrets hook missing from .pre-commit-config.yaml"
    args = detect[0].get("args", [])
    assert "--baseline" in args and args[args.index("--baseline") + 1] == ".secrets.baseline"
    assert any(h.get("id") == "detect-private-key" for _repo, h in hooks)

    baseline = json.loads((REPO_ROOT / ".secrets.baseline").read_text())
    flagged = [
        f"{f}:{e.get('line_number')}"
        for f, entries in baseline.get("results", {}).items()
        for e in entries
        if e.get("is_secret") is True
    ]
    assert not flagged, f"Floor 2: baseline entries audited as real secrets: {flagged}"


def test_floor2_sentinels_are_not_secret_shaped():
    """The sentinels this file plants must not themselves trip the scanner."""
    for s in _all_sentinels():
        for label, pattern in HIGH_CONFIDENCE_SECRETS.items():
            assert not pattern.search(s.encode()), (s, label)
