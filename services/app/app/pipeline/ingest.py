"""Pipeline stage 0: Ingest — receive file, hash, dedup, create artifact."""

from datetime import UTC, datetime

import structlog

from app.core.database import async_session_factory, run_async
from app.core.exceptions import DuplicateFileError
from app.core.utils import generate_id
from app.models.pipeline_run import PipelineRun
from app.services import artifact_service
from app.services.event_service import publish_pipeline_event_sync
from app.worker import celery_app

logger = structlog.get_logger()


async def _ingest(
    file_path: str, user_id: str | None = None, artifact_id: str | None = None
) -> dict:
    """Async ingest implementation.

    Args:
        file_path: Storage key of the file to ingest.
        user_id: Owner user UUID.
        artifact_id: Artifact already created by the upload endpoint. When set,
            hashing/dedup/creation are skipped and this row is adopted.
    """
    async with async_session_factory() as session:
        # Create pipeline run record. Without a pre-created artifact the id is
        # only known once ingest_file returns, hence the placeholder.
        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact_id or "pending",
            stage="ingest",
            status="running",
            started_at=datetime.now(UTC),
        )

        try:
            artifact = await artifact_service.ingest_file(
                session, file_path, user_id=user_id or "", artifact_id=artifact_id
            )

            # Update pipeline run with real artifact_id
            run.artifact_id = artifact.id
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            if run.started_at:
                delta = run.completed_at - run.started_at
                run.duration_ms = int(delta.total_seconds() * 1000)

            session.add(run)
            await session.commit()

            logger.info(
                "ingest_stage_completed",
                artifact_id=artifact.id,
                filename=artifact.original_filename,
            )

            return {
                "artifact_id": artifact.id,
                "user_id": user_id,
                "status": "ingested",
                "filename": artifact.original_filename,
                "sha256": artifact.sha256,
            }

        except DuplicateFileError as e:
            logger.info("ingest_stage_duplicate", sha256=e.sha256)
            return {
                "artifact_id": e.existing_artifact_id,
                "user_id": user_id,
                "status": "duplicate",
                "sha256": e.sha256,
            }

        except Exception as e:
            logger.error("ingest_stage_failed", error=str(e), file_path=file_path)
            raise


@celery_app.task(
    name="app.pipeline.ingest.ingest_file",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def ingest_file(self, input_value: str | dict) -> dict:
    """Celery task: ingest a file into the pipeline.

    Args:
        input_value: Either a file_path string or dict with file_path and user_id.

    Returns:
        Dict with artifact_id, user_id, status, filename, sha256.
    """
    # Parse input — supports both legacy string and new dict format
    if isinstance(input_value, dict):
        file_path = input_value.get("file_path", "")
        user_id = input_value.get("user_id")
        known_artifact_id = input_value.get("artifact_id")
    else:
        file_path = input_value
        user_id = None
        known_artifact_id = None

    logger.info(
        "ingest_task_started", file_path=file_path, user_id=user_id, artifact_id=known_artifact_id
    )
    # Uploads always pass the real id here. Only a caller that has not created
    # the artifact yet falls back to the placeholder, which no client filters on.
    publish_pipeline_event_sync(known_artifact_id or "pending", "ingest", "started")
    try:
        result = run_async(_ingest(file_path, user_id=user_id, artifact_id=known_artifact_id))
        artifact_id = result.get("artifact_id") or known_artifact_id or "unknown"
        publish_pipeline_event_sync(artifact_id, "ingest", result.get("status", "completed"))
        return result
    except (DuplicateFileError, FileNotFoundError, ValueError):
        raise  # Don't retry on expected errors
    except Exception as exc:
        logger.error("ingest_task_error", error=str(exc))
        publish_pipeline_event_sync(known_artifact_id or "unknown", "ingest", "failed", str(exc))
        raise self.retry(exc=exc) from exc
