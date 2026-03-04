"""Business logic for pipeline activity queries."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.pipeline_run import PipelineRun

logger = structlog.get_logger()


async def get_recent_activity(
    session: AsyncSession, limit: int = 10, user_id: str | None = None
) -> list[dict]:
    """Get recent pipeline completions for the dashboard.

    Args:
        session: Database session.
        limit: Max results to return.

    Returns:
        List of dicts with artifact info and latest pipeline stage status.
    """
    from app.models.artifact import LectureArtifact

    query = (
        select(PipelineRun)
        .options(joinedload(PipelineRun.artifact))
        .join(LectureArtifact, PipelineRun.artifact_id == LectureArtifact.id)
    )
    if user_id:
        query = query.where(LectureArtifact.user_id == user_id)
    query = query.order_by(PipelineRun.started_at.desc()).limit(limit)

    result = await session.execute(query)
    runs = result.unique().scalars().all()

    activity = []
    for run in runs:
        artifact = run.artifact
        activity.append(
            {
                "pipeline_run_id": run.id,
                "artifact_id": run.artifact_id,
                "filename": artifact.original_filename if artifact else None,
                "stage": run.stage,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_ms": run.duration_ms,
            }
        )

    return activity


async def get_artifact_pipeline_runs(session: AsyncSession, artifact_id: str) -> list[PipelineRun]:
    """Get all pipeline runs for a given artifact.

    Args:
        session: Database session.
        artifact_id: Artifact UUID.

    Returns:
        List of PipelineRun records ordered by start time.
    """
    result = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.artifact_id == artifact_id)
        .order_by(PipelineRun.started_at.asc())
    )
    return list(result.scalars().all())
