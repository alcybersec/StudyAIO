"""Tests for GET /api/auth/config endpoint."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_auth_config_returns_defaults(async_client):
    """Config endpoint returns self_hosted=True by default."""
    resp = await async_client.get("/api/auth/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["self_hosted"] is True
    assert data["registration_enabled"] is False
    assert data["oauth_providers"] == []


@pytest.mark.asyncio
async def test_auth_config_detects_oauth_providers(async_client):
    """Config endpoint lists configured OAuth providers."""
    with patch("app.api.auth.settings") as mock_settings:
        mock_settings.self_hosted = False
        mock_settings.google_client_id = "google-id-123"
        mock_settings.github_client_id = "github-id-456"
        # Patching `settings` wholesale means every attribute the endpoint
        # reads must be set — a MagicMock fails the response model.
        mock_settings.registration_mode = "open"
        mock_settings.demo_enabled = False
        resp = await async_client.get("/api/auth/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["self_hosted"] is False
    assert data["registration_enabled"] is True
    assert "google" in data["oauth_providers"]
    assert "github" in data["oauth_providers"]


@pytest.mark.asyncio
async def test_auth_config_no_auth_required(async_client):
    """Config endpoint does not require authentication."""
    # No cookies set — should still return 200
    resp = await async_client.get("/api/auth/config")
    assert resp.status_code == 200
