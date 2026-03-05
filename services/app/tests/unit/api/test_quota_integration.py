"""Tests for quota enforcement integration in API endpoints."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import QuotaExceededError


@pytest.fixture
def free_user(make_user):
    """A free-tier user."""
    return make_user(
        id="user-free",
        email="free@test.com",
        username="freeuser",
        role="user",
        tier="free",
    )


@pytest.fixture
async def saas_client(mock_session, free_user):
    """Async client simulating SaaS mode (self_hosted=False) with free user."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return free_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    app.dependency_overrides[get_current_user] = override_user

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir:
        with (
            patch("app.config.settings.data_dir", tmpdir),
            patch("app.config.settings.self_hosted", False),
            patch("app.api.uploads.settings.self_hosted", False),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client

    app.dependency_overrides.clear()


class TestUploadQuota:
    """Tests for upload quota enforcement."""

    @pytest.mark.asyncio
    @patch("app.api.uploads.quota_service")
    async def test_upload_blocked_when_quota_exceeded(self, mock_quota, saas_client):
        """Free user gets 402 when upload quota exceeded."""
        mock_quota.check_upload_quota = AsyncMock(
            side_effect=QuotaExceededError(
                resource="uploads", limit=5, period="month"
            )
        )

        # Create a small PDF-like file
        import io

        file_content = b"%PDF-1.4 test content"
        resp = await saas_client.post(
            "/api/uploads",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 402
        data = resp.json()
        assert data["resource"] == "uploads"

    @pytest.mark.asyncio
    @patch("app.api.uploads.billing_service")
    @patch("app.api.uploads.quota_service")
    @patch("app.api.uploads.run_pipeline")
    async def test_upload_allowed_when_under_quota(
        self, mock_pipeline, mock_quota, mock_billing, saas_client
    ):
        """Free user can upload when under quota."""
        mock_quota.check_upload_quota = AsyncMock(return_value=None)
        mock_billing.record_usage = AsyncMock()

        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_pipeline.return_value = mock_result

        import io

        file_content = b"%PDF-1.4 test content"
        with patch("app.api.uploads.xp_service"):
            resp = await saas_client.post(
                "/api/uploads",
                files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
            )
        assert resp.status_code == 201


class TestQAQuota:
    """Tests for Q&A AI quota enforcement."""

    @pytest.mark.asyncio
    @patch("app.api.qa.quota_service")
    async def test_qa_blocked_when_quota_exceeded(self, mock_quota, saas_client):
        """Free user gets 402 when AI quota exceeded."""
        mock_quota.check_ai_quota = AsyncMock(
            side_effect=QuotaExceededError(
                resource="ai_calls", limit=20, period="day"
            )
        )

        resp = await saas_client.post(
            "/api/qa/ask",
            json={"question": "What is a firewall?"},
        )
        assert resp.status_code == 402
        assert resp.json()["resource"] == "ai_calls"


class TestChatQuota:
    """Tests for chat AI quota enforcement."""

    @pytest.mark.asyncio
    @patch("app.api.chat.quota_service")
    async def test_chat_blocked_when_quota_exceeded(self, mock_quota, saas_client):
        """Free user gets 402 when AI quota exceeded in chat."""
        mock_quota.check_ai_quota = AsyncMock(
            side_effect=QuotaExceededError(
                resource="ai_calls", limit=20, period="day"
            )
        )

        resp = await saas_client.post(
            "/api/chat/sessions/test-session/messages",
            json={"content": "Hello"},
        )
        assert resp.status_code == 402


class TestConceptExtractionQuota:
    """Tests for concept extraction AI quota enforcement."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.quota_service")
    async def test_extraction_blocked_when_quota_exceeded(self, mock_quota, saas_client):
        """Free user gets 402 when AI quota exceeded for concept extraction."""
        mock_quota.check_ai_quota = AsyncMock(
            side_effect=QuotaExceededError(
                resource="ai_calls", limit=20, period="day"
            )
        )

        resp = await saas_client.post("/api/concepts/extract/artifact-123")
        assert resp.status_code == 402


class TestSelfHostedBypass:
    """Tests that self-hosted mode bypasses all quotas."""

    @pytest.mark.asyncio
    @patch("app.api.qa.get_embedding_provider")
    @patch("app.api.qa.quota_service")
    @patch("app.api.qa.search_service")
    async def test_qa_bypasses_in_self_hosted(
        self, mock_search, mock_quota, mock_embed, async_client
    ):
        """Self-hosted mode doesn't block on AI quota."""
        # async_client uses default self_hosted=True
        mock_quota.check_ai_quota = AsyncMock(return_value=None)
        mock_search.search_chunks = AsyncMock(return_value=[])
        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]
        mock_embed.return_value = mock_provider

        resp = await async_client.post(
            "/api/qa/ask",
            json={"question": "What is a firewall?"},
        )
        # Should get 200 (no relevant chunks message) not 402
        assert resp.status_code == 200
