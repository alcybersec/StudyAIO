"""Chat service — persistent AI study companion conversations with RAG."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import get_embedding_provider
from app.agents.factory import get_agent
from app.core.clock import utc_now
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.course import Course
from app.services import course_service, retrieval, search_service, settings_service
from app.services.chat_scope import build_sources, detect_quiz_intent, parse_scope

logger = structlog.get_logger()

# Max conversation history messages to include in prompt context.
MAX_HISTORY_MESSAGES = 10
# Max RAG chunks to retrieve per question.
MAX_RAG_CHUNKS = 5
# Recent user messages scanned for a course/week to carry into a follow-up.
CARRY_WINDOW = 6


def _join_codes(codes: list[str]) -> str:
    """Render ['A', 'B', 'C'] as 'A, B or C'."""
    if len(codes) == 1:
        return codes[0]
    return ", ".join(codes[:-1]) + f" or {codes[-1]}"


@dataclass
class _Plan:
    """Retrieval scope and short-circuit reply decided before any AI call."""

    course_id: str | None
    week: int | None
    code: str | None = None
    from_message: bool = False
    reply: str | None = None
    action: dict | None = None


def _no_material_reply(plan: _Plan) -> str:
    """Plain reply when the named course/week has nothing indexed."""
    label = plan.code or "That course"
    if plan.week is not None:
        return f"{label} has no Week {plan.week} material indexed yet."
    return f"{label} has no indexed material yet."


async def _courses_with_week(session: AsyncSession, user_id: str, week: int) -> list[str]:
    """Codes of the caller's active courses that have an artifact in ``week``."""
    result = await session.execute(
        select(Course.code)
        .join(LectureArtifact, LectureArtifact.course_id == Course.id)
        .where(
            Course.user_id == user_id,
            Course.archived_at.is_(None),
            LectureArtifact.user_id == user_id,
            LectureArtifact.week == week,
        )
        .distinct()
        .order_by(Course.code)
    )
    return [row[0] for row in result.all()]


async def _carry_scope(
    session: AsyncSession,
    user_id: str,
    recent_user_messages: list[str],
) -> tuple[Course | None, int | None]:
    """Find the latest course (and week) named in recent user messages.

    Messages are newest first. The course is re-resolved against the caller's
    own courses on every turn, so a deleted or foreign code is skipped and the
    next older one is tried. The week is the newest one mentioned at or after
    the message that supplied the course.
    """
    week: int | None = None
    for text in recent_user_messages[:CARRY_WINDOW]:
        parsed = parse_scope(text)
        if week is None:
            week = parsed.week
        if parsed.code is None:
            continue
        course = await course_service.get_course_by_code(session, parsed.code, user_id=user_id)
        if course is not None:
            return course, week
    return None, None


async def _plan_message(
    session: AsyncSession,
    user_id: str,
    content: str,
    course_id: str | None,
    week: int | None,
    session_course_id: str | None,
    recent_user_messages: list[str] | None = None,
) -> _Plan:
    """Resolve the course/week scope and quiz intent for a message.

    A course code named in the message is resolved against the caller's own
    courses only; a code they do not own is reported exactly like a missing
    one. An explicit ``course_id`` skips message parsing entirely. When the
    message names no course, the latest one from ``recent_user_messages``
    (newest first, caller-scoped) is carried over. A week with no course
    anywhere in context gets a clarifying question, never an unscoped search.
    """
    plan = _Plan(course_id=course_id or session_course_id, week=week)
    parsed = None
    if course_id is None:
        parsed = parse_scope(content)
        if parsed.code:
            course = await course_service.get_course_by_code(session, parsed.code, user_id=user_id)
            if course is None:
                plan.code = parsed.code
                plan.reply = f"You have no course {parsed.code}."
                return plan
            plan.course_id = course.id
            plan.code = parsed.code
            plan.from_message = True
            if week is None:
                plan.week = parsed.week
        else:
            carried, carried_week = await _carry_scope(session, user_id, recent_user_messages or [])
            if carried is not None:
                plan.course_id = carried.id
                plan.code = carried.code
                plan.from_message = True
                if week is None:
                    plan.week = parsed.week if parsed.week is not None else carried_week
    if detect_quiz_intent(content):
        plan.action = {
            "type": "open_quiz_builder",
            "course_code": plan.code,
            "course_id": plan.course_id,
            "week": plan.week,
        }
        target = plan.code or "your course"
        if plan.week is not None:
            target += f" Week {plan.week}"
        plan.reply = f"Open the quiz builder to create a test for {target}."
    elif parsed is not None and plan.course_id is None and parsed.week is not None and week is None:
        codes = await _courses_with_week(session, user_id, parsed.week)
        if len(codes) == 1:
            course = await course_service.get_course_by_code(session, codes[0], user_id=user_id)
            if course is not None:
                plan.course_id = course.id
                plan.code = course.code
                plan.week = parsed.week
                plan.from_message = True
        elif codes:
            plan.week = parsed.week
            plan.reply = f"Which course for Week {parsed.week} — {_join_codes(codes)}?"
        else:
            plan.reply = f"None of your courses have Week {parsed.week} material indexed yet."
    return plan


