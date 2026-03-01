"""Upload API endpoints."""

import asyncio
import json
import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import PipelineRunResponse, RetryResponse, UploadResponse
from app.config import settings
from app.core.database import get_session
from app.core.exceptions import DuplicateFileError
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
async def upload_file(
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

    # Save to temp file
    try:
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        logger.error("upload_save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file") from e

    logger.info("upload_received", filename=file.filename, temp_path=tmp_path)

    # Dispatch pipeline
    try:
        result = run_pipeline(tmp_path)
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
