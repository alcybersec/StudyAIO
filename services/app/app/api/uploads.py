"""Upload API endpoints."""

import asyncio
import json
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user_or_default
from app.api.schemas import (
    BatchUploadFileResult,
    BatchUploadResponse,
    CaptureRequest,
    PipelineRunResponse,
    RetryResponse,
    UploadResponse,
)
from app.config import settings
from app.core.cache import cache_delete, dashboard_cache_key
from app.core.database import get_session
from app.core.exceptions import DuplicateFileError
from app.core.rate_limit import limiter
from app.core.utils import compute_sha256_from_bytes, read_upload_with_limit
from app.models.user import User
from app.pipeline.orchestrator import resume_pipeline, run_pipeline
from app.services import (
    artifact_service,
    billing_service,
    pipeline_service,
    quota_service,
    xp_service,
)
from app.services.event_service import PIPELINE_EVENTS_CHANNEL

logger = structlog.get_logger()

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}

# Quick captures are limited to 1 MB of text
MAX_CAPTURE_BYTES = 1024 * 1024


@router.post(
    "/uploads",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a lecture file",
    description=(
        "Accepts PDF, DOCX, or PPTX files. Hashes and dedups the bytes in the request, "
        "creates the artifact, then starts the processing pipeline and returns immediately. "
        "The returned artifact_id is always the real artifact — use it to follow the "
        "pipeline-events stream or to retry a stage. A file already in the library returns "
        '201 with status="duplicate" and the existing artifact id; nothing is stored and no '
        "quota or XP is consumed."
    ),
)
@limiter.limit(lambda: settings.rate_limit_uploads)
async def upload_file(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    """Upload a lecture file and start the processing pipeline.

    Hashes and dedups the bytes in the request so the response can carry the
    real artifact id, then stores the file, creates the artifact and dispatches
    the pipeline against it.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # Check upload quota, and that the user can afford the whole pipeline run
    # this upload will trigger. Checking here rather than per stage keeps an
    # accepted upload whole — a stage failing on quota would leave an artifact
    # with a summary and no flashcards.
    await quota_service.check_upload_quota(session, user.id, user.tier)
    await quota_service.check_ai_quota(
        session, user.id, user.tier, calls=quota_service.PIPELINE_AI_CALLS_PER_UPLOAD
    )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await read_upload_with_limit(file, max_bytes)

    # Dedup before touching storage. Doing it here rather than in the worker is
    # what lets the response carry a real artifact id, and it stops a duplicate
    # from orphaning a stored copy or burning quota and XP.
    sha256 = compute_sha256_from_bytes(content)
    existing = await artifact_service.check_duplicate(session, sha256, user.id)
    if existing:
        logger.info(
            "upload_duplicate_detected",
            filename=file.filename,
            existing_artifact_id=existing.id,
        )
        return UploadResponse(
            artifact_id=existing.id,
            filename=file.filename,
            status="duplicate",
            pipeline_task_id=None,
        )

    # Store the bytes and create the artifact row
    try:
        artifact = await artifact_service.create_upload_artifact(
            session,
            content=content,
            original_filename=file.filename,
            sha256=sha256,
            user_id=user.id,
        )
    except IntegrityError:
        # Two identical uploads raced past the dedup check above; the
        # (sha256, user_id) unique constraint settled it. Report the winner.
        await session.rollback()
        existing = await artifact_service.check_duplicate(session, sha256, user.id)
        if existing is None:
            logger.error("upload_conflict_unresolved", filename=file.filename)
            raise HTTPException(status_code=500, detail="Failed to save uploaded file") from None
        return UploadResponse(
            artifact_id=existing.id,
            filename=file.filename,
            status="duplicate",
            pipeline_task_id=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from e

    logger.info(
        "upload_received",
        filename=file.filename,
        artifact_id=artifact.id,
        saved_path=artifact.file_path,
    )

    # Dispatch pipeline against the artifact we just created
    result = run_pipeline(artifact.file_path, user_id=user.id, artifact_id=artifact.id)

    # Record upload usage for quota tracking (best-effort)
    try:
        await billing_service.record_usage(session, user.id, uploads=1)
        await session.commit()
    except Exception:
        logger.warning("usage_record_upload_failed", exc_info=True)

    # Award upload XP (best-effort, separate session since pipeline is async)
    try:
        from app.core.database import async_session_factory

        async with async_session_factory() as xp_session:
            await xp_service.award_xp(xp_session, user.id, "upload")
    except Exception:
        logger.warning("gamification_upload_xp_failed", exc_info=True)

    # Invalidate dashboard cache so next load reflects the new upload
    await cache_delete(dashboard_cache_key(str(user.id)))

    return UploadResponse(
        artifact_id=artifact.id,
        filename=file.filename,
        status="processing",
        pipeline_task_id=result.id if result else None,
    )


@router.post(
    "/uploads/batch",
    response_model=BatchUploadResponse,
    status_code=201,
    summary="Batch upload lecture files",
    description=(
        "Upload multiple lecture files in a single request. Each file is hashed and "
        "deduped before it is stored, so every result carries a real artifact id: "
        'status="processing" for a new artifact, status="duplicate" with the existing '
        "artifact id for a file already in the library. Returns per-file results with "
        "succeeded/failed/duplicate counts."
    ),
)
@limiter.limit("5/minute")
async def batch_upload(
    request: Request,
    files: list[UploadFile],
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> BatchUploadResponse:
    """Upload multiple lecture files and start processing pipelines."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results: list[BatchUploadFileResult] = []
    succeeded = 0
    duplicates = 0
    failed = 0

    for file in files:
        filename = file.filename or "unknown"

        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="error",
                    error=f"Unsupported file type: {ext}",
                )
            )
            failed += 1
            continue

        # Read and hash the bytes
        try:
            max_bytes = settings.max_upload_size_mb * 1024 * 1024
            content = await read_upload_with_limit(file, max_bytes)
        except HTTPException as e:
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="error",
                    error=e.detail,
                )
            )
            failed += 1
            continue
        except Exception as e:
            logger.error("batch_upload_read_failed", filename=filename, error=str(e))
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="error",
                    error="Failed to read file",
                )
            )
            failed += 1
            continue

        # Dedup before storing anything, same as the single-file endpoint
        sha256 = compute_sha256_from_bytes(content)
        existing = await artifact_service.check_duplicate(session, sha256, user.id)
        if existing:
            logger.info(
                "batch_upload_duplicate_detected",
                filename=filename,
                existing_artifact_id=existing.id,
            )
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="duplicate",
                    artifact_id=existing.id,
                )
            )
            duplicates += 1
            continue

        # Store the file and create the artifact row
        try:
            artifact = await artifact_service.create_upload_artifact(
                session,
                content=content,
                original_filename=filename,
                sha256=sha256,
                user_id=user.id,
            )
        except IntegrityError:
            await session.rollback()
            existing = await artifact_service.check_duplicate(session, sha256, user.id)
            if existing is None:
                logger.error("batch_upload_conflict_unresolved", filename=filename)
                results.append(
                    BatchUploadFileResult(
                        filename=filename,
                        status="error",
                        error="Failed to save file",
                    )
                )
                failed += 1
                continue
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="duplicate",
                    artifact_id=existing.id,
                )
            )
            duplicates += 1
            continue
        except Exception as e:
            logger.error("batch_upload_save_failed", filename=filename, error=str(e))
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="error",
                    error="Failed to save file",
                )
            )
            failed += 1
            continue

        # Dispatch pipeline against the artifact we just created
        try:
            run_pipeline(artifact.file_path, user_id=user.id, artifact_id=artifact.id)
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="processing",
                    artifact_id=artifact.id,
                )
            )
            succeeded += 1
        except Exception as e:
            logger.error("batch_upload_pipeline_failed", filename=filename, error=str(e))
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="error",
                    error="Pipeline dispatch failed",
                )
            )
            failed += 1

    logger.info(
        "batch_upload_complete",
        total=len(files),
        succeeded=succeeded,
        duplicates=duplicates,
        failed=failed,
    )

    return BatchUploadResponse(
        total=len(files),
        succeeded=succeeded,
        duplicates=duplicates,
        failed=failed,
        results=results,
    )


