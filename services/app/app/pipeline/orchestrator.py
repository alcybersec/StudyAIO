"""Pipeline orchestrator — builds and dispatches Celery chains."""

import structlog
from celery import chain
from celery.result import AsyncResult

from app.pipeline.ingest import ingest_file
from app.pipeline.classify import classify_artifact
from app.pipeline.extract import extract_artifact
from app.pipeline.summarize import summarize_artifact
from app.pipeline.index import index_artifact
from app.pipeline.assets import generate_assets

logger = structlog.get_logger()

# Stage order for resume_pipeline
_STAGES = {
    "ingest": [ingest_file, classify_artifact, extract_artifact, summarize_artifact, index_artifact, generate_assets],
    "classify": [classify_artifact, extract_artifact, summarize_artifact, index_artifact, generate_assets],
    "extract": [extract_artifact, summarize_artifact, index_artifact, generate_assets],
    "summarize": [summarize_artifact, index_artifact, generate_assets],
    "index": [index_artifact, generate_assets],
    "assets": [generate_assets],
}


def resolve_pipeline_input(input_value: str | dict, stage: str) -> str | None:
    """Extract artifact_id from pipeline input, or None if pipeline should stop.

    Args:
        input_value: Either a plain artifact_id string or a dict from a previous stage.
        stage: Current stage name (for logging).

    Returns:
        artifact_id string, or None if a stop status was detected.
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
            return None
        return input_value.get("artifact_id", "") or None
    return input_value or None


def run_pipeline(file_path: str) -> AsyncResult:
    """Build and dispatch the full ingest-to-summarize pipeline.

    Args:
        file_path: Absolute path to the file to ingest.

    Returns:
        Celery AsyncResult for the chain.
    """
    logger.info("pipeline_dispatched", file_path=file_path)
    return chain(
        ingest_file.s(file_path),
        classify_artifact.s(),
        extract_artifact.s(),
        summarize_artifact.s(),
        index_artifact.s(),
        generate_assets.s(),
    ).apply_async()


def resume_pipeline(artifact_id: str, from_stage: str) -> AsyncResult:
    """Resume pipeline from a given stage.

    Useful after resolving a review item to continue processing.

    Args:
        artifact_id: UUID of the artifact to continue processing.
        from_stage: Stage name to resume from (classify, extract, summarize).

    Returns:
        Celery AsyncResult for the chain.

    Raises:
        ValueError: If from_stage is not a valid stage.
    """
    tasks = _STAGES.get(from_stage)
    if tasks is None:
        raise ValueError(
            f"Unknown stage: {from_stage}. Valid: {list(_STAGES.keys())}"
        )

    logger.info(
        "pipeline_resumed",
        artifact_id=artifact_id,
        from_stage=from_stage,
        stages=len(tasks),
    )

    if len(tasks) == 1:
        return tasks[0].apply_async(args=[artifact_id])

    return chain(
        tasks[0].s(artifact_id),
        *[t.s() for t in tasks[1:]],
    ).apply_async()
