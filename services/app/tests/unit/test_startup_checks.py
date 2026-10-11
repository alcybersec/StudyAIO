"""Tests for application startup safety checks."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr


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
            patch("app.main.settings.single_user_mode", False),
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
            patch("app.main.settings.single_user_mode", False),
            patch(
                "app.main.settings.settings_encryption_key",
                SecretStr(Fernet.generate_key().decode()),
            ),
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

    def test_default_secret_in_selfhosted_multi_user_mode_raises(self):
        """SEC-05: SELF_HOSTED has logins, so the committed key must be refused."""
        from app.main import _DEFAULT_JWT_SECRET

        with (
            patch("app.main.settings.self_hosted", True),
            patch("app.main.settings.single_user_mode", False),
            patch("app.main.settings.jwt_secret_key") as mock_secret,
            _no_embedding_probe(),
        ):
            mock_secret.get_secret_value.return_value = _DEFAULT_JWT_SECRET
            import asyncio

            from app.main import app, lifespan

            async def _run():
                async with lifespan(app):
                    pass

            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is set to the default"):
                asyncio.run(_run())

    def test_default_secret_in_single_user_mode_starts(self):
        """No login in single-user mode, so no token is signed and the default is inert."""
        with (
            patch("app.main.settings.self_hosted", True),
            patch("app.main.settings.single_user_mode", True),
            patch("app.main.check_single_user_mode"),
            patch("app.main.configure_logging"),
            _no_embedding_probe(),
        ):
            import asyncio

            from app.main import app, lifespan

            async def _run():
                async with lifespan(app):
                    pass

            # Should not raise — single-user mode signs no tokens
            asyncio.run(_run())
