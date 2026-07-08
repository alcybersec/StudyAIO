"""Global search API endpoint."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import search_service

logger = structlog.get_logger()

router = APIRouter()


class SearchResultItem(BaseModel):
    """A single global search result."""

    kind: str
    title: str
    snippet: str
    href_meta: dict


class SearchResponse(BaseModel):
    """Global search response."""

    query: str
    results: list[SearchResultItem]


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Global search",
    description="Search courses, week summaries, flashcards, and chat sessions. "
    "Returns grouped results with navigation metadata.",
)
@limiter.limit("60/minute")
async def global_search(
    request: Request,
    q: str = Query(..., description="Search term"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Search across all indexed entity kinds for the current user."""
    term = q.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Search query must not be empty")

    results = await search_service.search_all(session, user.id, term, limit=limit)
    return SearchResponse(
        query=term,
        results=[
            SearchResultItem(
                kind=r.kind,
                title=r.title,
                snippet=r.snippet,
                href_meta=r.href_meta,
            )
            for r in results
        ],
    )
