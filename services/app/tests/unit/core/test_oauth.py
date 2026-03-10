"""Tests for core OAuth helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.oauth import (
    VALID_PROVIDERS,
    OAuthUserInfo,
    build_authorize_url,
    build_callback_url,
    fetch_userinfo,
    generate_oauth_state,
    get_provider_config,
    store_oauth_state,
    validate_oauth_state,
)


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
            with patch("app.core.oauth.build_callback_url", return_value="https://app.example.com/api/auth/oauth/google/callback"):
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
            with patch("app.core.oauth.build_callback_url", return_value="https://app.example.com/api/auth/oauth/github/callback"):
                url = build_authorize_url("github", "test-state")

        assert "client_id=gh-id" in url
        assert "prompt" not in url


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
            patch("app.core.oauth.get_provider_config", return_value={
                "client_id": "id", "client_secret": "sec",
                "userinfo_url": "https://googleapis.com/userinfo",
            }),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("google", {"access_token": "tok"})

        assert info.provider_user_id == "google-uid-123"
        assert info.email == "user@gmail.com"
        assert info.name == "Test User"
        assert "googleusercontent.com" in info.avatar_url

    @pytest.mark.asyncio
    async def test_github_userinfo_with_email(self):
        github_data = {
            "id": 42,
            "email": "dev@github.com",
            "name": "Dev User",
            "login": "devuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/42",
        }
        mock_response = MagicMock()
        mock_response.json.return_value = github_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.oauth.get_provider_config", return_value={
                "client_id": "id", "client_secret": "sec",
                "userinfo_url": "https://api.github.com/user",
            }),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("github", {"access_token": "tok"})

        assert info.provider_user_id == "42"
        assert info.email == "dev@github.com"
        assert info.name == "Dev User"

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
            patch("app.core.oauth.get_provider_config", return_value={
                "client_id": "id", "client_secret": "sec",
                "userinfo_url": "https://api.github.com/user",
            }),
            patch("app.core.oauth.AsyncOAuth2Client", return_value=mock_client),
        ):
            info = await fetch_userinfo("github", {"access_token": "tok"})

        assert info.email == "primary@example.com"
        assert info.name == "ghostuser"  # Falls back to login
