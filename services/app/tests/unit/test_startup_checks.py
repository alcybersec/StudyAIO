"""Tests for application startup safety checks."""

from unittest.mock import patch

import pytest


def _no_embedding_probe():
    """Stub the embedding startup check out of the lifespan.

    It loads the sentence-transformers model for real (issue #44), which in a
    unit test means importing torch and downloading ~90MB from Hugging Face.
    These tests are about the JWT secret; `test_embedding_startup_check.py`
    covers the probe itself, including that it is wired into this lifespan.
    """
    return patch("app.main.warn_if_embedding_provider_unavailable")


class TestJWTSecretStartupCheck:
    """Verify the app refuses to start with default JWT secret in SaaS mode."""

    def test_default_secret_in_saas_mode_raises(self):
        """App should raise RuntimeError when using default JWT secret with self_hosted=False."""
        from app.main import _DEFAULT_JWT_SECRET

        with (
            patch("app.main.settings.self_hosted", False),
            patch("app.main.settings.jwt_secret_key") as mock_secret,
            _no_embedding_probe(),
        ):
            mock_secret.get_secret_value.return_value = _DEFAULT_JWT_SECRET

            # Import and call the lifespan manually
            from app.main import app, lifespan

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
            _no_embedding_probe(),
        ):
            mock_secret.get_secret_value.return_value = "a-real-production-secret-key-12345"

            import asyncio

            from app.main import app, lifespan

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
            _no_embedding_probe(),
        ):
            import asyncio

            from app.main import app, lifespan

            async def _run():
                async with lifespan(app):
                    pass

            # Should not raise — self-hosted allows default secret
            asyncio.run(_run())
