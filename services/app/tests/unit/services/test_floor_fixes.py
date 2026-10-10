"""Unit tests for the floor fixes V1-V4 and R-008 (M31-S1-BACKEND-008)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.services import account_service, courseops_service, settings_service

USER_A = "0192abcd-dead-beef-cafe-00000000000a"
KEY = f"courseops/{USER_A}/0123456789abcdef_handbook.pdf"


def _session_returning_scalar(value: object) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = value
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
class TestAttachAssessmentDocumentScoping:
    async def test_scoped_lookup_returns_none_for_foreign_assessment(self):
        session = _session_returning_scalar(None)
        doc = await courseops_service.attach_assessment_document(
            session,
            assessment_id="a1",
            document_type="brief",
            original_filename="x.pdf",
            file_path=KEY,
            file_type="pdf",
            sha256="0" * 64,
            file_size_bytes=1,
            user_id=USER_A,
        )
        assert doc is None
        session.add.assert_not_called()
        # The owner join is in the query, not a bare session.get
        session.get.assert_not_called()
        stmt = str(session.execute.call_args.args[0])
        assert "courses.user_id" in stmt


@pytest.mark.asyncio
class TestDiscardFailedUploadBlob:
    async def test_keeps_blob_an_existing_row_references(self):
        storage = AsyncMock()
        deleted = await courseops_service.discard_failed_upload_blob(
            _session_returning_scalar(1), USER_A, KEY, storage
        )
        assert deleted is False
        storage.delete.assert_not_called()

    async def test_deletes_blob_nothing_references(self):
        storage = AsyncMock()
        storage.exists.return_value = True
        deleted = await courseops_service.discard_failed_upload_blob(
            _session_returning_scalar(0), USER_A, KEY, storage
        )
        assert deleted is True
        storage.delete.assert_awaited_once_with(KEY)


class TestExportStripsCredentials:
    def test_settings_json_loses_every_secret_key(self):
        blob = {k: "sekret-value" for k in settings_service.SECRET_KEYS}
        blob["agent_backend"] = "openai"
        out = account_service._export_value("settings_json", blob)
        assert out == {"agent_backend": "openai"}

    def test_other_columns_untouched(self):
        assert account_service._export_value("theme", "dark") == "dark"


@pytest.mark.asyncio
class TestRedactUserSecrets:
    async def test_redacts_stored_key_and_nested_cli_token(self):
        creds = json.dumps({"claudeAiOauth": {"accessToken": "tok-abcdef123456"}})
        row = MagicMock()
        row.settings_json = {
            "openai_api_key": "sk-user-secret-999",
            "claude_cli_credentials": creds,
        }
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        session.execute = AsyncMock(return_value=result)
        text = "401 bad key sk-user-secret-999 / token tok-abcdef123456"
        out = await settings_service.redact_user_secrets(session, USER_A, text)
        assert "sk-user-secret-999" not in out
        assert "tok-abcdef123456" not in out
        assert out.count(settings_service.REDACTED) == 2


@pytest.mark.asyncio
async def test_test_ai_error_is_redacted_in_response_and_logs(async_client):
    """A provider error echoing the key is redacted in the 502 body and the log."""
    secret = "sk-user-secret-999"
    agent = MagicMock()
    agent.classify_lecture = AsyncMock(side_effect=RuntimeError(f"invalid key {secret}"))
    with (
        patch(
            "app.services.settings_service.get_user_agent_config",
            new_callable=AsyncMock,
            return_value={"agent_backend": "openai", "openai_api_key": secret},
        ),
        patch("app.agents.factory.get_agent", return_value=agent),
        patch(
            "app.services.settings_service.redact_user_secrets",
            new=AsyncMock(side_effect=lambda s, u, t: t.replace(secret, "[redacted]")),
        ),
        structlog.testing.capture_logs() as logs,
    ):
        response = await async_client.post("/api/settings/test-ai")

    assert response.status_code == 502
    assert secret not in response.text
    assert "[redacted]" in response.text
    assert secret not in json.dumps(logs, default=str)
    assert any(e["event"] == "test_ai_failed" for e in logs)
