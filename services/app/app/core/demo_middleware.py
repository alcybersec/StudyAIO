"""Middleware to restrict demo users to read-only operations."""

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings
from app.core.auth import ACCESS_TOKEN_COOKIE, decode_token

logger = structlog.get_logger()

# HTTP methods that are always allowed for demo users
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Write paths that demo users are allowed to use (auth flows)
_ALLOWED_WRITE_PATHS = {
    "/api/auth/logout",
    "/api/auth/refresh",
}


class DemoAccountMiddleware(BaseHTTPMiddleware):
    """Block write operations for demo users.

    Demo users (role=demo) can only perform GET/HEAD/OPTIONS requests,
    plus a small allowlist of auth-related writes. All other writes
    return a 403 with an upgrade URL.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip entirely if demo mode is disabled
        if not settings.demo_enabled:
            return await call_next(request)

        # Safe methods always pass through
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Check if the user is a demo user via JWT cookie
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
        if not token:
            # No cookie — let endpoint deps handle auth
            return await call_next(request)

        try:
            payload = decode_token(token)
        except Exception:
            # Invalid token — let endpoint deps handle it
            return await call_next(request)

        if payload.get("role") != "demo":
            # Regular user — allow through
            return await call_next(request)

        # Demo user attempting a write — check allowlist
        path = request.url.path
        if path in _ALLOWED_WRITE_PATHS:
            return await call_next(request)

        logger.info("demo_write_blocked", path=path, method=request.method)
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Demo account — read-only access",
                "upgrade_url": "/register",
            },
        )
