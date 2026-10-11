"""Floor 2: the committed default JWT signing key is never live while login is on.

M32-S4-SAFETY-027, review of SEC-05 (33c7d1d, GL#25). ``JWT_SECRET_KEY`` defaults
to a value committed in ``app/config.py`` and ``.env.example``. Anyone who reads
the repository can sign a token with it, so an instance that authenticates with
it has no authentication.

Before SEC-05 the startup refusal was skipped under ``SELF_HOSTED=true``, which
was harmless because self-hosted mode let every anonymous caller in as the
default admin anyway. SEC-05 made ``SELF_HOSTED`` an authenticated mode, so the
same skip now leaves a multi-user, logged-in deployment signing sessions with a
public key. Only ``SINGLE_USER_MODE`` (where an anonymous caller already *is*
the admin, and startup refuses a non-loopback bind without
``I_UNDERSTAND_NO_AUTH``) gains nothing from forging a token.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


def _start(*, self_hosted: bool, single_user_mode: bool, secret: str) -> None:
    from app.main import app, lifespan

    with (
        patch("app.main.settings.self_hosted", self_hosted),
        patch("app.main.settings.single_user_mode", single_user_mode),
        patch("app.main.settings.bind_host", "127.0.0.1"),
        patch("app.main.settings.jwt_secret_key") as mock_secret,
        patch("app.main.configure_logging"),
        patch("app.main.warn_if_embedding_provider_unavailable"),
    ):
        mock_secret.get_secret_value.return_value = secret

        async def _run() -> None:
            async with lifespan(app):
                pass

        asyncio.run(_run())


@pytest.mark.parametrize("self_hosted", [False, True], ids=["saas", "self_hosted"])
def test_floor2_default_jwt_secret_refused_whenever_login_is_on(self_hosted):
    """Startup refuses the committed key in every authenticated mode.

    The ``self_hosted`` case was held by the SAFETY-027 veto of SEC-05 until
    8356b15 keyed the refusal on ``settings.single_user_mode`` (SAFETY-028).
    """
    from app.main import _DEFAULT_JWT_SECRET

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _start(self_hosted=self_hosted, single_user_mode=False, secret=_DEFAULT_JWT_SECRET)


def test_floor2_jwt_secret_check_controls():
    """Controls: a real key starts; single-user mode on loopback starts on the default."""
    from app.main import _DEFAULT_JWT_SECRET

    _start(self_hosted=True, single_user_mode=False, secret="a-real-unique-signing-key-0123456789")
    _start(self_hosted=True, single_user_mode=True, secret=_DEFAULT_JWT_SECRET)
