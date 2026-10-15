"""No open transaction while the chat / Q&A answer agent runs (GL#50, TECH-07).

Sibling of `test_no_txn_across_embed.py`: same fake session and transaction flag,
but the probe is the answer call (`answer_question` / `stream_answer`), which sits
after the history, plan, search and week-summary reads. For streaming, the flag is
also checked on every token so a transaction reopened mid-stream is caught.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from tests.unit.services.test_no_txn_across_embed import (
    TxnState,
    chat_session_mock,
    make_session,
    slow_provider,
)


def chat_patches(state: TxnState, agent):
    async def search(*a, **kw):
        state.open = True  # the RAG read opens a transaction
        return []

    async def ctx(*a, **kw):
        state.open = True  # the settings read opens one too
        return (None, None)

    return (
        patch(
            "app.services.chat_service.get_embedding_provider",
            return_value=slow_provider(state),
        ),
        patch("app.services.chat_service._search", side_effect=search),
        patch("app.services.chat_service.get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_ai_context", side_effect=ctx),
    )


@pytest.mark.asyncio
async def test_send_message_releases_session_before_answer_question():
    from app.services import chat_service

    state = TxnState()
    session = make_session(state, chat_session_mock())
    agent = MagicMock()

    async def answer_question(q, chunks):
        state.check("answer_question")
        await asyncio.sleep(0)
        return AnswerResult(answer="ok", citations=[])

    agent.answer_question = answer_question
    p1, p2, p3, p4 = chat_patches(state, agent)
    with p1, p2, p3, p4:
        await chat_service.send_message(session, "s-1", "u-1", "what is ASLR?")

    assert "answer_question" in state.calls
    assert not state.violations, state.violations


@pytest.mark.asyncio
async def test_stream_message_holds_no_transaction_while_tokens_stream():
    from app.services import chat_service

    state = TxnState()
    session = make_session(state, chat_session_mock())
    agent = MagicMock()

    async def stream_answer(q, chunks):
        state.check("stream_answer")
        for tok in ("a", "b", "c"):
            await asyncio.sleep(0)
            state.check("token")
            yield tok

    agent.stream_answer = stream_answer
    p1, p2, p3, p4 = chat_patches(state, agent)
    with p1, p2, p3, p4:
        events = [e async for e in chat_service.stream_message(session, "s-1", "u-1", "what?")]

    assert [e["data"] for e in events if e["event"] == "token"] == ["a", "b", "c"]
    assert "stream_answer" in state.calls
    assert not state.violations, state.violations


@pytest.mark.asyncio
async def test_qa_releases_session_before_answer_question(async_client, mock_session):
    state = TxnState()

    async def execute(*a, **kw):
        state.open = True
        return MagicMock()

    async def end(*a, **kw):
        state.open = False

    mock_session.execute.side_effect = execute
    mock_session.commit.side_effect = end
    mock_session.rollback = AsyncMock(side_effect=end)

    async def open_txn(*a, **kw):
        state.open = True

    async def ctx(*a, **kw):
        state.open = True
        return (None, None)

    async def answer_question(q, chunks):
        state.check("answer_question")
        return AnswerResult(answer="a", citations=[])

    agent = MagicMock()
    agent.answer_question = answer_question
    chunk = {
        "chunk_id": "c1",
        "text": "t",
        "page_ref": 1,
        "slide_title": "s",
        "artifact_id": "a1",
        "week": 1,
        "artifact_title": "T",
        "original_filename": "f.pdf",
        "course_code": "CSIT302",
        "course_id": "course-001",
        "similarity": 0.9,
    }

    async def search(*a, **kw):
        state.open = True
        return [chunk]

    with (
        patch("app.api.qa.quota_service.check_ai_quota", side_effect=open_txn),
        patch("app.api.qa.get_embedding_provider", return_value=slow_provider(state)),
        patch("app.api.qa.search_service.search_chunks", side_effect=search),
        patch("app.api.qa.get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_ai_context", side_effect=ctx),
    ):
        response = await async_client.post("/api/qa/ask", json={"question": "What is ASLR?"})

    assert response.status_code == 200
    assert "answer_question" in state.calls
    assert not state.violations, state.violations
