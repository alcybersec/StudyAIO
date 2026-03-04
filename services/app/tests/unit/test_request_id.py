"""Tests for request ID middleware."""

import pytest


@pytest.mark.asyncio
class TestRequestIDMiddleware:
    """Verify X-Request-ID is set on all responses."""

    async def test_response_has_request_id(self, async_client):
        """Every response should include an X-Request-ID header."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        # Should be a valid UUID4 format (36 chars with hyphens)
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36

    async def test_provided_request_id_echoed(self, async_client):
        """If client sends X-Request-ID, it should be echoed back."""
        custom_id = "my-custom-request-id-12345"
        response = await async_client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id

    async def test_missing_header_generates_uuid(self, async_client):
        """Without X-Request-ID header, a UUID4 should be generated."""
        response = await async_client.get("/health")
        request_id = response.headers["x-request-id"]
        # UUID4 format: 8-4-4-4-12 hex characters
        parts = request_id.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    async def test_request_id_on_error_responses(self, async_client):
        """X-Request-ID should be present even on error responses."""
        response = await async_client.get("/api/nonexistent-12345")
        assert "x-request-id" in response.headers
