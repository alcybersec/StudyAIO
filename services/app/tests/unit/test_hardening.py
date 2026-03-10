"""Comprehensive hardening tests for Milestone 12 security features."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AuthenticationError

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "1; mode=block",
    "referrer-policy": "strict-origin-when-cross-origin",
}


@pytest.mark.asyncio
class TestRateLimiting:
    """Rate limiting returns 429 after exceeding limits."""

    async def test_upload_rate_limit_returns_429(self, async_client):
        """Exceeding upload rate limit returns 429."""
        from app.core.rate_limit import limiter

        limiter.reset()

        mock_result = MagicMock()
        mock_result.id = "task-id"

        # Default rate_limit_uploads is "10/minute".  Patching Pydantic v2
        # Settings attributes via mock.patch is unreliable, so we hit the
        # real limit by sending 10+1 requests instead.
        with patch("app.api.uploads.run_pipeline", return_value=mock_result):
            small_pdf = b"x" * 100
            for _ in range(10):
                resp = await async_client.post(
                    "/api/uploads",
                    files={"file": ("test.pdf", small_pdf, "application/pdf")},
                )
                assert resp.status_code == 201

            # 11th request should be rate limited
            resp = await async_client.post(
                "/api/uploads",
                files={"file": ("test.pdf", small_pdf, "application/pdf")},
            )
            assert resp.status_code == 429

    async def test_rate_limit_headers_present(self, async_client):
        """Rate limited responses should still include security headers."""
        from app.core.rate_limit import limiter

        limiter.reset()

        # Use /api/auth/register which has a hardcoded "3/minute" limit —
        # avoids patching Pydantic Settings and keeps the test fast.
        with patch(
            "app.api.auth.user_service.register_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("mocked"),
        ):
            for _ in range(3):
                await async_client.post(
                    "/api/auth/register",
                    json={"email": "u@e.com", "username": "usr", "password": "Pass1!aa"},
                )
            # 4th request triggers 429
            resp = await async_client.post(
                "/api/auth/register",
                json={"email": "u@e.com", "username": "usr", "password": "Pass1!aa"},
            )
            assert resp.status_code == 429
            # Security headers still present on 429
            for header in SECURITY_HEADERS:
                assert header in resp.headers, f"Missing {header} on 429"


@pytest.mark.asyncio
class TestFileSizeLimits:
    """File size enforcement on upload endpoints."""

    async def test_oversized_upload_returns_413(self, async_client):
        """Files exceeding MAX_UPLOAD_SIZE_MB get 413."""
        large_content = b"x" * (2 * 1024 * 1024)  # 2 MB

        with patch("app.config.settings.max_upload_size_mb", 1):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("test.pdf", large_content, "application/pdf")},
            )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    async def test_batch_oversized_file_reported(self, async_client):
        """Oversized file in batch is reported as error, other files proceed."""
        large_content = b"x" * (2 * 1024 * 1024)
        small_content = b"x" * 100

        mock_result = MagicMock()
        mock_result.id = "task-id"

        with (
            patch("app.config.settings.max_upload_size_mb", 1),
            patch("app.api.uploads.run_pipeline", return_value=mock_result),
        ):
            response = await async_client.post(
                "/api/uploads/batch",
                files=[
                    ("files", ("small.pdf", small_content, "application/pdf")),
                    ("files", ("large.pdf", large_content, "application/pdf")),
                ],
            )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] >= 1
        # At least one should have the size error
        error_results = [r for r in data["results"] if r["status"] == "error"]
        assert any("too large" in (r.get("error") or "").lower() for r in error_results)


@pytest.mark.asyncio
class TestSecurityHeadersComprehensive:
    """Security headers on all response types."""

    async def test_all_security_headers_on_200(self, async_client):
        """Health check response has all 4 security headers."""
        response = await async_client.get("/health")
        for header, value in SECURITY_HEADERS.items():
            assert response.headers.get(header) == value

    async def test_security_headers_on_404(self, async_client):
        """404 responses include security headers."""
        response = await async_client.get("/nonexistent")
        for header in SECURITY_HEADERS:
            assert header in response.headers

    async def test_security_headers_on_400(self, async_client):
        """400 responses include security headers."""
        response = await async_client.post(
            "/api/uploads",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        for header in SECURITY_HEADERS:
            assert header in response.headers


@pytest.mark.asyncio
class TestRequestIDPropagation:
    """Request ID middleware behavior."""

    async def test_generated_request_id(self, async_client):
        """Requests without X-Request-ID get one generated."""
        response = await async_client.get("/health")
        rid = response.headers.get("x-request-id")
        assert rid is not None
        assert len(rid) == 36  # UUID4 format

    async def test_echoed_request_id(self, async_client):
        """Client-provided X-Request-ID is echoed back."""
        response = await async_client.get(
            "/health",
            headers={"X-Request-ID": "test-abc-123"},
        )
        assert response.headers["x-request-id"] == "test-abc-123"

    async def test_unique_request_ids(self, async_client):
        """Each request gets a unique ID when not provided."""
        r1 = await async_client.get("/health")
        r2 = await async_client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


@pytest.mark.asyncio
class TestCORSConfiguration:
    """CORS configuration from settings."""

    async def test_allowed_origin_accepted(self, async_client):
        """Preflight from allowed origin returns CORS header."""
        response = await async_client.options(
            "/health",
            headers={
                "origin": "http://localhost:3001",
                "access-control-request-method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"

    async def test_disallowed_origin_rejected(self, async_client):
        """Preflight from disallowed origin does not return allow-origin."""
        response = await async_client.options(
            "/health",
            headers={
                "origin": "http://attacker.com",
                "access-control-request-method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "http://attacker.com"
