"""Recover artifacts stuck in an in-progress state (TECH-04, GL#22).

A worker killed mid-stage (OOM, deploy, hard time limit) leaves its artifact at
`classifying` / `summarizing` / ... forever: nothing is running and nothing will.
A beat job finds them and requeues the stage, a bounded number of times, then
marks the artifact failed with a visible `pipeline_runs` row.

Worker-only: this module is a Celery beat task over all users' artifacts and is
not reachable from any request. Requeueing passes the artifact's own `user_id`
down the chain; the stages are idempotent, so a requeue is safe.
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select

from app.core.database import async_session_factory, run_async
from app.models.artifact import LectureArtifact
from app.models.pipeline_run import PipelineRun
from app.pipeline.resilience import STUCK_THRESHOLD_SECONDS, count_metric
from app.worker import celery_app

logger = structlog.get_logger()

#: in-progress artifact status -> stage to resume from.
IN_PROGRESS_STAGES: dict[str, str] = {
    "classifying": "classify",
    "extracting": "extract",
    "summarizing": "summarize",
    "indexing": "index",
    "generating_assets": "assets",
}

RECOVERY_STAGE = "recovery"
MAX_RECOVERY_ATTEMPTS = 3
BATCH_LIMIT = 100


async def _recover(now: datetime | None = None) -> dict:
    """Requeue or fail every artifact stuck past the threshold.

    Args:
        now: Clock override for tests.

    Returns:
        Dict with ``requeued`` and ``failed`` artifact id lists.
    """
    from app.pipeline.orchestrator import resume_pipeline

    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=STUCK_THRESHOLD_SECONDS)
    requeued: list[str] = []
    failed: list[str] = []
    dispatch: list[tuple[str, str, str]] = []

    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(LectureArtifact)
                    .where(
                        LectureArtifact.status.in_(list(IN_PROGRESS_STAGES)),
                        LectureArtifact.updated_at < cutoff,
                    )
                    .order_by(LectureArtifact.updated_at)
                    .limit(BATCH_LIMIT)
                    # A second beat tick (or worker) skips rows being handled.
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for artifact in rows:
            stage = IN_PROGRESS_STAGES[artifact.status]
            attempts = (
                await session.execute(
                    select(func.count())
                    .select_from(PipelineRun)
                    .where(
                        PipelineRun.artifact_id == artifact.id,
                        PipelineRun.stage == RECOVERY_STAGE,
                    )
                )
            ).scalar_one()
            stuck_minutes = int((now - artifact.updated_at).total_seconds() // 60)
            if attempts >= MAX_RECOVERY_ATTEMPTS:
                message = (
                    f"stuck in {artifact.status} for {stuck_minutes} min; "
                    f"gave up after {attempts} recovery attempts"
                )
                session.add(
                    PipelineRun(
                        artifact_id=artifact.id,
                        stage=RECOVERY_STAGE,
                        status="failed",
                        error_message=message,
                        started_at=now,
                        completed_at=now,
                        duration_ms=0,
                    )
                )
                artifact.status = "failed"
                failed.append(artifact.id)
                count_metric("pipeline_recovery_failed_total", stage=stage)
                logger.error(
                    "pipeline_recovery_gave_up",
                    artifact_id=artifact.id,
                    stage=stage,
                    attempts=attempts,
                )
            else:
                session.add(
                    PipelineRun(
                        artifact_id=artifact.id,
                        stage=RECOVERY_STAGE,
                        status="recovered",
                        error_message=(
                            f"stuck in {artifact.status} for {stuck_minutes} min; "
                            f"requeued {stage} (attempt {attempts + 1}/{MAX_RECOVERY_ATTEMPTS})"
                        ),
                        started_at=now,
                        completed_at=now,
                        duration_ms=0,
                    )
                )
                # Push updated_at forward so the next tick does not re-pick it
                # while the requeued stage is still queued.
                artifact.updated_at = now
                requeued.append(artifact.id)
                dispatch.append((artifact.id, stage, artifact.user_id))
                count_metric("pipeline_recovery_requeued_total", stage=stage)
                logger.warning(
                    "pipeline_recovery_requeued",
                    artifact_id=artifact.id,
                    stage=stage,
                    attempt=attempts + 1,
                    stuck_minutes=stuck_minutes,
                )
        await session.commit()

    # After the commit: a dispatched stage must find the committed state.
    for artifact_id, stage, owner_id in dispatch:
        try:
            resume_pipeline(artifact_id, from_stage=stage, user_id=owner_id)
        except Exception:
            logger.error(
                "pipeline_recovery_dispatch_failed", artifact_id=artifact_id, exc_info=True
            )
    return {"requeued": requeued, "failed": failed}


@celery_app.task(name="app.pipeline.recovery.recover_stuck_artifacts")
def recover_stuck_artifacts() -> dict:
    """Celery beat task: requeue or fail artifacts stuck in an in-progress state."""
    result = run_async(_recover())
    logger.info(
        "pipeline_recovery_tick",
        requeued=len(result["requeued"]),
        failed=len(result["failed"]),
    )
    return result
