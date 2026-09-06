"""FastAPI application factory."""

import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.agents.embeddings import get_embedding_provider
from app.api import (
    admin_router,
    analytics_router,
    artifacts_router,
    assets_router,
    auth_router,
    billing_router,
    calendar_sync_router,
    chat_router,
    concepts_router,
    courseops_router,
    courses_router,
    dashboard_router,
    exams_router,
    exports_router,
    files_router,
    gamification_router,
    notifications_inbox_router,
    notifications_router,
    qa_router,
    review_items_router,
    search_router,
    settings_router,
    study_router,
    summaries_router,
    uploads_router,
)
from app.config import settings
from app.core.demo_middleware import DemoAccountMiddleware
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DemoRestrictionError,
    DuplicateFileError,
    GlobalCeilingError,
    InviteError,
    LastAdminError,
    ProviderCredentialError,
    QuotaExceededError,
    RegistrationClosedError,
    StudyAIOError,
    UserExistsError,
)
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.core.rate_limit import limiter

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request/response and structlog context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_contextvars()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


def client_ip(request: Request) -> str:
    """The address a request is attributed to, for logging.

    Deliberately `request.client.host` — the exact value the rate limiter keys
    on (`slowapi.util.get_remote_address`). The two must agree, or a 429 in the
    log cannot be traced to the address that earned it, which is most of the
    point of recording it.

    That also rules out reading `X-Forwarded-For` here. A client can put
    anything in that header; the value only becomes trustworthy after the ASGI
    proxy-header layer has resolved it against the trusted hops, and the result
    of that resolution is `request.client` — which is what this returns.

    Args:
        request: The incoming request.

    Returns:
        The client address, or "unknown" when the transport reports none
        (in-process test clients and some ASGI servers leave it unset).
    """
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, duration, and client.

    The client address is recorded so authentication failures can be attributed
    and a brute-force attempt can be seen at all. Without it a burst of 401s is
    indistinguishable from one user mistyping a password, and an attack that has
    already happened cannot be investigated.

    Note this makes the application log personal data. It is the minimum needed
    for abuse investigation, and log retention governs how long it lives.
    """

    _SKIP_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip(request),
        )
        return response


_DEFAULT_JWT_SECRET = "changeme-in-production-use-a-real-secret"

#: Uvicorn's own default for --forwarded-allow-ips. Behind a reverse proxy on a
#: different host, this means every forwarding header is discarded.
_DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1"


def warn_if_proxy_headers_untrusted() -> None:
    """Warn when the app is behind a proxy it has not been told to trust.

    Uvicorn only honours `X-Forwarded-For` when the immediate peer appears in
    `--forwarded-allow-ips` / `FORWARDED_ALLOW_IPS`, which defaults to
    `127.0.0.1`. A reverse proxy on any other host therefore has its forwarding
    headers discarded, and `request.client.host` stays the proxy's address —
    for every request, from every client.

    That is not a cosmetic problem. The rate limiter keys on that address, so
    the whole internet lands in a single bucket: a handful of requests a minute
    from anywhere exhausts the login, registration and password-reset limits
    for every user at once. It also makes the access log useless for
    attribution. See StudyAIO issue #39.

    This only warns. The correct value depends on deployment topology, so
    guessing one would be worse than saying clearly that it is unset.
    """
    if settings.self_hosted:
        return

    configured = os.environ.get("FORWARDED_ALLOW_IPS", "").strip()
    if configured and configured != _DEFAULT_FORWARDED_ALLOW_IPS:
        return

    logger.warning(
        "proxy_headers_untrusted",
        forwarded_allow_ips=configured or _DEFAULT_FORWARDED_ALLOW_IPS,
        detail=(
            "X-Forwarded-For will be ignored, so every client shares one "
            "rate-limit bucket and the access log records the proxy address. "
            "Set FORWARDED_ALLOW_IPS to the reverse proxy's address."
        ),
    )


def warn_if_embedding_provider_unavailable() -> None:
    """Say loudly at startup when this process cannot embed text.

    Every retrieval path in the API needs an embedding provider, and until
    issue #44 not one of them had one. The api container runs as `studyaio`,
    whose home is the root-owned `/app`, so sentence-transformers could not
    create its model cache: `POST /api/qa` raised and returned 500, and chat
    caught the identical error and answered with no lecture context at all.
    That ran for six months. The process said nothing at boot either time.

    Note this **loads** the model rather than only constructing the provider.
    Construction is lazy — `SentenceTransformerProvider.__init__` records a
    model name and returns without touching the filesystem — so a check that
    stopped at `get_embedding_provider()` would have passed happily throughout
    the outage. `preload()` is the step that actually resolves the cache. For
    the OpenAI and Ollama backends `preload()` is a documented no-op, so this
    costs them nothing and never makes a billable call at startup.

    This only logs. A self-hosted instance that has deliberately stripped the
    model should still start and serve everything that does not need
    retrieval — the same reasoning as `warn_if_proxy_headers_untrusted`, at
    error level because unlike an untrusted proxy header this one means a
    feature is already dead.

    Nothing equivalent runs in the Celery worker: it does not execute this
    lifespan, and the worker's embedding paths were never the broken ones.
    """
    try:
        provider = get_embedding_provider()
        provider.preload()
    except Exception as exc:
        logger.error(
            "embedding_provider_unavailable",
            backend=settings.embedding_backend,
            model=settings.embedding_model,
            error=str(exc),
            error_type=type(exc).__name__,
            detail=(
                "Retrieval is dead in this process: /api/qa will return 500 and "
                "chat will answer without any lecture context, silently. A "
                "permission error here means the model cache is not readable by "
                "the user this container runs as — the image bakes a "
                "world-readable one at HF_HOME, so check that it survived the "
                "build and that EMBEDDING_MODEL still names the baked model."
            ),
        )
        return

    logger.info(
        "embedding_provider_ready",
        backend=settings.embedding_backend,
        dimensions=provider.dimensions,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown events."""
    configure_logging(settings.log_level)

    # Refuse to start with default JWT secret in SaaS mode
    if (
        not settings.self_hosted
        and settings.jwt_secret_key.get_secret_value() == _DEFAULT_JWT_SECRET
    ):
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY is set to the default value. "
            "You MUST set a unique, random JWT_SECRET_KEY in production (SaaS mode). "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    warn_if_proxy_headers_untrusted()
    warn_if_embedding_provider_unavailable()

    logger.info("studyaio_starting", data_dir=settings.data_dir)
    yield
    logger.info("studyaio_shutting_down")


