"""Upload API endpoints."""

import asyncio
import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import (
    BatchUploadFileResult,
    BatchUploadResponse,
    PipelineRunResponse,
    RetryResponse,
    UploadResponse,
)
from app.config import settings
from app.core.database import get_session
from app.core.exceptions import DuplicateFileError
from app.core.rate_limit import limiter
from app.core.utils import read_upload_with_limit, sanitize_filename
from app.pipeline.orchestrator import resume_pipeline, run_pipeline
from app.services import artifact_service, pipeline_service
from app.services.event_service import PIPELINE_EVENTS_CHANNEL

logger = structlog.get_logger()

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}


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

    # Save to shared uploads directory (accessible by both API and worker containers)
    try:
        uploads_dir = Path(settings.data_dir) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(file.filename)
        if not safe_name:
            safe_name = f"upload{Path(file.filename).suffix}"
        dest = uploads_dir / safe_name

        # Handle filename collision with counter
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            counter = 1
            while dest.exists():
                dest = uploads_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        content = await read_upload_with_limit(file, max_bytes)
        dest.write_bytes(content)
        file_path = str(dest)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from e

    logger.info("upload_received", filename=file.filename, saved_path=file_path)

    # Dispatch pipeline
    try:
        result = run_pipeline(file_path)
    except DuplicateFileError as e:
        raise HTTPException(
            status_code=409,
            detail=f"File already exists as artifact {e.existing_artifact_id}",
        ) from e

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
    session: AsyncSession = Depends(get_session),
) -> BatchUploadResponse:
    """Upload multiple lecture files and start processing pipelines."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results: list[BatchUploadFileResult] = []
    succeeded = 0
    duplicates = 0
    failed = 0

    uploads_dir = Path(settings.data_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        filename = file.filename or "unknown"

        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            results.append(BatchUploadFileResult(
                filename=filename,
                status="error",
                error=f"Unsupported file type: {ext}",
            ))
            failed += 1
            continue

        # Save file
        try:
            safe_name = sanitize_filename(filename)
            if not safe_name:
                safe_name = f"upload{ext}"
            dest = uploads_dir / safe_name

            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = uploads_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            max_bytes = settings.max_upload_size_mb * 1024 * 1024
            content = await read_upload_with_limit(file, max_bytes)
            dest.write_bytes(content)
            file_path = str(dest)
        except HTTPException as e:
            results.append(BatchUploadFileResult(
                filename=filename,
                status="error",
                error=e.detail,
            ))
            failed += 1
            continue
        except Exception as e:
            logger.error("batch_upload_save_failed", filename=filename, error=str(e))
            results.append(BatchUploadFileResult(
                filename=filename,
                status="error",
                error="Failed to save file",
            ))
            failed += 1
            continue

        # Dispatch pipeline
        try:
            pipeline_result = run_pipeline(file_path)
            results.append(BatchUploadFileResult(
                filename=filename,
                status="processing",
                artifact_id="pending",
            ))
            succeeded += 1
        except DuplicateFileError as e:
            results.append(BatchUploadFileResult(
                filename=filename,
                status="duplicate",
                artifact_id=e.existing_artifact_id,
            ))
            duplicates += 1
        except Exception as e:
            logger.error("batch_upload_pipeline_failed", filename=filename, error=str(e))
            results.append(BatchUploadFileResult(
                filename=filename,
                status="error",
                error="Pipeline dispatch failed",
            ))
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


@router.get(
    "/uploads/{artifact_id}/status",
    response_model=list[PipelineRunResponse],
    summary="Get pipeline status for an upload",
    description="Returns pipeline run history for an artifact showing each stage's status and timing.",
)
async def get_upload_status(
    artifact_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[PipelineRunResponse]:
    """Get pipeline run status for an uploaded artifact."""
    runs = await pipeline_service.get_artifact_pipeline_runs(session, artifact_id)
    if not runs:
        # Check if artifact exists at all
        artifact = await artifact_service.get_artifact(session, artifact_id)
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
    session: AsyncSession = Depends(get_session),
) -> RetryResponse:
    """Retry a failed artifact's pipeline from the failed stage."""
    artifact = await artifact_service.get_artifact(session, artifact_id)
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

    resume_pipeline(artifact_id, from_stage=failed_stage)

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
