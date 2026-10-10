"""SEC-05 (GL#25): authentication is on by default; "no login" is an explicit opt-in."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.core.exceptions import AuthenticationError


class TestDefaults:
    def test_default_config_is_not_self_hosted_and_not_single_user(self, monkeypatch):
        for name in ("SELF_HOSTED", "SINGLE_USER_MODE", "I_UNDERSTAND_NO_AUTH"):
            monkeypatch.delenv(name, raising=False)
        s = Settings(_env_file=None)
        assert s.self_hosted is False
        assert s.single_user_mode is False
        assert s.i_understand_no_auth is False

    def test_single_user_mode_implies_self_hosted(self):
        assert Settings(_env_file=None, single_user_mode=True).self_hosted is True


@pytest.mark.asyncio
class TestDependency:
    async def test_self_hosted_alone_unauthenticated_is_rejected(self, mock_session):
        from app.api.deps import get_current_user_or_default

        request = MagicMock()
        request.cookies = {}
        with patch("app.api.deps.settings") as s:
            s.self_hosted = True  # self-hosted alone must NOT grant the default admin
            s.single_user_mode = False
            with pytest.raises(AuthenticationError):
                await get_current_user_or_default(request, mock_session)

    async def test_single_user_mode_unauthenticated_gets_default_admin(self, mock_session):
        import app.api.deps as deps

        deps._default_user_cache = None
        admin = MagicMock()
        admin.id = deps.DEFAULT_ADMIN_ID
        result = MagicMock()
        result.scalar_one_or_none.return_value = admin
        mock_session.execute = AsyncMock(return_value=result)
        request = MagicMock()
        request.cookies = {}
        with patch("app.api.deps.settings") as s:
            s.single_user_mode = True
            s.self_hosted = True
            user = await deps.get_current_user_or_default(request, mock_session)
        assert user.id == deps.DEFAULT_ADMIN_ID
        deps._default_user_cache = None


class TestStartupGuard:
    def _check(self, **kw):
        from app.main import check_single_user_mode

        with patch("app.main.settings") as s:
            s.single_user_mode = kw.get("single_user_mode", True)
            s.bind_host = kw.get("bind_host", "0.0.0.0")
            s.i_understand_no_auth = kw.get("ack", False)
            check_single_user_mode()

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    def test_loopback_is_allowed(self, host):
        self._check(bind_host=host)

    @pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", ""])
    def test_non_loopback_refused_without_ack(self, host):
        with pytest.raises(RuntimeError, match="I_UNDERSTAND_NO_AUTH"):
            self._check(bind_host=host)

    def test_non_loopback_allowed_with_ack(self):
        self._check(bind_host="0.0.0.0", ack=True)

    def test_off_is_a_noop(self):
        self._check(single_user_mode=False, bind_host="0.0.0.0")


@pytest.mark.asyncio
class TestAuthConfigAdvertisesRegistration:
    async def _cfg(self, single_user: bool):
        from app.api.auth import get_auth_config

        with patch("app.api.auth.settings") as s:
            s.google_client_id = s.github_client_id = ""
            s.registration_mode = "open"
            s.self_hosted = True
            s.single_user_mode = single_user
            s.demo_enabled = False
            return await get_auth_config()

    async def test_self_hosted_multi_user_allows_registration(self):
        assert (await self._cfg(False)).registration_enabled is True

    async def test_single_user_mode_hides_registration(self):
        assert (await self._cfg(True)).registration_enabled is False


@pytest.mark.asyncio
async def test_startup_actually_runs_the_guard():
    """The guard must be wired into the lifespan, not merely defined."""
    from app.main import app, lifespan

    with (
        patch("app.main.check_single_user_mode") as check,
        patch("app.main.warn_if_embedding_provider_unavailable"),
        patch("app.main.configure_logging"),
        patch("app.main.settings.self_hosted", True),
    ):
        async with lifespan(app):
            pass
    check.assert_called_once()