# Error monitoring — must run before the app is built so startup errors are caught.
init_sentry("api")

# Prometheus metrics (conditional)
if settings.prometheus_enabled:
    from prometheus_fastapi_instrumentator import Instrumentator

    _instrumentator = Instrumentator()
else:
    _instrumentator = None

app = FastAPI(
    title="StudyAIO",
    description="AI-powered study workspace — automates the journey from raw lecture "
    "files (PDF, DOCX, PPTX) to organized, searchable, exam-ready study materials.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json" if settings.openapi_enabled else None,
    docs_url="/docs" if settings.openapi_enabled else None,
    redoc_url="/redoc" if settings.openapi_enabled else None,
    openapi_tags=[
        {"name": "dashboard", "description": "Aggregated dashboard data"},
        {"name": "courses", "description": "Course listing and per-week breakdowns"},
        {"name": "uploads", "description": "File uploads and pipeline status"},
        {"name": "summaries", "description": "Generated weekly summaries"},
        {
            "name": "review-items",
            "description": "Human review inbox for low-confidence classifications",
        },
        {"name": "files", "description": "Serve files from data directories"},
        {
            "name": "search",
            "description": "Global search across courses, summaries, flashcards, and chats",
        },
        {"name": "qa", "description": "Question & Answer with citation support"},
        {"name": "assets", "description": "Flashcards and quiz questions"},
        {"name": "exams", "description": "Exam management, scheduling, and progress"},
        {"name": "study", "description": "Spaced repetition study sessions"},
        {"name": "settings", "description": "Application settings management"},
        {"name": "exports", "description": "Data export (Obsidian vault, etc.)"},
        {
            "name": "courseops",
            "description": "Course documents, assessments, deadlines, and calendar exports",
        },
        {
            "name": "auth",
            "description": "Authentication, registration, MFA, and session management",
        },
        {"name": "admin", "description": "User management and system metrics (admin only)"},
        {
            "name": "analytics",
            "description": "Learning analytics, heatmaps, retention, and exam readiness",
        },
        {"name": "chat", "description": "Persistent AI study companion chat sessions"},
        {
            "name": "gamification",
            "description": "XP, levels, achievements, daily challenges, leaderboard",
        },
        {
            "name": "concepts",
            "description": "Knowledge graph: concept extraction, visualization, and relationships",
        },
        {"name": "billing", "description": "Stripe billing, subscriptions, and usage quotas"},
        {
            "name": "notifications",
            "description": "Email/Telegram notifications, preferences, and Telegram linking",
        },
        {"name": "calendar", "description": "Google Calendar bidirectional sync"},
    ],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request ID middleware (outermost — wraps everything)
app.add_middleware(RequestIDMiddleware)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Access log middleware (inside RequestID context for request_id in logs)
app.add_middleware(AccessLogMiddleware)

# Demo account restrictions (blocks writes for demo users)
app.add_middleware(DemoAccountMiddleware)

# CORS — origins from config
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
app.include_router(courses_router, prefix="/api", tags=["courses"])
app.include_router(uploads_router, prefix="/api", tags=["uploads"])
app.include_router(artifacts_router, prefix="/api", tags=["uploads"])
app.include_router(summaries_router, prefix="/api", tags=["summaries"])
app.include_router(review_items_router, prefix="/api", tags=["review-items"])
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(qa_router, prefix="/api", tags=["qa"])
app.include_router(assets_router, prefix="/api", tags=["assets"])
app.include_router(exams_router, prefix="/api", tags=["exams"])
app.include_router(study_router, prefix="/api", tags=["study"])
app.include_router(settings_router, prefix="/api", tags=["settings"])
app.include_router(exports_router, prefix="/api", tags=["exports"])
app.include_router(courseops_router, prefix="/api", tags=["courseops"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(admin_router, prefix="/api", tags=["admin"])
app.include_router(analytics_router, prefix="/api", tags=["analytics"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(gamification_router, prefix="/api", tags=["gamification"])
app.include_router(concepts_router, prefix="/api", tags=["concepts"])
app.include_router(billing_router, prefix="/api", tags=["billing"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(notifications_inbox_router, prefix="/api", tags=["notifications"])
app.include_router(calendar_sync_router, prefix="/api", tags=["calendar"])

# Instrument with Prometheus if enabled
if _instrumentator is not None:
    _instrumentator.instrument(app).expose(app, endpoint="/metrics")


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    """Handle authentication errors with 401."""
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    """Handle authorization errors with 403."""
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UserExistsError)
async def user_exists_handler(request: Request, exc: UserExistsError) -> JSONResponse:
    """Handle duplicate user registration with 409."""
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DemoRestrictionError)
async def demo_restriction_handler(request: Request, exc: DemoRestrictionError) -> JSONResponse:
    """Handle demo account restriction errors with 403."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": exc.message,
            "upgrade_url": "/register",
        },
    )


@app.exception_handler(LastAdminError)
async def last_admin_handler(request: Request, exc: LastAdminError) -> JSONResponse:
    """Handle last-admin protection with 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(GlobalCeilingError)
async def global_ceiling_handler(request: Request, exc: GlobalCeilingError) -> JSONResponse:
    """Handle the instance-wide daily AI ceiling with 429 + Retry-After."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc),
            "resource": exc.resource,
            "limit": exc.limit,
        },
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


@app.exception_handler(InviteError)
async def invite_error_handler(request: Request, exc: InviteError) -> JSONResponse:
    """Handle invalid invite codes with 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RegistrationClosedError)
async def registration_closed_handler(
    request: Request, exc: RegistrationClosedError
) -> JSONResponse:
    """Handle registration being disabled with 403."""
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ProviderCredentialError)
async def provider_credential_handler(
    request: Request, exc: ProviderCredentialError
) -> JSONResponse:
    """Handle a provider selected without a credential with 400."""
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "backend": exc.backend,
            "credential_key": exc.credential_key,
        },
    )


@app.exception_handler(QuotaExceededError)
async def quota_exceeded_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
    """Handle quota exceeded errors with 402 Payment Required."""
    return JSONResponse(
        status_code=402,
        content={
            "detail": str(exc),
            "resource": exc.resource,
            "limit": exc.limit,
            "period": exc.period,
        },
    )


@app.exception_handler(DuplicateFileError)
async def duplicate_file_handler(request: Request, exc: DuplicateFileError) -> JSONResponse:
    """Handle duplicate file uploads with 409 Conflict."""
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "existing_artifact_id": exc.existing_artifact_id,
        },
    )


@app.exception_handler(StudyAIOError)
async def studyaio_error_handler(request: Request, exc: StudyAIOError) -> JSONResponse:
    """Handle application errors with 500."""
    logger.error("unhandled_studyaio_error", error=str(exc), type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Liveness probe — confirms the process is running."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_check() -> Response:
    """Readiness probe — verifies DB and Redis connectivity."""
    from app.core.cache import check_redis_connectivity
    from app.core.database import check_db_connectivity

    db_ok = await check_db_connectivity()
    redis_ok = await check_redis_connectivity()
    all_ok = db_ok and redis_ok

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "degraded",
            "checks": {
                "database": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
        },
    )