@router.post(
    "/uploads/capture",
    response_model=UploadResponse,
    status_code=201,
    summary="Quick capture text or a URL",
    description="Creates a mini text artifact from pasted text or a fetched URL "
    "and runs the processing pipeline from the classify stage. Duplicate "
    "captures (by SHA-256 of the text) return 409.",
)
@limiter.limit(lambda: settings.rate_limit_uploads)
async def quick_capture(
    request: Request,
    body: CaptureRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    """Capture pasted text or a URL as a mini artifact and process it."""
    text = body.text
    title = body.title

    if body.url:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(body.url)
                response.raise_for_status()
                text = response.text
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}") from e
        if not title:
            title = body.url

    if text is None or not text.strip():
        raise HTTPException(status_code=400, detail="Captured content is empty")

    if len(text.encode("utf-8")) > MAX_CAPTURE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Captured text exceeds {MAX_CAPTURE_BYTES // (1024 * 1024)} MB limit",
        )

    # Quick capture counts as an upload, and triggers the same pipeline.
    await quota_service.check_upload_quota(session, user.id, user.tier)
    await quota_service.check_ai_quota(
        session, user.id, user.tier, calls=quota_service.PIPELINE_AI_CALLS_PER_UPLOAD
    )

    try:
        artifact = await artifact_service.ingest_text_capture(
            session, text=text, title=title, user_id=user.id
        )
    except DuplicateFileError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Capture already exists as artifact {e.existing_artifact_id}",
        ) from e

    # Run the pipeline from classify (ingest already done here)
    result = resume_pipeline(artifact.id, from_stage="classify", user_id=user.id)

    # Record upload usage for quota tracking (best-effort)
    try:
        await billing_service.record_usage(session, user.id, uploads=1)
        await session.commit()
    except Exception:
        logger.warning("usage_record_capture_failed", exc_info=True)

    # Invalidate dashboard cache so next load reflects the new capture
    await cache_delete(dashboard_cache_key(str(user.id)))

    logger.info("quick_capture_created", artifact_id=artifact.id, from_url=bool(body.url))

    return UploadResponse(
        artifact_id=artifact.id,
        filename=artifact.original_filename,
        status="processing",
        pipeline_task_id=str(result.id) if result is not None and result.id else None,
    )


