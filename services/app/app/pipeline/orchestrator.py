"""Pipeline orchestrator — builds and dispatches Celery chains."""

import structlog
from celery import chain
from celery.result import AsyncResult

from app.pipeline.assets import generate_assets
from app.pipeline.classify import classify_artifact
from app.pipeline.extract import extract_artifact
from app.pipeline.index import index_artifact
from app.pipeline.ingest import ingest_file
from app.pipeline.summarize import summarize_artifact

logger = structlog.get_logger()

# Stage order for resume_pipeline
_STAGES = {
    "ingest": [
        ingest_file,
        classify_artifact,
        extract_artifact,
        summarize_artifact,
        index_artifact,
        generate_assets,
    ],
    "classify": [
        classify_artifact,
        extract_artifact,
        summarize_artifact,
        index_artifact,
        generate_assets,
    ],
    "extract": [extract_artifact, summarize_artifact, index_artifact, generate_assets],
    "summarize": [summarize_artifact, index_artifact, generate_assets],
    "index": [index_artifact, generate_assets],
    "assets": [generate_assets],
}


def resolve_pipeline_input(input_value: str | dict, stage: str) -> tuple[str | None, str | None]:
    """Extract artifact_id and user_id from pipeline input.

    Args:
        input_value: Either a plain artifact_id string or a dict from a previous stage.
        stage: Current stage name (for logging).

    Returns:
        Tuple of (artifact_id, user_id), either may be None if pipeline should stop.
    """
    if isinstance(input_value, dict):
        status = input_value.get("status", "")
        if status in ("duplicate", "waiting_review", "failed"):
            logger.info(
                "pipeline_stop",
                stage=stage,
                status=status,
                artifact_id=input_value.get("artifact_id"),
            )
            return None, None
        artifact_id = input_value.get("artifact_id", "") or None
        user_id = input_value.get("user_id")
        return artifact_id, user_id
    return input_value or None, None


def run_pipeline(file_path: str, user_id: str | None = None) -> AsyncResult:
    """Build and dispatch the full ingest-to-assets pipeline.

    Args:
        file_path: Absolute path to the file to ingest.
        user_id: Owner user UUID (threaded through all stages).

    Returns:
        Celery AsyncResult for the chain.
    """
    logger.info("pipeline_dispatched", file_path=file_path, user_id=user_id)
    # Pack file_path and user_id into a dict for the first stage
    initial_input = {"file_path": file_path, "user_id": user_id}
    return chain(
        ingest_file.s(initial_input),
        classify_artifact.s(),
        extract_artifact.s(),
        summarize_artifact.s(),
        index_artifact.s(),
        generate_assets.s(),
    ).apply_async()


def resume_pipeline(
    artifact_id: str, from_stage: str, user_id: str | None = None
) -> AsyncResult:
    """Resume pipeline from a given stage.

    Args:
        artifact_id: UUID of the artifact to continue processing.
        from_stage: Stage name to resume from.
        user_id: Owner user UUID.

    Returns:
        Celery AsyncResult for the chain.

    Raises:
        ValueError: If from_stage is not a valid stage.
    """
    tasks = _STAGES.get(from_stage)
    if tasks is None:
        raise ValueError(f"Unknown stage: {from_stage}. Valid: {list(_STAGES.keys())}")

    logger.info(
        "pipeline_resumed",
        artifact_id=artifact_id,
        from_stage=from_stage,
        stages=len(tasks),
        user_id=user_id,
    )

    # Pack artifact_id and user_id for chain input
    initial_input = {"artifact_id": artifact_id, "user_id": user_id}

    if len(tasks) == 1:
        return tasks[0].apply_async(args=[initial_input])

    return chain(
        tasks[0].s(initial_input),
        *[t.s() for t in tasks[1:]],
    ).apply_async()
