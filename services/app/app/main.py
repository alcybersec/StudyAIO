"""FastAPI application factory."""

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
    QuotaExceededError,
    StudyAIOError,
    UserExistsError,
)
from app.core.logging import configure_logging
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


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration."""

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
        )
        return response


_DEFAULT_JWT_SECRET = "changeme-in-production-use-a-real-secret"


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

    logger.info("studyaio_starting", data_dir=settings.data_dir)
    yield
    logger.info("studyaio_shutting_down")


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
        {"name": "search", "description": "Global search across courses, summaries, flashcards, and chats"},
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
