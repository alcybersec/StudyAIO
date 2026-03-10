"""Smoke test to validate integration test infrastructure."""

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_health_returns_200(integration_client, db_session):
    """Health endpoint responds when wired to real database."""
    resp = await integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