def _previous_user_message(content: str, recent_user: list[str]) -> str | None:
    """Newest earlier user message (``recent_user`` is newest first).

    The history query may already contain the message being sent; a leading
    copy of ``content`` is skipped so a follow-up never uses itself as context.
    """
    earlier = recent_user[1:] if recent_user and recent_user[0] == content else recent_user
    return earlier[0] if earlier else None


async def _retrieve(
    session: AsyncSession,
    user_id: str,
    content: str,
    plan: _Plan,
    recent_user: list[str],
    failure_event: str,
) -> list[dict]:
    """Search the caller's chunks for ``content`` and apply the relevance floor.

    Follow-up turns embed the carried scope plus the previous question and the
    message (deterministic rewrite, no AI call). When the search succeeded but
    nothing clears the floor, ``plan.reply`` is set to a fixed reply so the
    agent is never called. A failed search still falls through to a general
    answer, as before.
    """
    query = retrieval.build_retrieval_query(
        content,
        code=plan.code,
        week=plan.week,
        previous_user_message=_previous_user_message(content, recent_user),
    )
    raw: list[dict] = []
    search_ok = False
    try:
        provider = get_embedding_provider()
        query_embeddings = provider.embed_texts([query])
        if query_embeddings:
            raw = await search_service.search_chunks(
                session=session,
                query_embedding=query_embeddings[0],
                top_k=MAX_RAG_CHUNKS,
                course_id=plan.course_id,
                week=plan.week,
                user_id=user_id,
            )
            search_ok = True
    except Exception as e:
        logger.warning(
            failure_event,
            error=await settings_service.redacted_error(session, user_id, e),
        )
        # Continue without RAG context -- still useful for general conversation
    chunks = retrieval.filter_by_floor(raw)
    if search_ok and not chunks:
        if raw:
            plan.reply = retrieval.not_found_reply(plan.code, plan.week)
            retrieval.record_below_floor(
                "chat", searched=len(raw), scope_code=plan.code, week=plan.week
            )
        elif plan.from_message:
            plan.reply = _no_material_reply(plan)
    return chunks


async def create_session(
    session: AsyncSession,
    user_id: str,
    title: str = "New Chat",
    course_id: str | None = None,
) -> ChatSession:
    """Create a new chat session.

    Args:
        session: Database session.
        user_id: Owner user ID.
        title: Session title.
        course_id: Optional course scope for RAG filtering.

    Returns:
        Created ChatSession instance.
    """
    chat_session = ChatSession(
        id=generate_id(),
        user_id=user_id,
        course_id=course_id,
        title=title,
        message_count=0,
    )
    session.add(chat_session)
    await session.flush()
    logger.info("chat_session_created", session_id=chat_session.id, user_id=user_id)
    return chat_session


