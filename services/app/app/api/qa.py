"""Q&A API endpoint — ask questions about lecture content."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import get_embedding_provider
from app.agents.factory import get_agent
from app.api.deps import get_current_user_or_default, require_ai_consent
from app.api.schemas import Citation, QARequest, QAResponse
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import (
    billing_service,
    course_service,
    quota_service,
    search_service,
    settings_service,
)
from app.services.chat_scope import build_sources
from app.services.retrieval import filter_by_floor, not_found_reply, record_below_floor

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/qa/ask",
    dependencies=[Depends(require_ai_consent)],
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
    # Check AI quota (free tier: 20/day)
    await quota_service.check_ai_quota(session, user.id, user.tier)

    # Resolve course_code to course_id if provided
    course_id: str | None = None
    if body.course_code:
        course = await course_service.get_course_by_code(session, body.course_code, user_id=user.id)
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Course {body.course_code} not found",
            )
        course_id = course.id

    # Embed the question
    provider = get_embedding_provider()
    try:
        query_embeddings = provider.embed_texts([body.question])
    except Exception as e:
        safe_error = await settings_service.redacted_error(session, user.id, e)
        logger.error("qa_embedding_error", error=safe_error)
        raise HTTPException(status_code=500, detail="Failed to embed question") from None
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

    searched = len(chunks)
    chunks = filter_by_floor(chunks)
    if not chunks:
        if searched:
            record_below_floor("qa", searched=searched, scope_code=body.course_code, week=body.week)
        # Nothing relevant: answer deterministically, no AI call, no usage.
        return QAResponse(
            answer=not_found_reply(body.course_code, body.week),
            citations=[],
            chunks_searched=0,
        )

    # Call agent with per-user settings
    from app.services.settings_service import get_user_ai_context

    user_agent_config, output_language = await get_user_ai_context(session, user.id)
    agent = get_agent(user_settings=user_agent_config, output_language=output_language)
    try:
        answer_result = await agent.answer_question(body.question, chunks)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Q&A agent not yet configured. Ensure Claude Code CLI is available.",
        ) from None
    except Exception as e:
        safe_error = await settings_service.redacted_error(session, user.id, e)
        logger.error("qa_agent_error", error=safe_error, question=body.question[:100])
        raise HTTPException(
            status_code=500, detail=f"Failed to generate answer: {safe_error}"
        ) from None

    # Record AI usage with real adapter tokens when reported, else an estimate.
    # Committed here: the session is not committed by the dependency, so a bare
    # flush would be rolled back on close and Q&A would never count.
    await billing_service.record_ai_call(
        session,
        user.id,
        agent=agent,
        prompt_text=body.question + "".join(str(c.get("text", "")) for c in chunks),
        output_text=getattr(answer_result, "answer", "") or "",
    )
    await session.commit()

    # Build response
    # Citations are derived from the chunks we sent, never from the model's
    # own citation list: ids and snippets there cannot be trusted (GL#13).
    citations = [
        Citation(
            ref=s["ref"],
            chunk_id=str(s["chunk_id"] or ""),
            text_snippet=s["text_snippet"],
            course_code=s["course_code"] or "",
            week=s["week"] or 0,
            page_ref=s["page_ref"] or 0,
            artifact_id=str(s["artifact_id"] or ""),
        )
        for s in build_sources(answer_result.answer, chunks)
    ]

    return QAResponse(
        answer=answer_result.answer,
        citations=citations,
        chunks_searched=len(chunks),
    )
