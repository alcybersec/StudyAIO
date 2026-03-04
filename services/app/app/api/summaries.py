"""Summary API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.schemas import SummaryResponse
from app.core.database import get_session
from app.models.user import User
from app.services import summary_service

router = APIRouter()


@router.get(
    "/summaries/{summary_id}",
    response_model=SummaryResponse,
    summary="Get a summary",
    description="Returns a generated weekly summary by ID, including markdown content, version, and source artifacts.",
)
async def get_summary(
    summary_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> SummaryResponse:
    """Get a summary by ID."""
    summary = await summary_service.get_summary_by_id(session, summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponse.model_validate(summary)
