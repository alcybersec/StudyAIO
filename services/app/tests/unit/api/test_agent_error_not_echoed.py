"""Floor 2: a provider failure's text never reaches a response or the logs unredacted.

Provider SDK errors can echo the credential that was sent, so ``AgentError``
is rendered generically; its text is available only after redaction.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.database import get_session
from app.core.exceptions import AgentError, ExtractionError
from app.main import app

SENTINEL = "sk-ant-SENTINEL-credential-0123456789"


@pytest.mark.asyncio
class TestStudyAIOErrorHandler:
    async def _hit(self, exc: Exception) -> httpx.Response:
        path = "/__test_raise"

        async def boom():
            raise exc

        app.add_api_route(path, boom, methods=["GET"])
        try:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)
        finally:
            app.router.routes.pop()

    async def test_agent_error_detail_is_generic(self):
        resp = await self._hit(AgentError(f"401 invalid x-api-key: {SENTINEL}"))
        assert resp.status_code == 500
        assert SENTINEL not in resp.text
        assert "invalid x-api-key" not in resp.text

    async def test_agent_error_text_is_not_logged_raw(self):
        with patch("app.main.logger") as log:
            await self._hit(AgentError(f"boom {SENTINEL}"))
        assert SENTINEL not in repr(log.mock_calls)

    async def test_other_studyaio_errors_keep_their_detail(self):
        resp = await self._hit(ExtractionError("PDF is encrypted"))
        assert resp.status_code == 500
        assert resp.json() == {"detail": "PDF is encrypted"}


@pytest.mark.asyncio
class TestConceptsExtractEndpoint:
    async def test_agent_error_is_redacted_and_generic(self, async_client, default_test_user):
        artifact = MagicMock()
        artifact.course_id = "c1"
        artifact.week = 1
        found = MagicMock()
        found.scalar_one_or_none.return_value = artifact

        session = AsyncMock()
        session.execute = AsyncMock(return_value=found)

        async def override():
            yield session

        app.dependency_overrides[get_session] = override
        with (
            patch("app.api.concepts.quota_service.check_ai_quota", new_callable=AsyncMock),
            patch(
                "app.api.concepts.concept_service.extract_and_save_concepts",
                new_callable=AsyncMock,
                side_effect=AgentError(f"auth failed for {SENTINEL}"),
            ),
            patch(
                "app.api.concepts.settings_service.redacted_error",
                new_callable=AsyncMock,
                return_value="auth failed for [redacted]",
            ) as redact,
            patch("app.api.concepts.logger") as log,
            patch("app.agents.parsing.build_extraction_text", return_value="t"),
            patch("app.services.summary_service.merge_extractions", return_value={}),
        ):
            resp = await async_client.post("/api/concepts/extract/art-1")

        assert resp.status_code == 502
        assert SENTINEL not in resp.text
        assert redact.await_args.args[1] == default_test_user.id
        assert SENTINEL not in repr(log.mock_calls)
