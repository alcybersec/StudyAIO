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

import contextlib
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


class _ProviderEcho:
    """Make every provider SDK fail with an error that quotes the credential it was sent.

    It patches the SDKs themselves rather than the adapters: the OpenAI chat
    ``create`` (OpenAI and Z.ai), the Anthropic messages ``create``, and the
    ``claude`` CLI subprocess, which prints the OAuth token it found back on
    stdout. The adapter, its ``AgentError`` wrapping and every layer above run
    for real, so a fix anywhere (the adapter boundary, a call site, the global
    handler) turns these tests green, and an echo nothing redacts keeps them red.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _openai(self):
        echo = self

        async def create(resource, *_a, **_k):
            echo.calls.append("openai")
            raise RuntimeError(
                f"Error code: 401 - Incorrect API key provided: {resource._client.api_key}"
            )

        return create

    def _anthropic(self):
        echo = self

        async def create(resource, *_a, **_k):
            echo.calls.append("anthropic")
            raise RuntimeError(
                f"authentication_error: invalid x-api-key {resource._client.api_key}"
            )

        return create

    def _subprocess(self):
        echo = self

        async def create_subprocess_exec(*_cmd, env=None, **_k):
            echo.calls.append("claude_cli")
            token = ""
            config_dir = (env or {}).get("CLAUDE_CONFIG_DIR")
            if config_dir:
                creds = json.loads((pathlib.Path(config_dir) / ".credentials.json").read_text())
                token = creds.get("claudeAiOauth", {}).get("accessToken", "")
            process = MagicMock()
            process.returncode = 1
            process.communicate = AsyncMock(
                return_value=(
                    f"401 OAuth access token {token} has been revoked".encode(),
                    b"",
                )
            )
            return process

        return create_subprocess_exec

    def __enter__(self) -> _ProviderEcho:
        import asyncio

        from anthropic.resources.messages.messages import AsyncMessages
        from openai.resources.chat.completions.completions import AsyncCompletions

        self._stack = contextlib.ExitStack()
        self._stack.enter_context(patch.object(AsyncCompletions, "create", self._openai()))
        self._stack.enter_context(patch.object(AsyncMessages, "create", self._anthropic()))
        self._stack.enter_context(
            patch.object(asyncio, "create_subprocess_exec", self._subprocess())
        )
        return self

    def __exit__(self, *exc) -> None:
        self._stack.__exit__(*exc)


def _real_agent_config(backend: str) -> dict:
    """The agent config a user on ``backend`` with every credential stored gets."""
    from app.services.settings_service import _agent_config_from_overrides

    config = _agent_config_from_overrides({"agent_backend": backend, **_stored_credentials()})
    assert config is not None
    return config


async def _site_concepts_extract(agent, async_client, mock_session) -> str:
    """ADR 0003 site #5. Runs the real adapter (``_ProviderEcho`` makes it fail).

    ``agent`` is unused: this site has no call-site handling to bypass, so the
    error must be the one a real adapter builds from a real SDK failure.
    """
    del agent
    artifact = SimpleNamespace(id="a1", user_id="u1", course_id="c1", week=1)
    extraction = SimpleNamespace(artifact_id="a1", manifest_json={"pages": []})
    mock_session.execute = _db_with_stored_credentials(
        {"lecture_artifacts": artifact, "extractions": extraction}
    )
    with (
        patch("app.api.concepts.quota_service.check_ai_quota", new=AsyncMock()),
        patch("app.agents.parsing.build_extraction_text", return_value="lecture text"),
        patch(
            "app.services.settings_service.get_user_agent_config",
            new=AsyncMock(return_value=_real_agent_config("openai")),
        ),
    ):
        response = await async_client.post("/api/concepts/extract/a1")
    assert response.status_code >= 400, response.text
    return response.text


#: Every request-time ``get_agent`` call site (floor 3's ADR 0003 allowlist).
#: ``concept_service`` (site #5) was left out until M31-S2 on the assumption
#: that its failure "propagates unhandled to a generic 500"; the M31 gate
#: showed the global ``StudyAIOError`` handler echoes ``str(exc)`` instead.
REQUEST_TIME_AI_ERROR_SITES = {
    "POST /api/settings/test-ai": _site_test_ai,
    "POST /api/qa/ask": _site_qa_ask,
    "chat_service.send_message": _site_chat_send,
    "chat_service.stream_message": _site_chat_stream,
    "POST /api/concepts/extract/{artifact_id}": _site_concepts_extract,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("site", sorted(REQUEST_TIME_AI_ERROR_SITES))
async def test_floor2_provider_error_never_echoes_a_stored_credential(
    site, async_client, mock_session, caplog
):
    """A provider error quoting the user's key is neither returned nor logged.

    Covers R-008: ``test-ai`` fixed in 7eecbac, ``qa/ask`` and chat in
    718faa0. The concepts site (#5) runs the real adapter, see
    ``_site_concepts_extract``.
    """
    agent = _echoing_agent()
    caplog.set_level(logging.DEBUG)
    with _ProviderEcho() as echo, structlog.testing.capture_logs() as events:
        returned = await REQUEST_TIME_AI_ERROR_SITES[site](agent, async_client, mock_session)

    assert agent.mock_calls or echo.calls, (
        f"{site}: the adapter was never called, so no provider error was raised and "
        "this test proves nothing"
    )
    _assert_no_sentinel(returned, f"{site} response")
    _assert_no_sentinel(repr(events), f"{site} structlog events")
    _assert_no_sentinel(caplog.text, f"{site} stdlib log records")


# ── provider errors in the worker (R-012) ──────────────────────────────
#
# The worker has no request to answer, but it writes the failure twice:
# ``pipeline_runs.error_message`` (``pipeline/failures.py``, shown to the user
# in the upload status view) and its logs (``*_task_error``,
# ``courseops_document_failed``, and Celery's own "Task ... raised" line,
# which renders the exception the task ends with). Each test drives a real
# Celery task, eagerly, with a real adapter whose SDK echoes the key.

#: Backends that send a stored per-user credential to a provider.
CREDENTIALED_BACKENDS = ("anthropic_api", "openai", "zai", "claude_code")


class _WorkerSession:
    """Just enough of an ``AsyncSession`` for one task to run and fail."""

    def __init__(self, rows: dict[str, object], by_pk: dict[type, object]):
        from tests.safety._tenant import tables_in

        self.added: list[object] = []
        self._by_pk = by_pk
        settings_row = SimpleNamespace(settings_json=_stored_credentials())

        def execute(statement, *_a, **_k):
            tables = tables_in(statement)
            row = settings_row if "user_settings" in tables else None
            for table, value in rows.items():
                if table in tables:
                    row = value
            result = MagicMock()
            result.scalar_one_or_none.return_value = row
            result.scalars.return_value.first.return_value = row
            result.scalars.return_value.all.return_value = []
            result.all.return_value = []
            result.first.return_value = row
            return result

        self.execute = AsyncMock(side_effect=execute)
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()
        self.close = AsyncMock()

    def add(self, obj) -> None:
        self.added.append(obj)

    async def get(self, model, ident, *_a, **_k):
        return self._by_pk.get(model)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _run_task(task, *args):
    """Run a Celery task eagerly; return the exception it ended with (or None)."""
    result = task.apply(args=args)
    return result.result if isinstance(result.result, BaseException) else None


def _worker_classify(backend: str) -> tuple[str, list[str]]:
    from app.models.artifact import LectureArtifact
    from app.models.pipeline_run import PipelineRun
    from app.pipeline import classify

    artifact = SimpleNamespace(
        id="a1",
        user_id="u1",
        file_path="uploads/u1/a1.pdf",
        file_type="pdf",
        original_filename="CSIT302_week1.pdf",
        status="ingested",
        course_id=None,
        week=None,
    )
    session = _WorkerSession({"lecture_artifacts": artifact}, {LectureArtifact: artifact})
    with (
        patch.object(classify, "async_session_factory", return_value=session),
        patch.object(classify, "publish_pipeline_event_sync", MagicMock()),
        patch.object(classify, "_extract_text_preview", return_value="CSIT302 week 1"),
        patch.object(classify, "_get_known_courses", new=AsyncMock(return_value=[])),
        patch(
            "app.services.settings_service.get_user_agent_config",
            new=AsyncMock(return_value=_real_agent_config(backend)),
        ),
    ):
        raised = _run_task(classify.classify_artifact, {"artifact_id": "a1", "user_id": "u1"})
    runs = [o for o in session.added if isinstance(o, PipelineRun) and o.status == "failed"]
    assert runs, "classify recorded no failed pipeline_runs row, so this test proves nothing"
    stored = [f"pipeline_runs.error_message={r.error_message!r}" for r in runs]
    return repr(raised), stored


def _worker_courseops(backend: str) -> tuple[str, list[str]]:
    from app.core.storage import LocalStorageBackend
    from app.models.course import Course
    from app.models.course_document import CourseDocument
    from app.pipeline import courseops_task

    doc = SimpleNamespace(
        id="d1",
        user_id="u1",
        course_id="c1",
        file_path="courseops/u1/d1/outline.pdf",
        file_type="pdf",
        document_type="outline",
        status="uploaded",
    )
    course = SimpleNamespace(id="c1", code="CSIT302", user_id="u1")
    session = _WorkerSession({}, {CourseDocument: doc, Course: course})
    storage = MagicMock(spec=LocalStorageBackend)
    file_path = MagicMock()
    file_path.exists.return_value = True
    storage.resolve_path.return_value = file_path
    extractor = MagicMock()
    extractor.extract.return_value = SimpleNamespace(
        pages=[SimpleNamespace(text="Assignment 1 due week 5")]
    )
    with (
        patch.object(courseops_task, "async_session_factory", return_value=session),
        patch.object(courseops_task, "get_storage", return_value=storage),
        patch.object(courseops_task, "get_extractor", return_value=extractor),
        patch(
            "app.services.settings_service.get_user_agent_config",
            new=AsyncMock(return_value=_real_agent_config(backend)),
        ),
    ):
        raised = _run_task(courseops_task.process_course_document, "d1")
    assert doc.status == "failed", "courseops did not record the failure; this proves nothing"
    return repr(raised), []


WORKER_AI_ERROR_SITES = {
    "pipeline.classify.classify_artifact": _worker_classify,
    "pipeline.courseops_task.process_course_document": _worker_courseops,
}


@pytest.mark.parametrize("backend", CREDENTIALED_BACKENDS)
@pytest.mark.parametrize("site", sorted(WORKER_AI_ERROR_SITES))
def test_floor2_worker_provider_error_never_stores_or_logs_a_credential(site, backend, caplog):
    """A provider error quoting the user's key reaches no pipeline_runs row and no log.

    Covers R-012 and, through the same adapters, ADR 0003 site #5. A fix at
    the adapter boundary (redact at ``AgentError`` construction) covers both
    processes at once; per-site redaction would have to repeat in every stage.
    """
    caplog.set_level(logging.DEBUG)
    with _ProviderEcho() as echo, structlog.testing.capture_logs() as events:
        raised, stored = WORKER_AI_ERROR_SITES[site](backend)

    assert echo.calls, f"{site}[{backend}]: no provider call was made; this proves nothing"
    _assert_no_sentinel("\n".join(stored), f"{site}[{backend}] pipeline_runs.error_message")
    _assert_no_sentinel(repr(events), f"{site}[{backend}] structlog events")
    _assert_no_sentinel(caplog.text, f"{site}[{backend}] stdlib log records")
    _assert_no_sentinel(raised, f"{site}[{backend}] the exception the task ended with")


# ── the global StudyAIOError handler ───────────────────────────────────

#: Distinctive text inside a provider error, so the test can tell whether the
#: handler passed the raw message through at all.
RAW_PROVIDER_TEXT = "floor2-raw-provider-text-4b1d"
INSTANCE_SENTINEL = "floor2-sentinel-instance-key-7f3a9c"


#: Where the global handler is reached from. The concepts route used to be the
#: driver here, until BACKEND-013 made it catch ``AgentError`` itself: from
#: then on the test exercised the route and never the handler, and disabling
#: the handler's ``AgentError`` branch left it green (M31 re-run, mutant 3c,
#: F-1). The concepts route is pinned as a request-time site above. This pin
#: reaches the handler on two paths no route catch can shadow: a direct call,
#: and a probe route mounted for the test that lets the error escape, so
#: FastAPI's own dispatch picks the handler (a narrower ``AgentError``
#: handler registered later would be the one tested).
GLOBAL_HANDLER_PATHS = ("direct call", "escaping route")
PROBE_PATH = "/api/__floor2_global_handler_probe__"


def _agent_error_subclass(message: str) -> Exception:
    """An ``AgentError`` subclass instance, so the handler's branch must cover subclasses."""
    from app.core.exceptions import AgentError

    return type("ProbeProviderError", (AgentError,), {})(message)


async def _through_global_handler(path: str, error: Exception, async_client) -> tuple[int, str]:
    """Hand ``error`` to the global ``StudyAIOError`` handler; return (status, body)."""
    from starlette.requests import Request

    from app.main import app, studyaio_error_handler

    if path == "direct call":
        request = Request({"type": "http", "method": "GET", "path": PROBE_PATH, "headers": []})
        response = await studyaio_error_handler(request, error)
        return response.status_code, response.body.decode()

    async def probe() -> dict:
        raise error

    app.add_api_route(PROBE_PATH, probe, methods=["GET"])
    route = app.router.routes[-1]
    try:
        response = await async_client.get(PROBE_PATH)
    finally:
        app.router.routes.remove(route)
    return response.status_code, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", GLOBAL_HANDLER_PATHS)
async def test_floor2_global_handler_never_returns_or_logs_raw_agent_error(
    path, async_client, caplog
):
    """An ``AgentError`` that reaches ``studyaio_error_handler`` is answered and logged generically.

    ``main.studyaio_error_handler`` used to log ``error=str(exc)`` and return
    ``{"detail": str(exc)}`` for every application error, so any ``AgentError``
    that escaped a route went to the client verbatim. Provider text can echo
    the credential that was sent, and the handler has no user to redact
    against, so none of the message may leave: not the provider's text, not
    the instance key, and not a per-user key (an ``AgentError`` built outside
    the adapter's redaction, as this one is, carries them raw).
    """
    from pydantic import SecretStr

    from app.config import settings
    from app.main import app

    user_keys = " ".join(_all_sentinels())
    error = _agent_error_subclass(
        f"OpenAI API call failed: {RAW_PROVIDER_TEXT} Incorrect API key provided: "
        f"{INSTANCE_SENTINEL} / {user_keys}"
    )
    routes_before = len(app.router.routes)
    caplog.set_level(logging.DEBUG)
    with (
        structlog.testing.capture_logs() as events,
        patch.object(settings, "openai_api_key", SecretStr(INSTANCE_SENTINEL)),
    ):
        status, body = await _through_global_handler(path, error, async_client)

    assert len(app.router.routes) == routes_before, "the probe route was left mounted"
    assert status == 500, f"{path}: the error did not reach the global handler: {status} {body}"
    assert RAW_PROVIDER_TEXT not in body, (
        f"Floor 2 ({path}): the global handler returned raw AgentError text: {body}"
    )
    assert INSTANCE_SENTINEL not in body, f"Floor 2 ({path}): instance key in the response"
    _assert_no_sentinel(body, f"the global handler's response ({path})")
    for where, text in (("structlog events", repr(events)), ("stdlib log records", caplog.text)):
        assert RAW_PROVIDER_TEXT not in text, f"Floor 2 ({path}): raw AgentError text in {where}"
        assert INSTANCE_SENTINEL not in text, (
            f"Floor 2 ({path}): the global handler logged a credential in {where}"
        )
        _assert_no_sentinel(text, f"{where} ({path})")


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
    """Every file git tracks in the repository. Fails the test if git cannot say.

    There is deliberately no fallback. The old one scanned ``services/app``
    when git was missing, which silently dropped ``docs/``, ``infra/`` and the
    rest of the tree from a check whose subject is "the tree" (a false green
    in CI, pipeline 525). A floor check that cannot see its subject fails.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.fail(
            f"Floor 2: cannot list tracked files with git ({exc!r}). The committed-secret "
            "checks need git and a checkout; install git in this environment rather than "
            "scanning a subset of the tree."
        )
    files = [REPO_ROOT / p.decode() for p in out.split(b"\0") if p]
    if not files:
        pytest.fail(f"Floor 2: git ls-files listed nothing under {REPO_ROOT}; not a checkout?")
    return files


@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError("git"), subprocess.CalledProcessError(128, "git"), "empty"],
    ids=["git-missing", "not-a-checkout", "no-files"],
)
def test_floor2_tracked_file_scan_fails_loudly_without_git(failure):
    """No git, no scan: the committed-secret checks must fail, not shrink to services/app.

    In CI the ``python:3.12-slim`` job had no git, ``_tracked_files`` swallowed
    the OSError and fell back to the service tree, and an AKIA sentinel
    committed under ``docs/`` passed ``test-floor`` (pipeline 525, job 4301).
    """
    real_run = subprocess.run

    def run(cmd, *a, **k):
        if cmd and cmd[0] == "git":
            if failure == "empty":
                return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
            raise failure
        return real_run(cmd, *a, **k)

    with patch.object(subprocess, "run", run), pytest.raises(pytest.fail.Exception) as info:
        _tracked_files()
    assert "git" in str(info.value)


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
