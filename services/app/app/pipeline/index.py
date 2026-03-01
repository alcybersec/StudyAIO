"""Pipeline stage 4: Index — chunk text and generate embeddings."""

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select

from app.agents.embeddings import get_embedding_provider
from app.core.database import async_session_factory
from app.core.exceptions import IndexingError
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.extraction import Extraction
from app.models.pipeline_run import PipelineRun
from app.services import index_service
from app.services.event_service import publish_pipeline_event_sync
from app.worker import celery_app

logger = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _index(artifact_id: str) -> dict:
    """Async index implementation.

    Args:
        artifact_id: UUID of the artifact to index.

    Returns:
        Dict with artifact_id, status, chunk_count.

    Raises:
        IndexingError: If indexing fails.
    """
    async with async_session_factory() as session:
        # Load artifact
        result = await session.execute(
            select(LectureArtifact).where(LectureArtifact.id == artifact_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            raise IndexingError(f"Artifact {artifact_id} not found")

        # Load extraction manifest
        ext_result = await session.execute(
            select(Extraction).where(Extraction.artifact_id == artifact_id)
        )
        extraction = ext_result.scalar_one_or_none()
        if not extraction:
            raise IndexingError(
                f"No extraction found for artifact {artifact_id}. Run extract stage first."
            )

        manifest = extraction.manifest_json
        if not manifest or "pages" not in manifest:
            raise IndexingError(f"Extraction for artifact {artifact_id} has no pages in manifest")

        # Update status
        artifact.status = "indexing"
        await session.commit()

        # Create pipeline run
        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact_id,
            stage="index",
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.flush()

        try:
            # Get embedding provider
            provider = get_embedding_provider()

            # Chunk and embed
            chunks = await index_service.index_artifact_chunks(
                session=session,
                artifact_id=artifact_id,
                sha256=artifact.sha256,
                pages=manifest["pages"],
                embedding_provider=provider,
            )

            # Update artifact status
            artifact.status = "indexed"

            # Update pipeline run
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            if run.started_at:
                delta = run.completed_at - run.started_at
                run.duration_ms = int(delta.total_seconds() * 1000)

            await session.commit()

            logger.info(
                "index_stage_completed",
                artifact_id=artifact_id,
                chunk_count=len(chunks),
            )

            return {
                "artifact_id": artifact_id,
                "status": "indexed",
                "chunk_count": len(chunks),
            }

        except IndexingError as e:
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
            raise IndexingError(f"Indexing failed: {e}") from e


@celery_app.task(
    name="app.pipeline.index.index_artifact",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def index_artifact(self, input_value: str | dict) -> dict:
    """Celery task: chunk and embed an artifact's extraction.

    Accepts either a plain artifact_id string or a dict from the
    previous pipeline stage (for chain compatibility).

    Args:
        input_value: Artifact UUID string or dict with artifact_id.

    Returns:
        Dict with artifact_id, status, chunk_count.
    """
    # Resolve input (chain compatibility)
    if isinstance(input_value, dict):
        status = input_value.get("status", "")
        if status in ("duplicate", "waiting_review", "failed"):
            logger.info(
                "index_task_skipped",
                status=status,
                artifact_id=input_value.get("artifact_id"),
            )
            return input_value
        artifact_id = input_value.get("artifact_id", "")
    else:
        artifact_id = input_value

    if not artifact_id:
        raise IndexingError("No artifact_id provided")

    logger.info("index_task_started", artifact_id=artifact_id)
    publish_pipeline_event_sync(artifact_id, "index", "started")
    try:
        result = _run_async(_index(artifact_id))
        publish_pipeline_event_sync(artifact_id, "index", result.get("status", "completed"))
        return result
    except IndexingError:
        publish_pipeline_event_sync(artifact_id, "index", "failed")
        raise  # Don't retry on indexing errors
    except Exception as exc:
        logger.error("index_task_error", error=str(exc), artifact_id=artifact_id)
        publish_pipeline_event_sync(artifact_id, "index", "failed", str(exc))
        raise self.retry(exc=exc) from exc
