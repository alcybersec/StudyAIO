"""Tests for core OAuth helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.oauth import (
    VALID_PROVIDERS,
    build_authorize_url,
    build_callback_url,
    fetch_userinfo,
    generate_oauth_state,
    get_provider_config,
    state_matches_cookie,
    store_oauth_state,
    validate_oauth_state,
)

# Not a credential: `fetch_userinfo` only carries the token through to a mocked
# client, so a placeholder keeps a file of OAuth-shaped fixtures from tripping
# secret scanners.
PLACEHOLDER_TOKEN = "<test-placeholder>"


def _mock_client(*responses):
    """An AsyncOAuth2Client stand-in returning `responses` in order."""
    mocks = []
    for payload in responses:
        resp = MagicMock()
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        mocks.append(resp)

    client = AsyncMock()
    client.get = AsyncMock(side_effect=mocks)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestGenerateOAuthState:
    def test_returns_string(self):
        state = generate_oauth_state()
        assert isinstance(state, str)
        assert len(state) > 20

    def test_returns_unique_values(self):
        states = {generate_oauth_state() for _ in range(10)}
        assert len(states) == 10


class TestGetProviderConfig:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            get_provider_config("twitter")

    def test_google_not_configured_raises(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.google_client_id = ""
            with pytest.raises(ValueError, match="not configured"):
                get_provider_config("google")

    def test_github_not_configured_raises(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.github_client_id = ""
            with pytest.raises(ValueError, match="not configured"):
                get_provider_config("github")

    def test_google_returns_config(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.google_client_id = "goog-id"
            secret = MagicMock()
            secret.get_secret_value.return_value = "goog-secret"
            mock_settings.google_client_secret = secret

            config = get_provider_config("google")
            assert config["client_id"] == "goog-id"
            assert config["client_secret"] == "goog-secret"
            assert "accounts.google.com" in config["authorize_url"]

    def test_github_returns_config(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.github_client_id = "gh-id"
            secret = MagicMock()
            secret.get_secret_value.return_value = "gh-secret"
            mock_settings.github_client_secret = secret

            config = get_provider_config("github")
            assert config["client_id"] == "gh-id"
            assert config["client_secret"] == "gh-secret"
            assert "github.com" in config["authorize_url"]


class TestBuildCallbackUrl:
    def test_uses_redirect_base(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.oauth_redirect_base_url = "https://app.example.com"
            url = build_callback_url("google")
        assert url == "https://app.example.com/api/auth/oauth/google/callback"

    def test_default_localhost(self):
        with patch("app.core.oauth.settings") as mock_settings:
            mock_settings.oauth_redirect_base_url = ""
            url = build_callback_url("github")
        assert url == "http://localhost:8000/api/auth/oauth/github/callback"


class TestBuildAuthorizeUrl:
    def test_google_url_includes_required_params(self):
        with patch("app.core.oauth.get_provider_config") as mock_config:
            mock_config.return_value = {
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "client_id": "goog-id",
                "scope": "openid email profile",
            }
            with patch(
                "app.core.oauth.build_callback_url",
                return_value="https://app.example.com/api/auth/oauth/google/callback",
            ):
                url = build_authorize_url("google", "test-state")

        assert "client_id=goog-id" in url
        assert "state=test-state" in url
        assert "response_type=code" in url
        assert "redirect_uri=" in url
        assert "prompt=select_account" in url

    def test_github_url_does_not_include_prompt(self):
        with patch("app.core.oauth.get_provider_config") as mock_config:
            mock_config.return_value = {
                "authorize_url": "https://github.com/login/oauth/authorize",
                "client_id": "gh-id",
                "scope": "read:user user:email",
            }
            with patch(
                "app.core.oauth.build_callback_url",
                return_value="https://app.example.com/api/auth/oauth/github/callback",
            ):
                url = build_authorize_url("github", "test-state")

        assert "client_id=gh-id" in url
        assert "prompt" not in url


class TestStateMatchesCookie:
    """#70: the state has to belong to *this* browser, not just to us.

    Redis proves we minted the state. Only the cookie set alongside it proves
    the browser presenting it at the callback is the one that started the flow
    -- without which an attacker completes consent as themselves and lures the
    victim to the callback URL to be signed into the attacker's account.
    """

    def test_matching_pair_passes(self):
        assert state_matches_cookie("abc123", "abc123") is True

    def test_mismatch_fails(self):
        assert state_matches_cookie("abc123", "different") is False

    def test_absent_cookie_fails(self):
        """The whole attack: a state we really minted, in a browser we never
        gave a cookie to."""
        assert state_matches_cookie("abc123", None) is False
        assert state_matches_cookie("abc123", "") is False

    def test_absent_state_fails(self):
        assert state_matches_cookie("", "abc123") is False

    def test_empty_pair_does_not_pass_as_equal(self):
        assert state_matches_cookie("", "") is False


class TestValidProviders:
    def test_contains_google_and_github(self):
        assert "google" in VALID_PROVIDERS
        assert "github" in VALID_PROVIDERS

    def test_does_not_contain_others(self):
        assert "twitter" not in VALID_PROVIDERS
        assert "facebook" not in VALID_PROVIDERS


class TestOAuthStateRedis:
    @pytest.mark.asyncio
    async def test_store_and_validate_state(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="google")
        mock_redis.setex = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("app.core.oauth.Redis") as MockRedis:
            MockRedis.from_url.return_value = mock_redis

            await store_oauth_state("test-state", "google")
            mock_redis.setex.assert_called_once()

            result = await validate_oauth_state("test-state", "google")
            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_wrong_provider(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="google")
        mock_redis.aclose = AsyncMock()

        with patch("app.core.oauth.Redis") as MockRedis:
            MockRedis.from_url.return_value = mock_redis

            result = await validate_oauth_state("test-state", "github")
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_missing_state(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch("app.core.oauth.Redis") as MockRedis:
            MockRedis.from_url.return_value = mock_redis

            result = await validate_oauth_state("nonexistent", "google")
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_redis_error_returns_false(self):
        with patch("app.core.oauth.Redis") as MockRedis:
            MockRedis.from_url.side_effect = Exception("Redis down")

            result = await validate_oauth_state("test-state", "google")
            assert result is False


class TestFetchUserInfo:
    @pytest.mark.asyncio
    async def test_google_userinfo(self):
        google_data = {
            "sub": "google-uid-123",
            "email": "user@gmail.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
        }
        mock_response = MagicMock()
        mock_response.json.return_value = google_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.core.oauth.get_provider_config",
                return_value={
                    "client_id": "id",
                    "client_secret": "sec",
                    "userinfo_url": "https://googleapis.com/userinfo",
                },
            ),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("google", {"access_token": "tok"})

        assert info.provider_user_id == "google-uid-123"
        assert info.email == "user@gmail.com"
        assert info.name == "Test User"
        assert "googleusercontent.com" in info.avatar_url
        assert info.email_verified is True

    @pytest.mark.asyncio
    async def test_github_userinfo_with_email(self):
        """The profile email is used, but only once /user/emails confirms it."""
        github_data = {
            "id": 42,
            "email": "dev@github.com",
            "name": "Dev User",
            "login": "devuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/42",
        }
        github_emails = [{"email": "dev@github.com", "primary": True, "verified": True}]

        mock_client = _mock_client(github_data, github_emails)

        with (
            patch(
                "app.core.oauth.get_provider_config",
                return_value={
                    "client_id": "id",
                    "client_secret": "sec",
                    "userinfo_url": "https://api.github.com/user",
                },
            ),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("github", {"access_token": PLACEHOLDER_TOKEN})

        assert info.provider_user_id == "42"
        assert info.email == "dev@github.com"
        assert info.name == "Dev User"
        assert info.email_verified is True

    @pytest.mark.asyncio
    async def test_github_userinfo_fallback_to_emails_endpoint(self):
        github_profile = {
            "id": 99,
            "email": None,
            "name": None,
            "login": "ghostuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/99",
        }
        github_emails = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        mock_profile_resp = MagicMock()
        mock_profile_resp.json.return_value = github_profile
        mock_profile_resp.raise_for_status = MagicMock()

        mock_emails_resp = MagicMock()
        mock_emails_resp.json.return_value = github_emails
        mock_emails_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_profile_resp, mock_emails_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.core.oauth.get_provider_config",
                return_value={
                    "client_id": "id",
                    "client_secret": "sec",
                    "userinfo_url": "https://api.github.com/user",
                },
            ),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("github", {"access_token": PLACEHOLDER_TOKEN})

        assert info.email == "primary@example.com"
        assert info.name == "ghostuser"  # Falls back to login
        assert info.email_verified is True


class TestProviderEmailVerification:
    """#70: `fetch_userinfo` has to report whether the *provider* checked.

    The address is what decides which account an identity lands in, so a
    provider that will not vouch for it must not be reported as if it had.
    """

    _GITHUB_CONFIG = {
        "client_id": "id",
        "client_secret": "sec",
        "userinfo_url": "https://api.github.com/user",
    }
    _GOOGLE_CONFIG = {
        "client_id": "id",
        "client_secret": "sec",
        "userinfo_url": "https://googleapis.com/userinfo",
    }

    async def _fetch(self, provider, config, *responses):
        client = _mock_client(*responses)
        with (
            patch("app.core.oauth.get_provider_config", return_value=config),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=client),
        ):
            return await fetch_userinfo(provider, {"access_token": PLACEHOLDER_TOKEN})

    @pytest.mark.asyncio
    async def test_google_email_verified_false_is_reported(self):
        info = await self._fetch(
            "google",
            self._GOOGLE_CONFIG,
            {"sub": "g-1", "email": "spoofed@example.com", "email_verified": False},
        )
        assert info.email == "spoofed@example.com"
        assert info.email_verified is False

    @pytest.mark.asyncio
    async def test_google_missing_claim_is_unverified(self):
        """Absent is not the same as true. Fail closed."""
        info = await self._fetch(
            "google",
            self._GOOGLE_CONFIG,
            {"sub": "g-2", "email": "nobody@example.com"},
        )
        assert info.email_verified is False

    @pytest.mark.asyncio
    async def test_github_unverified_profile_email_is_reported(self):
        """`/user` carries no verification flag; `/user/emails` is the source.

        A GitHub profile email need not be verified, and the old code took it
        straight from `/user` as if it were.
        """
        info = await self._fetch(
            "github",
            self._GITHUB_CONFIG,
            {"id": 7, "email": "unverified@example.com", "login": "someone"},
            [{"email": "unverified@example.com", "primary": True, "verified": False}],
        )
        assert info.email == "unverified@example.com"
        assert info.email_verified is False

    @pytest.mark.asyncio
    async def test_github_falls_through_to_a_verified_address(self):
        """An unverified profile email must not cost a user their sign-in.

        They have a confirmed address; use that one rather than reporting the
        unconfirmed one and having the caller turn them away.
        """
        info = await self._fetch(
            "github",
            self._GITHUB_CONFIG,
            {"id": 11, "email": "public@example.com", "login": "someone"},
            [
                {"email": "public@example.com", "primary": False, "verified": False},
                {"email": "real@example.com", "primary": True, "verified": True},
            ],
        )
        assert info.email == "real@example.com"
        assert info.email_verified is True

    @pytest.mark.asyncio
    async def test_github_profile_email_absent_from_the_list_is_unverified(self):
        """An address GitHub does not list at all cannot have been checked."""
        info = await self._fetch(
            "github",
            self._GITHUB_CONFIG,
            {"id": 8, "email": "typed-in@example.com", "login": "someone"},
            [],
        )
        assert info.email == "typed-in@example.com"
        assert info.email_verified is False

    @pytest.mark.asyncio
    async def test_github_emails_endpoint_failure_is_unverified_not_a_crash(self):
        """Scope withheld, rate limit, outage -- refuse cleanly, do not 500."""
        profile = MagicMock()
        profile.json.return_value = {"id": 9, "email": "dev@example.com", "login": "someone"}
        profile.raise_for_status = MagicMock()

        client = AsyncMock()
        client.get = AsyncMock(side_effect=[profile, RuntimeError("403 from /user/emails")])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.oauth.get_provider_config", return_value=self._GITHUB_CONFIG),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=client),
        ):
            info = await fetch_userinfo("github", {"access_token": PLACEHOLDER_TOKEN})

        assert info.email == "dev@example.com"
        assert info.email_verified is False
