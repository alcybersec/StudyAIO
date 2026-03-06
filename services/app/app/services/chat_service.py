"""Chat service — persistent AI study companion conversations with RAG."""

from collections.abc import AsyncIterator
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import get_embedding_provider
from app.agents.factory import get_agent
from app.core.utils import generate_id
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services import search_service

logger = structlog.get_logger()

# Max conversation history messages to include in prompt context.
MAX_HISTORY_MESSAGES = 10
# Max RAG chunks to retrieve per question.
MAX_RAG_CHUNKS = 5


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

    now = datetime.now(tz=None)

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

    # 3. Embed question and search for relevant chunks via RAG
    chunks: list[dict] = []
    try:
        provider = get_embedding_provider()
        query_embeddings = provider.embed_texts([content])
        if query_embeddings:
            chunks = await search_service.search_chunks(
                session=session,
                query_embedding=query_embeddings[0],
                top_k=MAX_RAG_CHUNKS,
                course_id=chat_session.course_id,
                user_id=user_id,
            )
    except Exception as e:
        logger.warning("chat_rag_search_failed", error=str(e))
        # Continue without RAG context — still useful for general conversation

    # 4. Call agent with context-enhanced question
    agent = get_agent()
    try:
        context_question = _build_contextual_question(content, history[:-1], chunks)
        answer_result = await agent.answer_question(context_question, chunks)
        answer_text = answer_result.answer
        answer_citations = answer_result.citations
    except Exception as e:
        logger.error("chat_agent_error", error=str(e))
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
        created_at=datetime.now(tz=None),
    )
    session.add(assistant_msg)

    # 6. Update session metadata
    chat_session.message_count += 2  # user + assistant
    chat_session.updated_at = datetime.now(tz=None)

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

    now = datetime.now(tz=None)

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

    # RAG search
    chunks: list[dict] = []
    try:
        provider = get_embedding_provider()
        query_embeddings = provider.embed_texts([content])
        if query_embeddings:
            chunks = await search_service.search_chunks(
                session=session,
                query_embedding=query_embeddings[0],
                top_k=MAX_RAG_CHUNKS,
                course_id=chat_session.course_id,
                user_id=user_id,
            )
    except Exception as e:
        logger.warning("chat_stream_rag_failed", error=str(e))

    # Yield user message ID
    yield {
        "event": "user_message",
        "data": {"id": user_msg.id},
    }

    # Stream tokens from agent
    agent = get_agent()
    full_text = ""
    try:
        context_question = _build_contextual_question(content, history[:-1], chunks)
        async for token in agent.stream_answer(context_question, chunks):
            full_text += token
            yield {"event": "token", "data": token}
    except Exception as e:
        logger.error("chat_stream_error", error=str(e))
        error_msg = (
            "I'm sorry, I encountered an error while processing your question. "
            "Please try again."
        )
        full_text = error_msg
        yield {"event": "token", "data": error_msg}

    # Parse citations from the full response (best-effort)
    citations: list[dict] = []
    try:
        from app.agents import parsing
        parsed = parsing.parse_json_response(full_text)
        if isinstance(parsed, dict) and "answer" in parsed:
            full_text = parsed["answer"]
            citations = parsed.get("citations", [])
    except Exception:
        pass  # Use raw text if not valid JSON

    # Save assistant message
    assistant_msg = ChatMessage(
        id=generate_id(),
        session_id=session_id,
        role="assistant",
        content=full_text,
        citations_json=citations if citations else None,
        created_at=datetime.now(tz=None),
    )
    session.add(assistant_msg)

    # Update session metadata
    chat_session.message_count += 2
    chat_session.updated_at = datetime.now(tz=None)
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
