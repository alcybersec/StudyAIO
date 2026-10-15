"""Recording a stage's failure on a session the failure has already poisoned (#93).

Every pipeline stage has the same shape. It commits an in-progress status, opens
a `PipelineRun` with `session.add(run)` + `session.flush()`, does the work, and
on failure writes two terminal rows — `run.status = "failed"` and
`artifact.status = "failed"` — before raising its own typed error. That last
write is what six stages got wrong, in identical fashion:

    except Exception as e:
        run.status = "failed"
        artifact.status = "failed"
        await session.commit()            # <- on a session marked for rollback
        raise IndexingError(...) from e   # <- therefore never reached

Two things make the correct sequence more than a one-liner.

**1. The session may already be marked for rollback.** A flush-time failure —
an `IntegrityError`, or a `DataError` from a value too long for its column —
puts SQLAlchemy into "pending rollback": every subsequent statement on that
session, `commit()` included, raises `PendingRollbackError`. So the handler's
bookkeeping dies *before* its `raise`, the typed error is replaced by
`PendingRollbackError`, and the caller's `except IndexingError` — the one
commented "Don't retry on indexing errors" — stops matching. The task then
retries a deterministic failure, and the terminal rows never land: the artifact
sits at whatever the last commit left it on (`"indexing"`, `"classifying"`, …)
with no `pipeline_runs` row to explain why.

**2. `rollback()` alone is not enough.** The `PipelineRun` was inserted by a
`flush()` *inside* the transaction being rolled back, so the rollback un-inserts
the row and expunges the object back to transient — re-using it, or fetching it
by id, finds nothing. The artifact was committed earlier so its row survives,
but `rollback()` expires the instance regardless of `expire_on_commit`, so the
next attribute touch re-selects it. Guessing at which objects survive in which
state is why PR #54 looked at this code and deliberately left it alone.

Hence the order below: read the identifiers off the ORM objects *first*, while
doing so still needs no SQL; roll back; then re-materialise both rows in the
clean transaction and commit.

A stage's `except` blocks keep raising their own typed errors — this module only
owns the transaction handling, not the error taxonomy.
"""

import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.course_document import CourseDocument
from app.models.pipeline_run import PipelineRun

logger = structlog.get_logger()

FAILED = "failed"


@contextlib.asynccontextmanager
async def _clean_transaction(
    session: AsyncSession, *, stage: str, subject: str
) -> AsyncIterator[None]:
    """Discard whatever the failure left behind, run the body, commit.

    The `rollback()` is unconditional on purpose. When the stage failed at flush
    time it is the only thing that will un-wedge the session; when the stage
    failed for some other reason it discards work that must not be committed
    alongside a `"failed"` status anyway (pre-fix, a stage that raised partway
    through `index_artifact_chunks` committed the chunks it had managed to add).

    Failures *inside* the body are logged and swallowed — an `@asynccontextmanager`
    generator that catches the exception thrown in at its `yield` and returns
    suppresses it. That is deliberate: the caller raises its own typed error
    immediately after this returns, and letting a bookkeeping problem replace
    that error is precisely the bug this module exists to remove. The stage
    still fails; it just fails with the exception that explains why.
    """
    try:
        await session.rollback()
        yield
        await session.commit()
    except Exception:
        logger.exception(
            "pipeline_failure_not_recorded",
            stage=stage,
            subject=subject,
        )
        # Leave the session usable for the `async with` exit, but never let this
        # rollback's own failure escape either.
        with contextlib.suppress(Exception):
            await session.rollback()


