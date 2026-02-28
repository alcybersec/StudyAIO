"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    courses_router,
    dashboard_router,
    files_router,
    review_items_router,
    summaries_router,
    uploads_router,
)
from app.config import settings
from app.core.exceptions import DuplicateFileError, StudyAIOError
from app.core.logging import configure_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown events."""
    configure_logging(settings.log_level)
    logger.info("studyaio_starting", data_dir=settings.data_dir)
    yield
    logger.info("studyaio_shutting_down")


app = FastAPI(
    title="StudyAIO",
    description="AI-powered study workspace",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


# Exception handlers
@app.exception_handler(DuplicateFileError)
async def duplicate_file_handler(
    request: Request, exc: DuplicateFileError
) -> JSONResponse:
    """Handle duplicate file uploads with 409 Conflict."""
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "existing_artifact_id": exc.existing_artifact_id,
        },
    )


@app.exception_handler(StudyAIOError)
async def studyaio_error_handler(
    request: Request, exc: StudyAIOError
) -> JSONResponse:
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