async def list_sessions(
    session: AsyncSession,
    user_id: str,
    limit: int = 50,
) -> list[ChatSession]:
    """List user's chat sessions, most recent first.

    Args:
        session: Database session.
        user_id: User ID to filter by.
        limit: Maximum sessions to return.

    Returns:
        List of ChatSession objects ordered by updated_at descending.
    """
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_messages(
    session: AsyncSession,
    session_id: str,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[ChatMessage]:
    """Get messages for a chat session (paginated).

    Args:
        session: Database session.
        session_id: Chat session ID.
        user_id: User ID for ownership check.
        limit: Max messages to return.
        offset: Pagination offset.

    Returns:
        List of ChatMessage objects ordered by created_at ascending.

    Raises:
        ValueError: If session not found or not owned by user.
    """
    chat_result = await session.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if not chat_session:
        raise ValueError("Chat session not found")

    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def send_message(
    session: AsyncSession,
    session_id: str,
    user_id: str,
    content: str,
    course_id: str | None = None,
    week: int | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    """Send a user message and get an AI response.

    Orchestration flow:
    1. Verify session ownership
    2. Save user message
    3. Get last N messages for conversation context
    4. Embed question + search relevant chunks (RAG)
    5. Build context-enhanced question with history
    6. Call agent.answer_question
    7. Save assistant message with citations
    8. Update session metadata (count, title, timestamp)

    Args:
        session: Database session.
        session_id: Chat session ID.
        user_id: User ID for ownership check.
        content: User's message text.
        course_id: Optional per-message course scope for RAG retrieval
            (overrides the session's course scope).
        week: Optional per-message week scope for RAG retrieval.

    Returns:
        Tuple of (user_message, assistant_message) ChatMessage objects.

    Raises:
        ValueError: If session not found or not owned by user.
    """
    # Verify session ownership
    chat_result = await session.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if not chat_session:
        raise ValueError("Chat session not found")

    now = utc_now()

    # 1. Save user message
    user_msg = ChatMessage(
        id=generate_id(),
        session_id=session_id,
        role="user",
        content=content,
        created_at=now,
    )
    session.add(user_msg)

    # 2. Get conversation history (last N messages BEFORE this one)
    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    # Build history for context
    history = [{"role": m.role, "content": m.content} for m in history_msgs]
    # Append current user message
    history.append({"role": "user", "content": content})

    # 3. Resolve scope named in the message, then embed + search (RAG)
    recent_user = [m.content for m in reversed(history_msgs) if m.role == "user"]
    plan = await _plan_message(
        session, user_id, content, course_id, week, chat_session.course_id, recent_user
    )
    chunks: list[dict] = []
    answer_text = ""
    answer_citations: list[dict] = []
    if plan.reply is None:
        chunks = await _retrieve(
            session, user_id, content, plan, recent_user, "chat_rag_search_failed"
        )

    if plan.reply is not None:
        answer_text = plan.reply
    else:
        # 4. Call agent with per-user settings
        from app.services.settings_service import get_user_ai_context

        user_agent_config, output_language = await get_user_ai_context(session, user_id)
        agent = get_agent(user_settings=user_agent_config, output_language=output_language)
        try:
            context_question = _build_contextual_question(content, history[:-1], chunks)
            answer_result = await agent.answer_question(context_question, chunks)
            answer_text = answer_result.answer
            # Sources are derived from the chunk order the [n] markers refer to,
            # not from the adapter's own (possibly partial) citation list.
            answer_citations = build_sources(answer_text, chunks)
        except Exception as e:
            logger.error(
                "chat_agent_error",
                error=await settings_service.redacted_error(session, user_id, e),
            )
            answer_text = (
                "I'm sorry, I encountered an error while processing your question. "
                "Please try again."
            )
            answer_citations = []

    # 5. Save assistant message
    assistant_msg = ChatMessage(
        id=generate_id(),
        session_id=session_id,
        role="assistant",
        content=answer_text,
        citations_json=answer_citations if answer_citations else None,
        created_at=utc_now(),
    )
    assistant_msg.action_json = plan.action
    session.add(assistant_msg)

    # 6. Update session metadata
    chat_session.message_count += 2  # user + assistant
    chat_session.updated_at = utc_now()

    # Auto-generate title from first user message
    if chat_session.message_count <= 2 and chat_session.title == "New Chat":
        chat_session.title = content[:80] + ("..." if len(content) > 80 else "")

    await session.flush()

    logger.info(
        "chat_message_sent",
        session_id=session_id,
        chunks_used=len(chunks),
        citations=len(answer_citations),
    )
    return user_msg, assistant_msg


async def stream_message(
    session: AsyncSession,
    session_id: str,
    user_id: str,
    content: str,
    course_id: str | None = None,
    week: int | None = None,
) -> AsyncIterator[dict]:
    """Stream a chat response token-by-token via SSE events.

    Yields SSE event dicts:
    - {"event": "token", "data": "text chunk"}
    - {"event": "done", "data": JSON with full message + citations}
    - {"event": "error", "data": error message}

    The full assistant message is saved to the database at the end.

    Args:
        session: Database session.
        session_id: Chat session ID.
        user_id: User ID for ownership check.
        content: User's message text.
        course_id: Optional per-message course scope for RAG retrieval
            (overrides the session's course scope).
        week: Optional per-message week scope for RAG retrieval.

    Yields:
        Dicts with event type and data for SSE serialization.
    """
    # Verify session ownership
    chat_result = await session.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if not chat_session:
        yield {"event": "error", "data": "Chat session not found"}
        return

    now = utc_now()

    # Save user message
    user_msg = ChatMessage(
        id=generate_id(),
        session_id=session_id,
        role="user",
        content=content,
        created_at=now,
    )
    session.add(user_msg)

    # Get conversation history
    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history_msgs = list(reversed(history_result.scalars().all()))
    history = [{"role": m.role, "content": m.content} for m in history_msgs]
    history.append({"role": "user", "content": content})

    # Resolve scope named in the message, then RAG search
    recent_user = [m.content for m in reversed(history_msgs) if m.role == "user"]
    plan = await _plan_message(
        session, user_id, content, course_id, week, chat_session.course_id, recent_user
    )
    chunks: list[dict] = []
    if plan.reply is None:
        chunks = await _retrieve(
            session, user_id, content, plan, recent_user, "chat_stream_rag_failed"
        )

    # Yield user message ID
    yield {
        "event": "user_message",
        "data": {"id": user_msg.id},
    }

    full_text = ""
    if plan.reply is not None:
        full_text = plan.reply
        yield {"event": "token", "data": full_text}
    else:
        # Stream tokens from agent with per-user settings
        from app.services.settings_service import get_user_ai_context

        user_agent_config, output_language = await get_user_ai_context(session, user_id)
        agent = get_agent(user_settings=user_agent_config, output_language=output_language)
        try:
            context_question = _build_contextual_question(content, history[:-1], chunks)
            async for token in agent.stream_answer(context_question, chunks):
                full_text += token
                yield {"event": "token", "data": token}
        except Exception as e:
            logger.error(
                "chat_stream_error",
                error=await settings_service.redacted_error(session, user_id, e),
            )
            error_msg = (
                "I'm sorry, I encountered an error while processing your question. "
                "Please try again."
            )
            full_text = error_msg
            yield {"event": "token", "data": error_msg}

    # Parse citations from the full response (best-effort)
    citations: list[dict] = []
    if plan.reply is None:
        try:
            from app.agents import parsing

            parsed = parsing.parse_json_response(full_text)
            if isinstance(parsed, dict) and "answer" in parsed:
                full_text = parsed["answer"]
        except Exception:
            pass  # Use raw text if not valid JSON
        # Sources follow the chunk order the [n] markers refer to.
        citations = build_sources(full_text, chunks)

    # Save assistant message
    assistant_msg = ChatMessage(
        id=generate_id(),
        session_id=session_id,
        role="assistant",
        content=full_text,
        citations_json=citations if citations else None,
        created_at=utc_now(),
    )
    assistant_msg.action_json = plan.action
    session.add(assistant_msg)

    # Update session metadata
    chat_session.message_count += 2
    chat_session.updated_at = utc_now()
    if chat_session.message_count <= 2 and chat_session.title == "New Chat":
        chat_session.title = content[:80] + ("..." if len(content) > 80 else "")

    await session.flush()

    # Final done event with full message + citations
    yield {
        "event": "done",
        "data": {
            "id": assistant_msg.id,
            "content": full_text,
            "citations_json": citations if citations else None,
            "action": plan.action,
        },
    }

    logger.info(
        "chat_stream_complete",
        session_id=session_id,
        chunks_used=len(chunks),
        citations=len(citations),
        response_length=len(full_text),
    )


def _build_contextual_question(
    question: str,
    history: list[dict],
    chunks: list[dict],
) -> str:
    """Build a context-enhanced question string for the agent.

    Prepends conversation history summary to help the agent
    understand the ongoing conversation.

    Args:
        question: Current user question.
        history: Previous messages (before current question).
        chunks: Retrieved RAG chunks (unused here but available for extension).

    Returns:
        Enhanced question string with conversation context.
    """
    if not history:
        return question

    # Include recent conversation context (last 6 messages)
    context_parts = ["[Conversation context]"]
    for msg in history[-6:]:
        role = "Student" if msg["role"] == "user" else "You"
        text = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
        context_parts.append(f"{role}: {text}")

    context_parts.append(f"\n[Current question]\n{question}")
    return "\n".join(context_parts)


async def delete_session(
    session: AsyncSession,
    session_id: str,
    user_id: str,
) -> bool:
    """Delete a chat session and all its messages (cascade).

    Args:
        session: Database session.
        session_id: Chat session ID.
        user_id: User ID for ownership check.

    Returns:
        True if deleted, False if not found.
    """
    chat_result = await session.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if not chat_session:
        return False

    await session.delete(chat_session)
    await session.flush()
    logger.info("chat_session_deleted", session_id=session_id)
    return True
