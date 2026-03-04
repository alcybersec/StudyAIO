"""Pipeline stage 2: Extract — full content extraction with images."""

from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select

from app.config import settings
from app.core.database import async_session_factory, run_async
from app.core.exceptions import ExtractionError
from app.core.utils import generate_id
from app.extractors import get_extractor
from app.models.artifact import LectureArtifact
from app.models.extraction import Extraction
from app.models.pipeline_run import PipelineRun
from app.services.event_service import publish_pipeline_event_sync
from app.worker import celery_app

logger = structlog.get_logger()


async def _extract(artifact_id: str, user_id: str | None = None) -> dict:
    """Async extract implementation."""
    async with async_session_factory() as session:
        # Load artifact
        result = await session.execute(
            select(LectureArtifact).where(LectureArtifact.id == artifact_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            raise ExtractionError(f"Artifact {artifact_id} not found")

        # Check for existing extraction (idempotency)
        existing = await session.execute(
            select(Extraction).where(Extraction.artifact_id == artifact_id)
        )
        if existing.scalar_one_or_none():
            logger.info("extract_already_exists", artifact_id=artifact_id)
            artifact.status = "extracted"
            await session.commit()
            return {
                "artifact_id": artifact_id,
                "user_id": user_id or artifact.user_id,
                "status": "already_extracted",
            }

        # Update status
        artifact.status = "extracting"
        await session.commit()

        # Create pipeline run
        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact_id,
            stage="extract",
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.flush()

        try:
            # Set up output directory
            extraction_dir = Path(settings.extractions_dir) / artifact_id
            extraction_dir.mkdir(parents=True, exist_ok=True)

            # Run appropriate extractor
            extractor = get_extractor(artifact.file_type)
            extraction_result = extractor.extract(
                file_path=Path(artifact.file_path),
                output_dir=extraction_dir,
            )

            # Create extraction record
            manifest = extraction_result.to_manifest()
            extraction = Extraction(
                id=generate_id(),
                artifact_id=artifact_id,
                manifest_json=manifest,
                image_count=extraction_result.image_count,
                page_count=extraction_result.page_count,
                extraction_path=str(extraction_dir),
            )
            session.add(extraction)

            # Update artifact status
            artifact.status = "extracted"

            # Update pipeline run
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            if run.started_at:
                delta = run.completed_at - run.started_at
                run.duration_ms = int(delta.total_seconds() * 1000)

            await session.commit()

            logger.info(
                "extract_stage_completed",
                artifact_id=artifact_id,
                pages=extraction_result.page_count,
                images=extraction_result.image_count,
            )

            return {
                "artifact_id": artifact_id,
                "user_id": user_id or artifact.user_id,
                "status": "extracted",
                "page_count": extraction_result.page_count,
                "image_count": extraction_result.image_count,
                "extraction_path": str(extraction_dir),
            }

        except ExtractionError as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            artifact.status = "failed"
            await session.commit()
            raise

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            artifact.status = "failed"
            await session.commit()
            raise ExtractionError(f"Extraction failed: {e}") from e


@celery_app.task(
    name="app.pipeline.extract.extract_artifact",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def extract_artifact(self, input_value: str | dict) -> dict:
    """Celery task: extract content from a classified artifact.

    Accepts either a plain artifact_id string or a dict from the
    previous pipeline stage (for chain compatibility).

    Args:
        input_value: Artifact UUID string or dict with artifact_id.

    Returns:
        Dict with artifact_id, status, page_count, image_count, extraction_path.
    """
    # Resolve input (chain compatibility)
    user_id = None
    if isinstance(input_value, dict):
        status = input_value.get("status", "")
        if status in ("duplicate", "waiting_review", "failed"):
            logger.info(
                "extract_task_skipped",
                status=status,
                artifact_id=input_value.get("artifact_id"),
            )
            return input_value
        artifact_id = input_value.get("artifact_id", "")
        user_id = input_value.get("user_id")
    else:
        artifact_id = input_value

    if not artifact_id:
        raise ExtractionError("No artifact_id provided")

    logger.info("extract_task_started", artifact_id=artifact_id, user_id=user_id)
    publish_pipeline_event_sync(artifact_id, "extract", "started")
    try:
        result = run_async(_extract(artifact_id, user_id=user_id))
        publish_pipeline_event_sync(artifact_id, "extract", result.get("status", "completed"))
        return result
    except ExtractionError:
        publish_pipeline_event_sync(artifact_id, "extract", "failed")
        raise  # Don't retry on extraction errors
    except Exception as exc:
        logger.error("extract_task_error", error=str(exc), artifact_id=artifact_id)
        publish_pipeline_event_sync(artifact_id, "extract", "failed", str(exc))
        raise self.retry(exc=exc) from exc
