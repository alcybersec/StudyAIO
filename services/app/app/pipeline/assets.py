"""Pipeline stage 5: Assets — generate flashcards and quiz questions."""

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.agents.factory import get_agent
from app.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import AgentError, AssetGenerationError
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.extraction import Extraction
from app.models.pipeline_run import PipelineRun
from app.models.summary import Summary
from app.services import asset_service
from app.services.event_service import publish_pipeline_event_sync
from app.services.summary_service import merge_extractions
from app.worker import celery_app

logger = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _generate_assets(artifact_id: str) -> dict:
    """Async asset generation implementation.

    Args:
        artifact_id: UUID of the artifact to generate assets for.

    Returns:
        Dict with artifact_id, status, flashcard_count, quiz_count.

    Raises:
        AssetGenerationError: If asset generation fails.
    """
    async with async_session_factory() as session:
        # Load artifact with course relationship
        result = await session.execute(
            select(LectureArtifact)
            .options(joinedload(LectureArtifact.course))
            .where(LectureArtifact.id == artifact_id)
        )
        artifact = result.unique().scalar_one_or_none()
        if not artifact:
            raise AssetGenerationError(f"Artifact {artifact_id} not found")

        if not artifact.course_id or artifact.week is None:
            raise AssetGenerationError(
                f"Artifact {artifact_id} not classified (missing course_id or week)"
            )

        course = artifact.course
        if not course:
            raise AssetGenerationError(
                f"Artifact {artifact_id} has course_id but course not found"
            )

        # Update status
        artifact.status = "generating_assets"
        await session.commit()

        # Create pipeline run
        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact_id,
            stage="assets",
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.flush()

        try:
            # Load extraction
            ext_result = await session.execute(
                select(Extraction).where(Extraction.artifact_id == artifact_id)
            )
            extraction = ext_result.scalar_one_or_none()
            if not extraction:
                raise AssetGenerationError(
                    f"No extraction found for artifact {artifact_id}"
                )

            extraction_data = merge_extractions([extraction])
            extraction_data.metadata["course_code"] = course.code
            extraction_data.metadata["week"] = artifact.week

            # Load summary (optional — pass empty string if missing)
            summary_result = await session.execute(
                select(Summary).where(
                    Summary.course_id == artifact.course_id,
                    Summary.week == artifact.week,
                )
            )
            summary = summary_result.scalar_one_or_none()
            summary_md = summary.content_md if summary else ""

            # Generate flashcards
            agent = get_agent()
            flashcard_data = await agent.generate_flashcards(
                summary=summary_md,
                extraction=extraction_data,
                count=settings.flashcard_count_per_week,
            )

            flashcards = await asset_service.save_flashcards(
                session=session,
                course_id=artifact.course_id,
                week=artifact.week,
                artifact_id=artifact_id,
                flashcards=flashcard_data,
            )

            # Generate quiz questions
            quiz_data = await agent.generate_quiz(
                summary=summary_md,
                extraction=extraction_data,
                count=settings.quiz_question_count_per_week,
            )

            quiz_questions = await asset_service.save_quiz_questions(
                session=session,
                course_id=artifact.course_id,
                week=artifact.week,
                artifact_id=artifact_id,
                questions=quiz_data,
            )

            # Update artifact status — terminal stage
            artifact.status = "processed"

            # Update pipeline run
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            if run.started_at:
                delta = run.completed_at - run.started_at
                run.duration_ms = int(delta.total_seconds() * 1000)

            await session.commit()

            logger.info(
                "assets_stage_completed",
                artifact_id=artifact_id,
                course=course.code,
                week=artifact.week,
                flashcard_count=len(flashcards),
                quiz_count=len(quiz_questions),
            )

            return {
                "artifact_id": artifact_id,
                "status": "processed",
                "flashcard_count": len(flashcards),
                "quiz_count": len(quiz_questions),
            }

        except (AssetGenerationError, AgentError):
            run.status = "failed"
            run.error_message = str(artifact_id)
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
            raise AssetGenerationError(f"Asset generation failed: {e}") from e


@celery_app.task(
    name="app.pipeline.assets.generate_assets",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_assets(self, input_value: str | dict) -> dict:
    """Celery task: generate flashcards and quiz questions for an artifact.

    Accepts either a plain artifact_id string or a dict from the
    previous pipeline stage (for chain compatibility).

    Args:
        input_value: Artifact UUID string or dict with artifact_id.

    Returns:
        Dict with artifact_id, status, flashcard_count, quiz_count.
    """
    # Resolve input (chain compatibility)
    if isinstance(input_value, dict):
        status = input_value.get("status", "")
        if status in ("duplicate", "waiting_review", "failed"):
            logger.info(
                "assets_task_skipped",
                status=status,
                artifact_id=input_value.get("artifact_id"),
            )
            return input_value
        artifact_id = input_value.get("artifact_id", "")
    else:
        artifact_id = input_value

    if not artifact_id:
        raise AssetGenerationError("No artifact_id provided")

    logger.info("assets_task_started", artifact_id=artifact_id)
    publish_pipeline_event_sync(artifact_id, "assets", "started")
    try:
        result = _run_async(_generate_assets(artifact_id))
        publish_pipeline_event_sync(artifact_id, "assets", result.get("status", "completed"))
        return result
    except (AssetGenerationError, AgentError):
        publish_pipeline_event_sync(artifact_id, "assets", "failed")
        raise  # Don't retry on asset/agent errors
    except Exception as exc:
        logger.error("assets_task_error", error=str(exc), artifact_id=artifact_id)
        publish_pipeline_event_sync(artifact_id, "assets", "failed", str(exc))
        raise self.retry(exc=exc)
