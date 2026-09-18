"""Pipeline stage 0: Ingest — receive file, hash, dedup, create artifact."""

from datetime import UTC, datetime

import structlog

from app.core.database import async_session_factory, run_async
from app.core.exceptions import DuplicateFileError
from app.core.utils import generate_id
from app.models.pipeline_run import PipelineRun
from app.pipeline.failures import record_stage_failure
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
        # `pipeline_runs.artifact_id` is a NOT NULL foreign key, so the run row
        # cannot exist before the artifact row does — which is also why this run
        # is not inserted up front the way the other five stages insert theirs:
        # the placeholder above would fail that constraint. Uploads always pass
        # a committed artifact id (`api/uploads.py` creates the row so it can
        # return a real id, then dispatches), so the failure an operator
        # actually hits is recordable. A caller that lets ingest create the
        # artifact has nothing to attach a run to until `ingest_file` returns.
        recordable_artifact_id = artifact_id

        try:
            artifact = await artifact_service.ingest_file(
                session, file_path, user_id=user_id or "", artifact_id=artifact_id
            )

            # Update pipeline run with real artifact_id
            recordable_artifact_id = artifact.id
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
            # Deliberately records no PipelineRun (#103). A duplicate is not a
            # failed run and not work performed: the only artifact involved is
            # the one ingested earlier, and the FK would force the row onto it.
            # `pipeline_runs` is read as "what the pipeline did to this
            # artifact", so an ingest run stamped now, after that artifact's own
            # extract/summarize/index runs, would describe a re-ingest that
            # never happened. The duplicate is already visible: the existing
            # artifact row, this log line, and the `duplicate` status the task
            # publishes. Provenance for a rejected re-upload belongs to the
            # upload attempt, not to the earlier artifact's stage history.
            logger.info("ingest_stage_duplicate", sha256=e.sha256)
            return {
                "artifact_id": e.existing_artifact_id,
                "user_id": user_id,
                "status": "duplicate",
                "sha256": e.sha256,
            }

        except Exception as e:
            logger.error("ingest_stage_failed", error=str(e), file_path=file_path)
            if recordable_artifact_id:
                # Rolls back first, then (re-)creates the run row and marks the
                # artifact failed. The rollback is needed here too: ingest's
                # failure can arrive on a session already marked for rollback,
                # since both the artifact INSERT inside `ingest_file` and the
                # run INSERT above can fail at flush time — after which every
                # further statement on this session, `commit()` included, raises
                # `PendingRollbackError`.
                await record_stage_failure(
                    session, run=run, artifact_id=recordable_artifact_id, error=e
                )
            else:
                # No artifact row yet, so the NOT NULL FK leaves nowhere to put
                # the run. Say so rather than silently recording nothing.
                logger.warning(
                    "ingest_failure_not_recorded",
                    reason="ingest failed before any artifact row existed",
                    file_path=file_path,
                    user_id=user_id,
                )
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
    publish_pipeline_event_sync(
        known_artifact_id or "pending", "ingest", "started", user_id=user_id
    )
    try:
        result = run_async(_ingest(file_path, user_id=user_id, artifact_id=known_artifact_id))
        artifact_id = result.get("artifact_id") or known_artifact_id or "unknown"
        publish_pipeline_event_sync(
            artifact_id, "ingest", result.get("status", "completed"), user_id=user_id
        )
        return result
    except (DuplicateFileError, FileNotFoundError, ValueError):
        raise  # Don't retry on expected errors
    except Exception as exc:
        # The exception text stays operator-side: it can carry storage paths
        # and filenames, and the published event goes to a client.
        logger.error(
            "ingest_task_error",
            error=str(exc),
            artifact_id=known_artifact_id,
            file_path=file_path,
            user_id=user_id,
        )
        publish_pipeline_event_sync(
            known_artifact_id or "unknown", "ingest", "failed", user_id=user_id
        )
        raise self.retry(exc=exc) from exc
