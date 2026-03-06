"""Tests for Prometheus metrics endpoint."""

from unittest.mock import patch


class TestMetricsEndpoint:
    """Tests for /metrics availability based on config."""

    async def test_metrics_disabled_by_default(self, async_client):
        """When prometheus_enabled=False, /metrics returns 404."""
        response = await async_client.get("/metrics")
        # By default prometheus is disabled, so no /metrics route exists
        assert response.status_code in (404, 405)

    @patch("app.config.settings")
    async def test_metrics_config_default_false(self, mock_settings):
        """Default config has prometheus_enabled=False."""
        from app.config import Settings

        s = Settings()
        assert s.prometheus_enabled is False
