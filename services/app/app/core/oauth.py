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

# The state token is also mirrored into this cookie at redirect time and must
# come back with the callback. Redis alone only proves *we* minted the state,
# not that the browser now presenting it is the one that started the flow —
# without the cookie an attacker can begin a flow, complete consent as
# themselves, and lure the victim to the callback URL to be logged into the
# attacker's account (login CSRF).
#
# SameSite must stay "lax": the callback is a cross-site top-level navigation
# from the provider, which "strict" would not send the cookie on, breaking
# every sign-in. The path scopes it to the two OAuth endpoints that use it.
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_COOKIE_PATH = "/api/auth/oauth"


@dataclass
class OAuthUserInfo:
    """Normalized user info from an OAuth provider."""

    provider_user_id: str
    email: str
    name: str | None
    avatar_url: str | None
    # Whether the *provider* vouches for the email above, not whether we do.
    # Defaults to False so a provider branch that forgets to set it fails
    # closed rather than silently asserting a verified address.
    email_verified: bool = False


def generate_oauth_state() -> str:
    """Generate a cryptographically random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


def state_matches_cookie(callback_state: str, cookie_state: str | None) -> bool:
    """Check the callback's ``state`` against the cookie set at redirect time.

    Both values must be present and identical. Compared with
    ``compare_digest`` — the state is a secret for the length of one flow, and
    a timing oracle on it would let it be recovered a byte at a time.
    """
    if not callback_state or not cookie_state:
        return False
    return secrets.compare_digest(callback_state, cookie_state)


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
            # `email_verified` sits right next to `email` in the userinfo
            # response and is the only thing that makes the address mean
            # anything. A Google Workspace admin can set an arbitrary address
            # on a directory account, and the claim is how Google says whether
            # it checked. Read it explicitly rather than assuming true.
            return OAuthUserInfo(
                provider_user_id=str(data["sub"]),
                email=data.get("email", ""),
                name=data.get("name"),
                avatar_url=data.get("picture"),
                email_verified=bool(data.get("email_verified")),
            )

        # GitHub
        email, email_verified = await _resolve_github_email(client, data.get("email") or "")

        return OAuthUserInfo(
            provider_user_id=str(data["id"]),
            email=email,
            name=data.get("name") or data.get("login"),
            avatar_url=data.get("avatar_url"),
            email_verified=email_verified,
        )


async def _resolve_github_email(client: AsyncOAuth2Client, profile_email: str) -> tuple[str, bool]:
    """Resolve a GitHub identity's email and whether GitHub verified it.

    `/user`'s ``email`` field is the user's *public profile* email. GitHub does
    not require it to be verified and returns no flag beside it, so it cannot
    be trusted on its own — only ``/user/emails`` says which addresses were
    confirmed. The profile value is therefore looked up in that list rather
    than taken at face value, and the primary verified address is used when the
    profile one is absent from the list or listed as unverified — a user who
    publishes an unconfirmed address on their profile but has a confirmed one
    should sign in as the confirmed one, not be turned away.

    A failure to read ``/user/emails`` (the `user:email` scope withheld, say)
    yields ``verified=False`` rather than an exception: the caller refuses an
    unverified identity anyway, and a clean refusal beats a 500.

    Returns:
        (email, verified). ``verified`` is True only for an address GitHub
        itself lists as verified.
    """
    try:
        entries = await _fetch_github_emails(client)
    except Exception:
        logger.warning("github_emails_fetch_failed", exc_info=True)
        entries = []

    if profile_email:
        for entry in entries:
            if str(entry.get("email", "")).lower() == profile_email.lower():
                if entry.get("verified"):
                    return profile_email, True
                break

    # Prefer primary + verified
    for entry in entries:
        if entry.get("primary") and entry.get("verified"):
            return entry["email"], True
    # Fallback to any verified email
    for entry in entries:
        if entry.get("verified"):
            return entry["email"], True

    # Nothing verified. Hand back the profile address anyway so the caller can
    # tell "no email at all" apart from "an email GitHub will not vouch for".
    return profile_email, False


async def _fetch_github_emails(client: AsyncOAuth2Client) -> list[dict]:
    """Fetch the caller's addresses from GitHub /user/emails."""
    resp = await client.get("https://api.github.com/user/emails")
    resp.raise_for_status()
    emails = resp.json()
    return emails if isinstance(emails, list) else []


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
