"""Owner resolution for the row-owner pipeline stages (floor 1, C6).

A stage loads the artifact row and acts for ``artifact.user_id`` — credentials,
billing, course resolution. The Celery payload's ``user_id`` is advisory: if it
disagrees with the row, the row wins and the disagreement is logged.
"""

import structlog
from sqlalchemy import select

from app.core.database import async_session_factory, run_async
from app.models.artifact import LectureArtifact

logger = structlog.get_logger()


def warn_on_owner_mismatch(
    stage: str, artifact_id: str, row_owner: str, payload_owner: str | None
) -> None:
    """Log a warning when the payload names a different owner than the row.

    Args:
        stage: Pipeline stage name.
        artifact_id: Artifact UUID.
        row_owner: ``artifact.user_id`` (authoritative).
        payload_owner: ``user_id`` carried by the Celery payload, if any.
    """
    if payload_owner and str(payload_owner) != str(row_owner):
        logger.warning(
            "pipeline_owner_mismatch",
            stage=stage,
            artifact_id=artifact_id,
            row_owner=str(row_owner),
            payload_owner=str(payload_owner),
        )


async def _row_owner_async(artifact_id: str) -> str | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(LectureArtifact.user_id).where(LectureArtifact.id == artifact_id)
        )
        return result.scalar_one_or_none()


def _row_owner(artifact_id: str) -> str | None:
    """Return ``artifact.user_id`` for an artifact id, or ``None`` if unknown."""
    return run_async(_row_owner_async(artifact_id))


def resolve_event_owner(stage: str, artifact_id: str, payload_owner: str | None) -> str | None:
    """Resolve whose SSE channel a pipeline event for this artifact belongs to.

    The artifact row's owner wins over the Celery payload, matching what the
    stages themselves act as. Fails closed: a missing row or a failed lookup
    returns ``None``, and the publisher drops events with no owner, so the
    payload user is never used as a guess for a row that is not known to be theirs.

    Args:
        stage: Pipeline stage name (for the mismatch log).
        artifact_id: Artifact UUID.
        payload_owner: ``user_id`` carried by the Celery payload, if any.

    Returns:
        The row owner's id as a string, or ``None`` when it cannot be determined.
    """
    try:
        owner = _row_owner(artifact_id)
    except Exception as exc:
        logger.warning(
            "pipeline_event_owner_lookup_failed",
            stage=stage,
            artifact_id=artifact_id,
            error=str(exc),
        )
        return None
    if owner is None:
        logger.warning("pipeline_event_owner_unknown", stage=stage, artifact_id=artifact_id)
        return None
    warn_on_owner_mismatch(stage, artifact_id, owner, payload_owner)
    return str(owner)
