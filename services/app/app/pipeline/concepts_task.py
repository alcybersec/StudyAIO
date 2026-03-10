"""Standalone Celery task for on-demand concept extraction."""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.database import async_session_factory, run_async
from app.models.artifact import LectureArtifact
from app.models.extraction import Extraction
from app.services.summary_service import merge_extractions
from app.worker import celery_app

logger = structlog.get_logger()


async def _extract_concepts_for_artifact(artifact_id: str, user_id: str | None = None) -> dict:
    """Extract concepts from a single artifact.

    Args:
        artifact_id: UUID of the artifact.
        user_id: Owner user ID (optional, falls back to artifact.user_id).

    Returns:
        Dict with artifact_id, concept_count, relation_count.
    """
    from app.agents import parsing
    from app.services import concept_service

    async with async_session_factory() as session:
        # Load artifact + course
        result = await session.execute(
            select(LectureArtifact)
            .options(joinedload(LectureArtifact.course))
            .where(LectureArtifact.id == artifact_id)
        )
        artifact = result.unique().scalar_one_or_none()
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        if not artifact.course_id or artifact.week is None:
            raise ValueError(f"Artifact {artifact_id} not classified")

        effective_user_id = user_id or artifact.user_id

        # Load extraction text
        ext_result = await session.execute(
            select(Extraction).where(Extraction.artifact_id == artifact_id)
        )
        extraction = ext_result.scalar_one_or_none()
        if not extraction:
            raise ValueError(f"No extraction found for artifact {artifact_id}")

        extraction_data = merge_extractions([extraction])
        extraction_text = parsing.build_extraction_text(extraction_data)

        result = await concept_service.extract_and_save_concepts(
            session=session,
            artifact_id=artifact_id,
            user_id=effective_user_id,
            course_id=artifact.course_id,
            week=artifact.week,
            extraction_text=extraction_text,
        )

        return {
            "artifact_id": artifact_id,
            "concept_count": result["concept_count"],
            "relation_count": result["relation_count"],
        }


@celery_app.task(
    name="app.pipeline.concepts_task.extract_concepts",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def extract_concepts(self, artifact_id: str, user_id: str | None = None) -> dict:
    """Celery task: extract concepts from an artifact on demand.

    Args:
        artifact_id: Artifact UUID.
        user_id: Optional owner user ID.

    Returns:
        Dict with artifact_id, concept_count, relation_count.
    """
    logger.info("concept_extraction_started", artifact_id=artifact_id)
    try:
        return run_async(_extract_concepts_for_artifact(artifact_id, user_id))
    except Exception as exc:
        logger.error("concept_extraction_failed", error=str(exc), artifact_id=artifact_id)
        raise self.retry(exc=exc) from exc
