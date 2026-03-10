"""Tests for application startup safety checks."""

from unittest.mock import patch

import pytest


class TestJWTSecretStartupCheck:
    """Verify the app refuses to start with default JWT secret in SaaS mode."""

    def test_default_secret_in_saas_mode_raises(self):
        """App should raise RuntimeError when using default JWT secret with self_hosted=False."""
        from app.main import _DEFAULT_JWT_SECRET

        with (
            patch("app.main.settings.self_hosted", False),
            patch("app.main.settings.jwt_secret_key") as mock_secret,
        ):
            mock_secret.get_secret_value.return_value = _DEFAULT_JWT_SECRET

            # Import and call the lifespan manually
            from app.main import lifespan, app

            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is set to the default"):
                import asyncio

                async def _run():
                    async with lifespan(app):
                        pass

                asyncio.run(_run())

    def test_custom_secret_in_saas_mode_starts(self):
        """App should start fine with a custom JWT secret in SaaS mode."""
        with (
            patch("app.main.settings.self_hosted", False),
            patch("app.main.settings.jwt_secret_key") as mock_secret,
            patch("app.main.configure_logging"),
        ):
            mock_secret.get_secret_value.return_value = "a-real-production-secret-key-12345"

            from app.main import lifespan, app

            import asyncio

            async def _run():
                async with lifespan(app):
                    pass

            # Should not raise
            asyncio.run(_run())

    def test_default_secret_in_selfhosted_mode_starts(self):
        """App should start fine with default JWT secret in self-hosted mode."""
        with (
            patch("app.main.settings.self_hosted", True),
            patch("app.main.configure_logging"),
        ):
            from app.main import lifespan, app

            import asyncio

            async def _run():
                async with lifespan(app):
                    pass

            # Should not raise — self-hosted allows default secret
            asyncio.run(_run())
