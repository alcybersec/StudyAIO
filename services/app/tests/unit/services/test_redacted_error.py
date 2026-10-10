"""Unit tests for ``settings_service.redacted_error`` and its call sites (M31-S1-BACKEND-010)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.services import settings_service

USER = "0192abcd-dead-beef-cafe-00000000000a"
SECRET = "sk-user-secret-999-abcdef"


def _session_with_key() -> AsyncMock:
    row = MagicMock()
    row.settings_json = {"openai_api_key": SECRET}
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_redacted_error_removes_key_inside_exception_text():
    out = await settings_service.redacted_error(
        _session_with_key(), USER, RuntimeError(f"401 invalid key {SECRET}")
    )
    assert SECRET not in out
    assert settings_service.REDACTED in out


@pytest.mark.asyncio
async def test_redacted_error_withholds_text_when_scrub_fails():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    out = await settings_service.redacted_error(session, USER, ValueError(f"bad {SECRET}"))
    assert SECRET not in out
    assert "ValueError" in out


@pytest.mark.asyncio
async def test_qa_ask_agent_error_redacted_in_body_and_log(async_client, mock_session):
    mock_session.execute = _session_with_key().execute
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.0]]
    agent = MagicMock()
    agent.answer_question = AsyncMock(side_effect=RuntimeError(f"bad key {SECRET}"))
    with (
        patch("app.api.qa.quota_service.check_ai_quota", new=AsyncMock()),
        patch("app.api.qa.get_embedding_provider", return_value=provider),
        patch(
            "app.api.qa.search_service.search_chunks",
            new=AsyncMock(return_value=[{"chunk_id": "c"}]),
        ),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new=AsyncMock(return_value=({}, "en")),
        ),
        patch("app.api.qa.get_agent", return_value=agent),
        structlog.testing.capture_logs() as logs,
    ):
        response = await async_client.post("/api/qa/ask", json={"question": "q?"})
    assert response.status_code == 500
    assert SECRET not in response.text
    assert SECRET not in repr(logs)
    assert any(e["event"] == "qa_agent_error" for e in logs)


@pytest.mark.asyncio
async def test_qa_ask_embedding_error_redacted_in_log(async_client, mock_session):
    mock_session.execute = _session_with_key().execute
    provider = MagicMock()
    provider.embed_texts.side_effect = RuntimeError(f"embed auth failed {SECRET}")
    with (
        patch("app.api.qa.quota_service.check_ai_quota", new=AsyncMock()),
        patch("app.api.qa.get_embedding_provider", return_value=provider),
        structlog.testing.capture_logs() as logs,
    ):
        response = await async_client.post("/api/qa/ask", json={"question": "q?"})
    assert response.status_code == 500
    assert SECRET not in response.text
    assert SECRET not in repr(logs)
    assert any(e["event"] == "qa_embedding_error" for e in logs)
