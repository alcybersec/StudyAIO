"""Pipeline stage 0: Ingest — receive file, hash, dedup, create artifact."""

from datetime import datetime

import structlog

from app.core.database import async_session_factory, run_async
from app.core.exceptions import DuplicateFileError
from app.core.utils import generate_id
from app.models.pipeline_run import PipelineRun
from app.services import artifact_service
from app.services.event_service import publish_pipeline_event_sync
from app.worker import celery_app

logger = structlog.get_logger()


async def _ingest(file_path: str) -> dict:
    """Async ingest implementation."""
    async with async_session_factory() as session:
        # Create pipeline run record
        run = PipelineRun(
            id=generate_id(),
            artifact_id="pending",  # will be updated after artifact creation
            stage="ingest",
            status="running",
            started_at=datetime.utcnow(),
        )

        try:
            artifact = await artifact_service.ingest_file(session, file_path)

            # Update pipeline run with real artifact_id
            run.artifact_id = artifact.id
            run.status = "completed"
            run.completed_at = datetime.utcnow()
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
                "status": "ingested",
                "filename": artifact.original_filename,
                "sha256": artifact.sha256,
            }

        except DuplicateFileError as e:
            logger.info("ingest_stage_duplicate", sha256=e.sha256)
            return {
                "artifact_id": e.existing_artifact_id,
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
def ingest_file(self, file_path: str) -> dict:
    """Celery task: ingest a file into the pipeline.

    Args:
        file_path: Absolute path to the file to ingest.

    Returns:
        Dict with artifact_id, status, filename, sha256.
    """
    logger.info("ingest_task_started", file_path=file_path)
    publish_pipeline_event_sync("pending", "ingest", "started")
    try:
        result = run_async(_ingest(file_path))
        artifact_id = result.get("artifact_id", "unknown")
        publish_pipeline_event_sync(artifact_id, "ingest", result.get("status", "completed"))
        return result
    except (DuplicateFileError, FileNotFoundError, ValueError):
        raise  # Don't retry on expected errors
    except Exception as exc:
        logger.error("ingest_task_error", error=str(exc))
        publish_pipeline_event_sync("unknown", "ingest", "failed", str(exc))
        raise self.retry(exc=exc) from exc
