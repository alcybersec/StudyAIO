"""Export API endpoints -- Obsidian vault export."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.models.user import User
from app.services import export_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/exports/obsidian/{course_code}",
    summary="Export course as Obsidian vault",
    description="Generates and downloads an Obsidian-compatible vault (zip archive) "
    "with summaries, flashcards, and quizzes.",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "Obsidian vault zip archive",
        },
    },
)
async def export_obsidian_vault(
    course_code: str,
    weeks: str = Query(
        "",
        description="Comma-separated week numbers to include (empty = all)",
    ),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export a course as an Obsidian vault."""
    # Parse weeks parameter
    week_list: list[int] | None = None
    if weeks.strip():
        try:
            week_list = [int(w.strip()) for w in weeks.split(",") if w.strip()]
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid weeks parameter. Use comma-separated integers.",
            ) from exc

    result = await export_service.generate_obsidian_vault(
        session, course_code, week_list, user_id=user.id
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Course '{course_code}' not found",
        )

    buf, filename = result

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
