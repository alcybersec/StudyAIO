"""Chat API endpoints — persistent AI study companion conversations."""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.chat_schemas import (
    ChatMessageResponse,
    ChatMessagesResponse,
    ChatSessionListResponse,
    ChatSessionSummary,
    CreateSessionRequest,
    CreateSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.api.deps import get_current_user_or_default
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.course import Course
from app.models.user import User
from app.services import billing_service, chat_service, quota_service

logger = structlog.get_logger()

router = APIRouter()


def _session_to_response(chat_session) -> dict:
    """Convert ChatSession ORM object to response dict."""
    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "course_id": chat_session.course_id,
        "message_count": chat_session.message_count,
        "created_at": chat_session.created_at.isoformat(),
        "updated_at": chat_session.updated_at.isoformat(),
    }


async def _resolve_scope_course(
    session: AsyncSession,
    user: User,
    course_code: str | None,
) -> str | None:
    """Resolve an optional per-message course_code scope to a course_id.

    Raises:
        HTTPException: 404 if the course code doesn't exist for this user.
    """
    if not course_code:
        return None
    result = await session.execute(
        select(Course).where(Course.code == course_code, Course.user_id == user.id)
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found")
    return course.id


def _message_to_response(msg) -> dict:
    """Convert ChatMessage ORM object to response dict."""
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "citations_json": msg.citations_json,
        "created_at": msg.created_at.isoformat(),
    }


@router.post(
    "/chat/sessions",
    response_model=CreateSessionResponse,
    status_code=201,
    summary="Create chat session",
    description="Create a new persistent chat session, optionally scoped to a course.",
)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CreateSessionResponse:
    """Create a new chat session."""
    # Resolve course_code to course_id if provided
    course_id = None
    if body.course_code:
        result = await session.execute(
            select(Course).where(Course.code == body.course_code, Course.user_id == user.id)
        )
        course = result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail=f"Course '{body.course_code}' not found")
        course_id = course.id

    chat_session = await chat_service.create_session(
        session=session,
        user_id=user.id,
        title=body.title,
        course_id=course_id,
    )
    await session.commit()
    return CreateSessionResponse(**_session_to_response(chat_session))


@router.get(
    "/chat/sessions",
    response_model=ChatSessionListResponse,
    summary="List chat sessions",
    description="List the current user's chat sessions, most recent first.",
)
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ChatSessionListResponse:
    """List chat sessions for the current user."""
    sessions = await chat_service.list_sessions(session, user.id, limit=limit)
    return ChatSessionListResponse(
        sessions=[ChatSessionSummary(**_session_to_response(s)) for s in sessions]
    )


@router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=ChatMessagesResponse,
    summary="Get chat messages",
    description="Get messages for a chat session (paginated).",
)
async def get_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ChatMessagesResponse:
    """Get paginated messages for a chat session."""
    try:
        messages = await chat_service.get_messages(
            session=session,
            session_id=session_id,
            user_id=user.id,
            limit=limit,
            offset=offset,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Chat session not found") from None
    return ChatMessagesResponse(
        messages=[ChatMessageResponse(**_message_to_response(m)) for m in messages]
    )


@router.post(
    "/chat/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a message",
    description="Send a message in a chat session and receive an AI response.",
)
@limiter.limit(lambda: settings.rate_limit_qa)
async def send_message(
    request: Request,
    session_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> SendMessageResponse:
    """Send a user message and get an AI assistant response."""
    # Check AI quota (free tier: 20/day)
    await quota_service.check_ai_quota(session, user.id, user.tier)

    scope_course_id = await _resolve_scope_course(session, user, body.course_code)

    try:
        user_msg, assistant_msg = await chat_service.send_message(
            session=session,
            session_id=session_id,
            user_id=user.id,
            content=body.content,
            course_id=scope_course_id,
            week=body.week,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Chat session not found") from None
    except Exception as e:
        logger.error("chat_send_error", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail="Failed to process message") from e

    # Record AI usage (best-effort)
    try:
        await billing_service.record_usage(session, user.id, ai_calls=1)
    except Exception:
        logger.warning("usage_record_chat_failed", exc_info=True)

    await session.commit()

    return SendMessageResponse(
        user_message=ChatMessageResponse(**_message_to_response(user_msg)),
        assistant_message=ChatMessageResponse(**_message_to_response(assistant_msg)),
    )


@router.post(
    "/chat/sessions/{session_id}/messages/stream",
    summary="Send a message (streaming)",
    description="Send a message and receive the AI response as an SSE stream.",
)
@limiter.limit(lambda: settings.rate_limit_qa)
async def stream_message(
    request: Request,
    session_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> EventSourceResponse:
    """Send a user message and stream the AI response via SSE."""
    # Check AI quota
    await quota_service.check_ai_quota(session, user.id, user.tier)

    scope_course_id = await _resolve_scope_course(session, user, body.course_code)

    async def event_generator():
        try:
            async for event in chat_service.stream_message(
                session=session,
                session_id=session_id,
                user_id=user.id,
                content=body.content,
                course_id=scope_course_id,
                week=body.week,
            ):
                event_type = event["event"]
                data = event["data"]
                if isinstance(data, dict):
                    yield {"event": event_type, "data": json.dumps(data)}
                else:
                    yield {"event": event_type, "data": data}
        except ValueError:
            yield {"event": "error", "data": "Chat session not found"}
        except Exception as e:
            logger.error("chat_stream_error", error=str(e), session_id=session_id)
            yield {"event": "error", "data": "Failed to process message"}

        # Record AI usage (best-effort)
        try:
            await billing_service.record_usage(session, user.id, ai_calls=1)
        except Exception:
            logger.warning("usage_record_stream_failed", exc_info=True)

        await session.commit()

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


@router.delete(
    "/chat/sessions/{session_id}",
    status_code=204,
    summary="Delete chat session",
    description="Delete a chat session and all its messages.",
)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a chat session and all its messages (cascade)."""
    deleted = await chat_service.delete_session(session, session_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    await session.commit()
