"""API routes for artifact operations (reclassification)."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.exceptions import ArtifactBusyError
from app.models.user import User
from app.pipeline.summarize import summarize_artifact
from app.services import artifact_service

logger = structlog.get_logger()

router = APIRouter()


class ReclassifyRequest(BaseModel):
    """Request body for reclassifying an artifact."""

    course_code: str = Field(..., min_length=1, max_length=20)
    week: int = Field(..., ge=0, le=52)


class ReclassifyResponse(BaseModel):
    """Result of a reclassification."""

    artifact_id: str
    course_code: str
    week: int
    summaries_enqueued: int


@router.post(
    "/artifacts/{artifact_id}/reclassify",
    response_model=ReclassifyResponse,
    summary="Reclassify an artifact",
    description="Moves an artifact (and its flashcards/quiz questions) to a "
    "different course/week and regenerates summaries for both affected weeks. "
    "Returns 409 if the artifact is still processing.",
)
async def reclassify_artifact(
    artifact_id: str,
    body: ReclassifyRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ReclassifyResponse:
    """Reclassify an artifact to another course/week."""
    try:
        result = await artifact_service.reclassify(
            session,
            artifact_id,
            user_id=user.id,
            course_code=body.course_code,
            week=body.week,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ArtifactBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await session.commit()

    # Regenerate summaries for both affected weeks (target + source)
    enqueued = 0
    try:
        summarize_artifact.apply_async(args=[{"artifact_id": artifact_id, "user_id": user.id}])
        enqueued += 1
        if result["source_artifact_id"]:
            summarize_artifact.apply_async(
                args=[{"artifact_id": result["source_artifact_id"], "user_id": user.id}]
            )
            enqueued += 1
    except Exception:
        logger.error("reclassify_summarize_enqueue_failed", artifact_id=artifact_id)

    logger.info(
        "artifact_reclassify_completed",
        artifact_id=artifact_id,
        course_code=body.course_code,
        week=body.week,
        summaries_enqueued=enqueued,
    )

    return ReclassifyResponse(
        artifact_id=artifact_id,
        course_code=body.course_code,
        week=body.week,
        summaries_enqueued=enqueued,
    )
