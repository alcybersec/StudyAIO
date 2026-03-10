"""Authentication API endpoints."""

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_schemas import (
    AuthConfigResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MagicLinkRequest,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    VerifyEmailRequest,
)
from app.api.deps import get_current_user
from app.config import settings
from app.core.auth import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.database import get_session
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.rate_limit import limiter
from app.core.security import generate_qr_code_base64, setup_totp, verify_totp
from app.models.user import User
from app.services import user_service

logger = structlog.get_logger()

router = APIRouter(prefix="/auth")

# Cookie settings
_COOKIE_SAMESITE = "lax"
_COOKIE_HTTPONLY = True


def _set_auth_cookies(response: Response, user: User) -> None:
    """Set HttpOnly access and refresh token cookies."""
    access_token = create_access_token(user.id, user.role, user.tier)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=_COOKIE_HTTPONLY,
        secure=settings.cookie_secure,
        samesite=_COOKIE_SAMESITE,
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=_COOKIE_HTTPONLY,
        secure=settings.cookie_secure,
        samesite=_COOKIE_SAMESITE,
        path="/",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")


@router.get("/config")
async def get_auth_config() -> AuthConfigResponse:
    """Return public auth configuration (no auth required)."""
    providers: list[str] = []
    if settings.google_client_id:
        providers.append("google")
    if settings.github_client_id:
        providers.append("github")

    return AuthConfigResponse(
        self_hosted=settings.self_hosted,
        registration_enabled=not settings.self_hosted,
        oauth_providers=providers,
        demo_enabled=settings.demo_enabled,
    )


@router.post("/register", status_code=201)
@limiter.limit(lambda: "3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserProfileResponse:
    """Register a new user account."""
    user = await user_service.register_user(
        session, body.email, body.username, body.password
    )
    await session.commit()
    _set_auth_cookies(response, user)
    return UserProfileResponse.model_validate(user)


@router.post("/login")
@limiter.limit(lambda: "5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserProfileResponse:
    """Authenticate with email and password."""
    user = await user_service.authenticate_user(session, body.email, body.password)

    # Check MFA if enabled
    if user.mfa_enabled:
        if not body.totp_code:
            raise AuthorizationError("MFA code required")
        if not user.mfa_secret or not verify_totp(user.mfa_secret, body.totp_code):
            raise AuthorizationError("Invalid MFA code")

    await session.commit()
    _set_auth_cookies(response, user)
    return UserProfileResponse.model_validate(user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Log out by clearing auth cookies."""
    _clear_auth_cookies(response)
    return {"detail": "Logged out"}


@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Rotate access and refresh tokens."""
    token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not token:
        raise AuthenticationError("No refresh token")

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    user = await user_service.get_user_by_id(session, user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    _set_auth_cookies(response, user)
    return {"detail": "Tokens refreshed"}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Get current user profile."""
    return UserProfileResponse.model_validate(user)


@router.put("/me")
async def update_me(
    body: UpdateProfileRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Update current user profile."""
    updated = await user_service.update_profile(
        session, user.id, username=body.username, avatar_url=body.avatar_url
    )
    await session.commit()
    return UserProfileResponse.model_validate(updated)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Change password for the current user."""
    await user_service.change_password(
        session, user.id, body.old_password, body.new_password
    )
    await session.commit()
    return {"detail": "Password changed"}


@router.post("/forgot-password", status_code=202)
@limiter.limit(lambda: "3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Request a password reset email. Always returns 202 (no email leak)."""
    await user_service.request_password_reset(session, body.email)
    await session.commit()
    return {"detail": "If an account exists with that email, a reset link has been sent"}


@router.post("/reset-password")
@limiter.limit(lambda: "3/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Reset password using a magic link token."""
    await user_service.reset_password_with_token(session, body.token, body.new_password)
    await session.commit()
    return {"detail": "Password reset successfully"}


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Verify email address using a magic link token."""
    await user_service.verify_email_token(session, body.token)
    await session.commit()
    return {"detail": "Email verified"}


@router.post("/mfa/setup")
async def mfa_setup(
    user: User = Depends(get_current_user),
) -> MFASetupResponse:
    """Generate a TOTP secret and QR code for MFA setup."""
    secret, uri = setup_totp(user.email)
    qr_b64 = generate_qr_code_base64(uri)
    return MFASetupResponse(
        secret=secret,
        qr_code_base64=qr_b64,
        provisioning_uri=uri,
    )


@router.post("/mfa/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Verify TOTP code and enable MFA. Returns backup codes."""
    backup_codes = await user_service.enable_mfa(
        session, user.id, body.totp_code, body.secret
    )
    await session.commit()
    return {"detail": "MFA enabled", "backup_codes": backup_codes}


@router.post("/mfa/disable")
async def mfa_disable(
    body: MFADisableRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Disable MFA for the current user."""
    await user_service.disable_mfa(session, user.id, body.totp_code)
    await session.commit()
    return {"detail": "MFA disabled"}


@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str) -> dict[str, str]:
    """Redirect to OAuth provider (placeholder — full implementation in M21)."""
    return {"detail": f"OAuth redirect for {provider} not yet implemented"}


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Handle OAuth callback (placeholder — full implementation in M21)."""
    return {"detail": f"OAuth callback for {provider} not yet implemented"}


@router.post("/magic-link", status_code=202)
@limiter.limit(lambda: "5/minute")
async def request_magic_link(
    request: Request,
    body: MagicLinkRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Request a magic link for passwordless login. Always returns 202."""
    # Reuse password reset flow for now — magic link sending deferred to M21
    await user_service.request_password_reset(session, body.email)
    await session.commit()
    return {"detail": "If an account exists with that email, a magic link has been sent"}


DEMO_USER_ID = "00000000-0000-0000-0000-000000000002"


@router.get("/demo-login")
@limiter.limit(lambda: "10/minute")
async def demo_login(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Auto-authenticate as the demo user and redirect to dashboard.

    Returns 404 if demo mode is disabled or the demo user doesn't exist.
    """
    if not settings.demo_enabled:
        return JSONResponse(status_code=404, content={"detail": "Demo mode is not enabled"})

    user = await user_service.get_user_by_id(session, DEMO_USER_ID)
    if not user:
        return JSONResponse(status_code=404, content={"detail": "Demo user not found"})

    redirect = RedirectResponse(url="/", status_code=302)
    _set_auth_cookies(redirect, user)
    logger.info("demo_login", user_id=DEMO_USER_ID)
    return redirect


@router.get("/magic/{token}")
async def magic_link_login(
    token: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Login via magic link token (placeholder — full implementation in M21)."""
    return {"detail": "Magic link login not yet fully implemented"}