@router.get(
    "/uploads/{artifact_id}/status",
    response_model=list[PipelineRunResponse],
    summary="Get pipeline status for an upload",
    description="Returns pipeline run history for an artifact showing each stage's status and timing.",
)
async def get_upload_status(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[PipelineRunResponse]:
    """Get pipeline run status for an uploaded artifact."""
    runs = await pipeline_service.get_artifact_pipeline_runs(session, artifact_id)
    if not runs:
        # Check if artifact exists at all
        artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
    return [PipelineRunResponse.model_validate(r) for r in runs]


# Stage that precedes each stage (used for retry status reset)
_PRE_STAGE_STATUS = {
    "ingest": "ingested",
    "classify": "ingested",
    "extract": "classified",
    "summarize": "extracted",
    "index": "summarized",
    "assets": "indexed",
}


@router.post(
    "/uploads/{artifact_id}/retry",
    response_model=RetryResponse,
    summary="Retry a failed pipeline",
    description="Retries the processing pipeline for a failed artifact, resuming from the failed stage.",
)
async def retry_pipeline(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> RetryResponse:
    """Retry a failed artifact's pipeline from the failed stage."""
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if artifact.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact status is '{artifact.status}', not 'failed'. Only failed artifacts can be retried.",
        )

    # Find the latest failed pipeline run to determine which stage failed
    runs = await pipeline_service.get_artifact_pipeline_runs(session, artifact_id)
    failed_runs = [r for r in runs if r.status == "failed"]
    if not failed_runs:
        raise HTTPException(
            status_code=400,
            detail="No failed pipeline run found for this artifact",
        )

    latest_failed = failed_runs[-1]
    failed_stage = latest_failed.stage

    # Reset artifact status to pre-failure state
    pre_status = _PRE_STAGE_STATUS.get(failed_stage, "ingested")
    artifact.status = pre_status
    await session.commit()

    logger.info(
        "retry_pipeline_dispatched",
        artifact_id=artifact_id,
        failed_stage=failed_stage,
        reset_status=pre_status,
    )

    resume_pipeline(artifact_id, from_stage=failed_stage, user_id=user.id)

    return RetryResponse(
        artifact_id=artifact_id,
        status=pre_status,
        retrying_from_stage=failed_stage,
    )


@router.get(
    "/uploads/pipeline-events",
    summary="Stream pipeline events (SSE)",
    description="Server-Sent Events stream for real-time pipeline progress. Optionally filter by artifact_id.",
)
async def pipeline_events(
    request: Request,
    artifact_id: str = Query(default=""),
    user: User = Depends(get_current_user_or_default),
) -> EventSourceResponse:
    """SSE stream of pipeline events, optionally filtered by artifact_id."""

    async def event_generator():
        # Send initial comment so EventSource.onopen fires immediately
        yield {"comment": "connected"}

        # Connect timeout only: this is a long-lived subscriber, and a socket
        # read timeout would fight the explicit `get_message(timeout=...)`
        # below. The connect timeout is what stops an unreachable Redis from
        # hanging the request forever.
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
        )
        pubsub = redis.pubsub()
        await pubsub.subscribe(PIPELINE_EVENTS_CHANNEL)
        heartbeat_interval = 15
        heartbeat_counter = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    if not artifact_id or data.get("artifact_id") == artifact_id:
                        yield {"event": "pipeline", "data": json.dumps(data)}
                    heartbeat_counter = 0
                else:
                    heartbeat_counter += 1
                    if heartbeat_counter >= heartbeat_interval:
                        yield {"comment": "keepalive"}
                        heartbeat_counter = 0
                    await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(PIPELINE_EVENTS_CHANNEL)
            await redis.aclose()

    return EventSourceResponse(event_generator())
