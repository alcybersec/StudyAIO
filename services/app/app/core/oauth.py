"""OAuth client helpers for Google and GitHub providers."""

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import structlog
from authlib.integrations.httpx_client import AsyncOAuth2Client
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger()

# Provider configurations
OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "access_token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "access_token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
}

VALID_PROVIDERS = frozenset({"google", "github"})
STATE_TTL_SECONDS = 600  # 10 minutes
STATE_KEY_PREFIX = "oauth:state:"


@dataclass
class OAuthUserInfo:
    """Normalized user info from an OAuth provider."""

    provider_user_id: str
    email: str
    name: str | None
    avatar_url: str | None


def generate_oauth_state() -> str:
    """Generate a cryptographically random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


def get_provider_config(provider: str) -> dict[str, str]:
    """Get OAuth provider configuration including client credentials.

    Args:
        provider: Provider name ("google" or "github").

    Returns:
        Dict with authorize_url, access_token_url, userinfo_url, scope,
        client_id, and client_secret.

    Raises:
        ValueError: If provider is unknown or not configured.
    """
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unknown OAuth provider: {provider}")

    base = OAUTH_PROVIDERS[provider]

    if provider == "google":
        if not settings.google_client_id:
            raise ValueError("Google OAuth not configured")
        return {
            **base,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
        }

    # github
    if not settings.github_client_id:
        raise ValueError("GitHub OAuth not configured")
    return {
        **base,
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret.get_secret_value(),
    }


def build_callback_url(provider: str) -> str:
    """Build the OAuth callback URL for a provider."""
    base = settings.oauth_redirect_base_url or "http://localhost:8000"
    return f"{base}/api/auth/oauth/{provider}/callback"


def build_authorize_url(provider: str, state: str) -> str:
    """Build the full authorization redirect URL for a provider.

    Args:
        provider: Provider name.
        state: Random state token for CSRF protection.

    Returns:
        Full authorization URL to redirect the user to.
    """
    config = get_provider_config(provider)
    callback_url = build_callback_url(provider)

    params: dict[str, str] = {
        "client_id": config["client_id"],
        "redirect_uri": callback_url,
        "state": state,
        "response_type": "code",
        "scope": config["scope"],
    }

    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "select_account"

    return f"{config['authorize_url']}?{urlencode(params)}"


async def exchange_code_for_token(provider: str, code: str) -> dict:
    """Exchange an authorization code for an access token.

    Args:
        provider: Provider name.
        code: Authorization code from the callback.

    Returns:
        Token dict containing at least access_token and token_type.

    Raises:
        OAuthError: If the token exchange fails.
    """
    config = get_provider_config(provider)
    callback_url = build_callback_url(provider)

    headers = {"Accept": "application/json"}

    async with AsyncOAuth2Client(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token_endpoint_auth_method="client_secret_post",
    ) as client:
        token = await client.fetch_token(
            config["access_token_url"],
            code=code,
            redirect_uri=callback_url,
            headers=headers,
        )

    logger.info("oauth_token_exchanged", provider=provider)
    return dict(token)


async def fetch_userinfo(provider: str, token: dict) -> OAuthUserInfo:
    """Fetch and normalize user info from an OAuth provider.

    Args:
        provider: Provider name.
        token: Access token dict from exchange_code_for_token.

    Returns:
        Normalized OAuthUserInfo.

    Raises:
        httpx.HTTPStatusError: If the userinfo request fails.
        ValueError: If no email can be determined.
    """
    config = get_provider_config(provider)

    async with AsyncOAuth2Client(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token=token,
    ) as client:
        resp = await client.get(
            config["userinfo_url"],
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        if provider == "google":
            return OAuthUserInfo(
                provider_user_id=str(data["sub"]),
                email=data.get("email", ""),
                name=data.get("name"),
                avatar_url=data.get("picture"),
            )

        # GitHub
        email = data.get("email") or ""
        if not email:
            email = await _fetch_github_primary_email(client)

        return OAuthUserInfo(
            provider_user_id=str(data["id"]),
            email=email,
            name=data.get("name") or data.get("login"),
            avatar_url=data.get("avatar_url"),
        )


async def _fetch_github_primary_email(client: AsyncOAuth2Client) -> str:
    """Fetch the primary verified email from GitHub /user/emails endpoint."""
    resp = await client.get("https://api.github.com/user/emails")
    resp.raise_for_status()
    emails = resp.json()

    # Prefer primary + verified
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry["email"]
    # Fallback to any verified email
    for entry in emails:
        if entry.get("verified"):
            return entry["email"]
    return ""


# ── Redis state storage ─────────────────────────────────────────────


async def store_oauth_state(state: str, provider: str) -> None:
    """Store an OAuth state token in Redis with a 10-minute TTL."""
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            await redis.setex(
                f"{STATE_KEY_PREFIX}{state}",
                STATE_TTL_SECONDS,
                provider,
            )
        finally:
            await redis.aclose()
    except Exception:
        logger.warning("oauth_state_store_failed", exc_info=True)
        raise


async def validate_oauth_state(state: str, provider: str) -> bool:
    """Validate and consume an OAuth state token from Redis.

    Returns True if the state is valid for the given provider, False otherwise.
    The state is deleted after validation (one-time use).
    """
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            stored = await redis.get(f"{STATE_KEY_PREFIX}{state}")
            if stored == provider:
                await redis.delete(f"{STATE_KEY_PREFIX}{state}")
                return True
            return False
        finally:
            await redis.aclose()
    except Exception:
        logger.warning("oauth_state_validate_failed", exc_info=True)
        return False
