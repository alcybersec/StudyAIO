"""Authentication API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    is_token_invalidated,
)
from app.core.database import get_session
from app.core.exceptions import AuthenticationError, AuthorizationError, SessionRevokedError
from app.core.oauth import (
    VALID_PROVIDERS,
    build_authorize_url,
    exchange_code_for_token,
    fetch_userinfo,
    generate_oauth_state,
    store_oauth_state,
    validate_oauth_state,
)
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
    user = await user_service.register_user(session, body.email, body.username, body.password)
    minted = await user_service.create_email_verification_link(session, user)
    await session.commit()
    _set_auth_cookies(response, user)

    # Deliver after the commit so the link can never arrive before its token is
    # durable. Failures are swallowed — registration must not fail over email.
    try:
        await user_service.deliver_email_verification(body.email, minted.raw_token)
    except Exception:
        logger.warning("email_verification_delivery_failed", exc_info=True)

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

    # The refresh token itself must postdate the last password reset/change
    # or MFA disable — otherwise a stolen refresh token would keep minting
    # fresh access tokens after the user tried to lock it out.
    if is_token_invalidated(payload, user.tokens_valid_from):
        raise SessionRevokedError("Session invalidated by password change; please sign in again")

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
    await user_service.change_password(session, user.id, body.old_password, body.new_password)
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
    minted = await user_service.request_password_reset(session, body.email)
    await session.commit()

    # Deliver after the commit so the link can never arrive before its token is
    # durable. Failures are swallowed — the response must look identical whether
    # or not the account exists, and a dead mail server is not the caller's problem.
    if minted is not None:
        try:
            await user_service.deliver_password_reset(body.email, minted.raw_token)
        except Exception:
            logger.warning("password_reset_delivery_failed", exc_info=True)

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


@router.post("/resend-verification", status_code=202)
@limiter.limit(lambda: "3/minute")
async def resend_verification(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Resend the email verification link for the current user.

    Always 202 for an unverified account so mail outages stay invisible; an
    already-verified account is told so, since the caller is authenticated and
    there is nothing to hide from them.
    """
    if user.email_verified:
        return {"detail": "Email is already verified"}

    minted = await user_service.create_email_verification_link(session, user)
    await session.commit()

    try:
        await user_service.deliver_email_verification(user.email, minted.raw_token)
    except Exception:
        logger.warning("email_verification_delivery_failed", exc_info=True)

    return {"detail": "Verification email sent"}


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
    backup_codes = await user_service.enable_mfa(session, user.id, body.totp_code, body.secret)
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
async def oauth_redirect(provider: str) -> Response:
    """Redirect the user to an OAuth provider's consent screen.

    Generates a CSRF state token, stores it in Redis, and returns a
    redirect to the provider's authorization URL.
    """
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")

    try:
        state = generate_oauth_state()
        await store_oauth_state(state, provider)
        url = build_authorize_url(provider, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("oauth_redirect", provider=provider)
    return RedirectResponse(url=url, status_code=302)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Handle the OAuth provider callback after user consent.

    Validates the state token, exchanges the authorization code for an
    access token, fetches user info, creates or links the user account,
    sets auth cookies, and redirects to the frontend.
    """
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")

    # Extract query params
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.warning("oauth_callback_error", provider=provider, error=error)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    if not code or not state:
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    # Validate CSRF state
    if not await validate_oauth_state(state, provider):
        logger.warning("oauth_invalid_state", provider=provider)
        raise HTTPException(status_code=403, detail="Invalid or expired OAuth state")

    try:
        # Exchange code for token
        token = await exchange_code_for_token(provider, code)

        # Fetch user info from provider
        userinfo = await fetch_userinfo(provider, token)

        if not userinfo.email:
            raise HTTPException(
                status_code=400,
                detail=f"No email returned from {provider}. Check your account privacy settings.",
            )

        # Create or link user
        user = await user_service.create_or_link_oauth(
            session,
            provider=provider,
            provider_user_id=userinfo.provider_user_id,
            email=userinfo.email,
            access_token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            avatar_url=userinfo.avatar_url,
        )
        await session.commit()

        # Set cookies and redirect to dashboard
        redirect = RedirectResponse(url="/", status_code=302)
        _set_auth_cookies(redirect, user)
        logger.info("oauth_login_success", provider=provider, user_id=user.id)
        return redirect

    except HTTPException:
        raise
    except Exception:
        logger.exception("oauth_callback_failed", provider=provider)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)


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
