"""Q&A API endpoint — ask questions about lecture content."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import get_embedding_provider
from app.agents.factory import get_agent
from app.api.deps import get_current_user_or_default
from app.api.schemas import Citation, QARequest, QAResponse
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.course import Course
from app.models.user import User
from app.services import search_service

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/qa/ask",
    response_model=QAResponse,
    summary="Ask a question",
    description="Ask a question about lecture content. Returns an AI-generated answer with citations to source chunks.",
)
@limiter.limit(lambda: settings.rate_limit_qa)
async def ask_question(
    request: Request,
    body: QARequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> QAResponse:
    """Answer a question using retrieved context chunks and Claude.

    Flow: embed question -> search chunks -> Claude answers with citations.
    """
    # Resolve course_code to course_id if provided
    course_id: str | None = None
    if body.course_code:
        result = await session.execute(select(Course).where(Course.code == body.course_code))
        course = result.scalar_one_or_none()
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Course {body.course_code} not found",
            )
        course_id = course.id

    # Embed the question
    provider = get_embedding_provider()
    query_embeddings = provider.embed_texts([body.question])
    if not query_embeddings:
        raise HTTPException(status_code=500, detail="Failed to embed question")
    query_embedding = query_embeddings[0]

    # Search for relevant chunks
    chunks = await search_service.search_chunks(
        session=session,
        query_embedding=query_embedding,
        top_k=body.top_k or 10,
        course_id=course_id,
        week=body.week,
        user_id=user.id,
    )

    if not chunks:
        return QAResponse(
            answer="I couldn't find any relevant content in the indexed lecture materials for your question. "
            "Make sure the relevant lectures have been uploaded and processed.",
            citations=[],
            chunks_searched=0,
        )

    # Call agent to generate answer with citations
    agent = get_agent()
    try:
        answer_result = await agent.answer_question(body.question, chunks)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Q&A agent not yet configured. Ensure Claude Code CLI is available.",
        ) from None
    except Exception as e:
        logger.error("qa_agent_error", error=str(e), question=body.question[:100])
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {e}") from e

    # Build response
    citations = [
        Citation(
            ref=c.get("ref", i + 1),
            chunk_id=c.get("chunk_id", ""),
            text_snippet=c.get("text_snippet", ""),
            course_code=c.get("course_code", ""),
            week=c.get("week", 0),
            page_ref=c.get("page_ref", 0),
            artifact_id=c.get("artifact_id", ""),
        )
        for i, c in enumerate(answer_result.citations)
    ]

    return QAResponse(
        answer=answer_result.answer,
        citations=citations,
        chunks_searched=len(chunks),
    )
