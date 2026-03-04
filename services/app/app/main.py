"""FastAPI application factory."""

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
    assets_router,
    courseops_router,
    courses_router,
    dashboard_router,
    exams_router,
    exports_router,
    files_router,
    qa_router,
    review_items_router,
    settings_router,
    study_router,
    summaries_router,
    uploads_router,
)
from app.config import settings
from app.core.exceptions import DuplicateFileError, StudyAIOError
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
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown events."""
    configure_logging(settings.log_level)
    logger.info("studyaio_starting", data_dir=settings.data_dir)
    yield
    logger.info("studyaio_shutting_down")


app = FastAPI(
    title="StudyAIO",
    description="AI-powered study workspace — automates the journey from raw lecture "
    "files (PDF, DOCX, PPTX) to organized, searchable, exam-ready study materials.",
    version="0.1.0",
    lifespan=lifespan,
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
        {"name": "qa", "description": "Question & Answer with citation support"},
        {"name": "assets", "description": "Flashcards and quiz questions"},
        {"name": "exams", "description": "Exam management, scheduling, and progress"},
        {"name": "study", "description": "Spaced repetition study sessions"},
        {"name": "settings", "description": "Application settings management"},
        {"name": "exports", "description": "Data export (Obsidian vault, etc.)"},
        {"name": "courseops", "description": "Course documents, assessments, deadlines, and calendar exports"},
    ],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request ID middleware (outermost — wraps everything)
app.add_middleware(RequestIDMiddleware)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

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
app.include_router(summaries_router, prefix="/api", tags=["summaries"])
app.include_router(review_items_router, prefix="/api", tags=["review-items"])
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(qa_router, prefix="/api", tags=["qa"])
app.include_router(assets_router, prefix="/api", tags=["assets"])
app.include_router(exams_router, prefix="/api", tags=["exams"])
app.include_router(study_router, prefix="/api", tags=["study"])
app.include_router(settings_router, prefix="/api", tags=["settings"])
app.include_router(exports_router, prefix="/api", tags=["exports"])
app.include_router(courseops_router, prefix="/api", tags=["courseops"])


# Exception handlers
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
