"""Upload API endpoints."""

import asyncio
import json
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from redis.asyncio import Redis
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
from app.core.storage import get_storage
from app.core.utils import read_upload_with_limit, sanitize_filename
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
    description="Accepts PDF, DOCX, or PPTX files. Saves to storage, starts the processing pipeline, and returns immediately. Duplicate files (by SHA-256) return 409.",
)
@limiter.limit(lambda: settings.rate_limit_uploads)
async def upload_file(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    """Upload a lecture file and start the processing pipeline.

    Saves the file to a temp location and dispatches the pipeline.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # Check upload quota (free tier: 5/month)
    await quota_service.check_upload_quota(session, user.id, user.tier)

    # Save to storage backend
    try:
        storage = get_storage()
        await storage.ensure_dir("uploads")

        safe_name = sanitize_filename(file.filename)
        if not safe_name:
            safe_name = f"upload{Path(file.filename).suffix}"
        storage_key = f"uploads/{safe_name}"

        # Handle key collision with counter
        if await storage.exists(storage_key):
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix
            counter = 1
            while await storage.exists(storage_key):
                storage_key = f"uploads/{stem}_{counter}{suffix}"
                counter += 1

        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        content = await read_upload_with_limit(file, max_bytes)
        await storage.put(storage_key, content)
        file_path = storage_key
    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from e

    logger.info("upload_received", filename=file.filename, saved_path=file_path)

    # Dispatch pipeline
    try:
        result = run_pipeline(file_path, user_id=user.id)
    except DuplicateFileError as e:
        raise HTTPException(
            status_code=409,
            detail=f"File already exists as artifact {e.existing_artifact_id}",
        ) from e

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
        artifact_id="pending",
        filename=file.filename,
        status="processing",
        pipeline_task_id=result.id if result else None,
    )


@router.post(
    "/uploads/batch",
    response_model=BatchUploadResponse,
    status_code=201,
    summary="Batch upload lecture files",
    description="Upload multiple lecture files in a single request. Returns per-file results with succeeded/failed/duplicate counts.",
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

    storage = get_storage()
    await storage.ensure_dir("uploads")

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

        # Save file
        try:
            safe_name = sanitize_filename(filename)
            if not safe_name:
                safe_name = f"upload{ext}"
            storage_key = f"uploads/{safe_name}"

            if await storage.exists(storage_key):
                stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                counter = 1
                while await storage.exists(storage_key):
                    storage_key = f"uploads/{stem}_{counter}{suffix}"
                    counter += 1

            max_bytes = settings.max_upload_size_mb * 1024 * 1024
            content = await read_upload_with_limit(file, max_bytes)
            await storage.put(storage_key, content)
            file_path = storage_key
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

        # Dispatch pipeline
        try:
            run_pipeline(file_path, user_id=user.id)
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="processing",
                    artifact_id="pending",
                )
            )
            succeeded += 1
        except DuplicateFileError as e:
            results.append(
                BatchUploadFileResult(
                    filename=filename,
                    status="duplicate",
                    artifact_id=e.existing_artifact_id,
                )
            )
            duplicates += 1
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

    # Quick capture counts as an upload for quota purposes
    await quota_service.check_upload_quota(session, user.id, user.tier)

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

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
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
