"""Pipeline stage 3: Summarize — generate weekly markdown summaries."""

import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.agents.factory import get_agent
from app.core.database import async_session_factory, run_async
from app.core.exceptions import AgentError, SummarizationError
from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.pipeline_run import PipelineRun
from app.services import summary_service
from app.services.event_service import publish_pipeline_event_sync
from app.worker import celery_app

logger = structlog.get_logger()


async def _summarize(artifact_id: str, user_id: str | None = None) -> dict:
    """Async summarize implementation.

    Args:
        artifact_id: UUID of the artifact to summarize.
        user_id: Owner user UUID.

    Returns:
        Dict with artifact_id, status, summary file path.

    Raises:
        SummarizationError: If summarization fails.
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
            raise SummarizationError(f"Artifact {artifact_id} not found")

        # Verify artifact is classified
        if not artifact.course_id or artifact.week is None:
            raise SummarizationError(
                f"Artifact {artifact_id} not classified (missing course_id or week)"
            )

        course = artifact.course
        if not course:
            raise SummarizationError(f"Artifact {artifact_id} has course_id but course not found")

        # Update status
        artifact.status = "summarizing"
        await session.commit()

        # Create pipeline run
        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact_id,
            stage="summarize",
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()

        try:
            # Get all extractions for this course+week
            extractions = await summary_service.get_week_extractions(
                session, artifact.course_id, artifact.week
            )
            if not extractions:
                raise SummarizationError(
                    f"No extractions found for {course.code} week {artifact.week}"
                )

            # Merge extractions into single ExtractionData
            extraction_data = summary_service.merge_extractions(extractions)

            # Inject course_code and week into metadata for the agent
            extraction_data.metadata["course_code"] = course.code
            extraction_data.metadata["week"] = artifact.week

            # Check for existing summary (for update)
            existing = await summary_service.get_existing_summary(
                session, artifact.course_id, artifact.week
            )
            existing_md = existing.content_md if existing else None

            # Call AI agent with per-user settings
            from app.services.settings_service import get_user_agent_config

            user_agent_config = await get_user_agent_config(session, user_id or artifact.user_id)
            agent = get_agent(user_settings=user_agent_config)
            summary_result = await agent.generate_summary(extraction_data, existing_md)

            # Persist refreshed CLI credentials if applicable
            if hasattr(agent, "refreshed_credentials") and agent.refreshed_credentials:
                try:
                    from app.services.settings_service import update_user_settings

                    await update_user_settings(
                        session,
                        user_id or artifact.user_id,
                        {"claude_cli_credentials": json.dumps(agent.refreshed_credentials)},
                    )
                except Exception:
                    logger.warning("credential_refresh_persist_failed", exc_info=True)

            # Write summary to storage
            storage = get_storage()
            storage_key = summary_service.build_summary_storage_key(course.code, artifact.week)
            await storage.put(storage_key, summary_result.content_md.encode("utf-8"))

            # Collect source artifact IDs from the merged extraction
            source_artifact_ids = extraction_data.metadata.get("artifact_ids", [artifact_id])

            # Create or update summary in database
            summary = await summary_service.create_or_update_summary(
                session=session,
                course_id=artifact.course_id,
                week=artifact.week,
                content_md=summary_result.content_md,
                file_path=storage_key,
                source_artifact_ids=source_artifact_ids,
            )

            # Update artifact status
            artifact.status = "summarized"

            # Update pipeline run
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            if run.started_at:
                delta = run.completed_at - run.started_at
                run.duration_ms = int(delta.total_seconds() * 1000)

            await session.commit()

            logger.info(
                "summarize_stage_completed",
                artifact_id=artifact_id,
                course=course.code,
                week=artifact.week,
                summary_id=summary.id,
                version=summary.version,
                file_path=storage_key,
            )

            return {
                "artifact_id": artifact_id,
                "user_id": user_id or artifact.user_id,
                "status": "summarized",
                "summary_id": summary.id,
                "version": summary.version,
                "file_path": storage_key,
            }

        except (SummarizationError, AgentError) as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(UTC)
            artifact.status = "failed"
            await session.commit()
            raise

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(UTC)
            artifact.status = "failed"
            await session.commit()
            raise SummarizationError(f"Summarization failed: {e}") from e


@celery_app.task(
    name="app.pipeline.summarize.summarize_artifact",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def summarize_artifact(self, input_value: str | dict) -> dict:
    """Celery task: generate summary for an artifact's course+week.

    Accepts either a plain artifact_id string or a dict from the
    previous pipeline stage (for chain compatibility).

    Args:
        input_value: Artifact UUID string or dict with artifact_id.

    Returns:
        Dict with artifact_id, status, summary_id, version, file_path.
    """
    # Resolve input (chain compatibility)
    user_id = None
    if isinstance(input_value, dict):
        status = input_value.get("status", "")
        if status in ("duplicate", "waiting_review", "failed"):
            logger.info(
                "summarize_task_skipped",
                status=status,
                artifact_id=input_value.get("artifact_id"),
            )
            return input_value
        artifact_id = input_value.get("artifact_id", "")
        user_id = input_value.get("user_id")
    else:
        artifact_id = input_value

    if not artifact_id:
        raise SummarizationError("No artifact_id provided")

    logger.info("summarize_task_started", artifact_id=artifact_id, user_id=user_id)
    publish_pipeline_event_sync(artifact_id, "summarize", "started")
    try:
        result = run_async(_summarize(artifact_id, user_id=user_id))
        publish_pipeline_event_sync(artifact_id, "summarize", result.get("status", "completed"))
        return result
    except (SummarizationError, AgentError):
        publish_pipeline_event_sync(artifact_id, "summarize", "failed")
        raise  # Don't retry on summarization/agent errors
    except Exception as exc:
        logger.error("summarize_task_error", error=str(exc), artifact_id=artifact_id)
        publish_pipeline_event_sync(artifact_id, "summarize", "failed", str(exc))
        raise self.retry(exc=exc) from exc