async def record_stage_failure(
    session: AsyncSession,
    *,
    run: PipelineRun,
    artifact_id: str,
    error: BaseException,
    retrying: bool = False,
) -> None:
    """Mark a pipeline stage failed: the `PipelineRun` row and the artifact.

    Args:
        session: The stage's session. May be marked for rollback; that is the
            whole point. It is left committed and usable on return.
        run: The `PipelineRun` the stage opened. Read for its identifiers only —
            the instance itself is not reused, because the rollback invalidates it.
        artifact_id: The artifact to move to `"failed"`.
        error: The exception the stage is about to raise, recorded as
            `run.error_message`.
        retrying: The error is transient and the task will retry (GL#22). The
            run is still recorded as failed, but the artifact keeps its
            in-progress status; the final attempt fails it.
    """
    # Read these *before* the rollback, and without SQL: on a session marked for
    # rollback any statement raises PendingRollbackError. A run that was only
    # flushed is transient after the failure and keeps its attributes. A run the
    # stage committed before a provider call (GL#50, `release_connection`) is
    # persistent, and the failed flush's internal rollback has expired it, so its
    # attributes cannot be read; its identity still can, and the row itself
    # (committed) supplies `stage`/`started_at` once the session is clean.
    state = sa_inspect(run)
    loaded = state.dict
    run_id = state.identity[0] if state.identity else loaded.get("id")
    stage = loaded.get("stage")
    started_at = loaded.get("started_at")
    message = str(error)

    async with _clean_transaction(session, stage=stage or "unknown", subject=artifact_id):
        # The committed run (see above), or normally gone: the run's INSERT was in
        # the rolled-back transaction.
        failed_run = await session.get(PipelineRun, run_id)
        if failed_run is None:
            failed_run = PipelineRun(
                id=run_id,
                artifact_id=artifact_id,
                stage=stage,
                started_at=started_at,
            )
            session.add(failed_run)
        else:
            started_at = failed_run.started_at

        completed_at = datetime.now(UTC)
        failed_run.status = FAILED
        failed_run.error_message = message
        failed_run.completed_at = completed_at
        if started_at is not None:
            failed_run.duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # Re-fetch rather than reuse the caller's instance: the rollback expired it.
        artifact = await session.get(LectureArtifact, artifact_id)
        if artifact is not None and not retrying:
            artifact.status = FAILED


async def record_stage_event(
    artifact_id: str,
    stage: str,
    status: str,
    message: str,
    *,
    artifact_status: str | None = None,
) -> None:
    """Write a standalone `PipelineRun` row from a fresh session.

    For events no stage session can record: a time limit that killed the
    transaction, retries running out, the recovery job. Optionally moves the
    artifact to ``artifact_status``.

    Args:
        artifact_id: Artifact the event belongs to.
        stage: Stage name (at most 30 characters).
        status: Run status to record (``failed``, ``recovered``, ...).
        message: Stored as `error_message`. Callers pass redacted text only.
        artifact_status: If given, the artifact's new status.
    """
    from app.core.database import async_session_factory

    now = datetime.now(UTC)
    async with async_session_factory() as session:
        session.add(
            PipelineRun(
                artifact_id=artifact_id,
                stage=stage,
                status=status,
                error_message=message,
                started_at=now,
                completed_at=now,
                duration_ms=0,
            )
        )
        if artifact_status is not None:
            artifact = await session.get(LectureArtifact, artifact_id)
            if artifact is not None:
                artifact.status = artifact_status
        await session.commit()


async def record_document_failure(
    session: AsyncSession,
    *,
    document_id: str,
    error: BaseException,
) -> None:
    """Mark a `CourseDocument` failed.

    `courseops_task` is not one of the six chained stages and opens no
    `PipelineRun`, but its handler has the same `commit()`-on-a-poisoned-session
    shape and the same consequence: the document sticks at `"processing"` and
    `PendingRollbackError` escapes in place of `CourseOpsError`, so the task
    retries.

    Args:
        session: The task's session. May be marked for rollback.
        document_id: The `CourseDocument` to move to `"failed"`.
        error: The exception the task is about to raise. Logged, not stored —
            `course_documents` has no error column.
    """
    async with _clean_transaction(session, stage="courseops", subject=document_id):
        document = await session.get(CourseDocument, document_id)
        if document is not None:
            document.status = FAILED
            logger.info(
                "courseops_document_failed",
                document_id=document_id,
                error=str(error),
            )
