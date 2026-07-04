"""Pydantic schemas for chat API."""

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Request body for creating a new chat session."""

    title: str = "New Chat"
    course_code: str | None = None


class CreateSessionResponse(BaseModel):
    """Response after creating a chat session."""

    id: str
    title: str
    course_id: str | None
    message_count: int
    created_at: str
    updated_at: str


class ChatSessionSummary(BaseModel):
    """Summary of a chat session for list views."""

    id: str
    title: str
    course_id: str | None
    message_count: int
    created_at: str
    updated_at: str


class ChatSessionListResponse(BaseModel):
    """Response containing a list of chat sessions."""

    sessions: list[ChatSessionSummary]


class ChatMessageResponse(BaseModel):
    """Response for a single chat message."""

    id: str
    session_id: str
    role: str
    content: str
    citations_json: list[dict] | None = None
    created_at: str


class ChatMessagesResponse(BaseModel):
    """Response containing a list of chat messages."""

    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    """Request body for sending a message in a chat session.

    Optional per-message scope chips (course/week) narrow RAG retrieval
    for this message without changing the session's own course scope.
    """

    content: str = Field(..., min_length=1, max_length=5000)
    course_code: str | None = None
    week: int | None = Field(default=None, ge=1)


class SendMessageResponse(BaseModel):
    """Response after sending a message, containing both user and assistant messages."""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
