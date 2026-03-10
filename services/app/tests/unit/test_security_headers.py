"""Tests for security headers and CORS configuration."""

from unittest.mock import patch

import pytest

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "1; mode=block",
    "referrer-policy": "strict-origin-when-cross-origin",
}


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    async def test_health_endpoint_has_security_headers(self, async_client):
        """GET /health includes all 4 security headers."""
        response = await async_client.get("/health")
        assert response.status_code == 200

        for header, expected_value in SECURITY_HEADERS.items():
            assert response.headers.get(header) == expected_value, (
                f"Missing or wrong header: {header}"
            )

    async def test_404_has_security_headers(self, async_client):
        """404 responses include security headers."""
        response = await async_client.get("/api/nonexistent-route-12345")
        for header in SECURITY_HEADERS:
            assert header in response.headers, f"Missing header on 404: {header}"

    async def test_openapi_has_security_headers(self, async_client):
        """GET /openapi.json includes security headers."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        for header in SECURITY_HEADERS:
            assert header in response.headers, f"Missing header: {header}"

    async def test_hsts_present_when_cookie_secure(self, async_client):
        """HSTS header is present when cookie_secure is True."""
        with patch("app.main.settings.cookie_secure", True):
            response = await async_client.get("/health")
        assert response.status_code == 200
        hsts = response.headers.get("strict-transport-security")
        assert hsts is not None
        assert "max-age=63072000" in hsts
        assert "includeSubDomains" in hsts

    async def test_hsts_absent_when_cookie_not_secure(self, async_client):
        """HSTS header is absent when cookie_secure is False (dev)."""
        with patch("app.main.settings.cookie_secure", False):
            response = await async_client.get("/health")
        assert response.status_code == 200
        assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
class TestCORSConfig:
    """Verify CORS origins are loaded from config."""

    async def test_default_cors_origins(self, async_client):
        """Preflight request to allowed origin returns CORS headers."""
        response = await async_client.options(
            "/health",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    async def test_disallowed_origin_no_cors(self, async_client):
        """Preflight from disallowed origin does not return allow-origin."""
        response = await async_client.options(
            "/health",
            headers={
                "origin": "http://evil.com",
                "access-control-request-method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") != "http://evil.com"
