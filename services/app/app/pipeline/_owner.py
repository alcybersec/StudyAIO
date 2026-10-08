"""Owner resolution for the row-owner pipeline stages (floor 1, C6).

A stage loads the artifact row and acts for ``artifact.user_id`` — credentials,
billing, course resolution. The Celery payload's ``user_id`` is advisory: if it
disagrees with the row, the row wins and the disagreement is logged.
"""

import structlog

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
