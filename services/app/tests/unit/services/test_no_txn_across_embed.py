"""No open transaction and no blocked event loop across a provider call (GL#50, TECH-07).

Backend half of the pipeline rule pinned in
`tests/unit/pipeline/test_no_session_across_provider_call.py`: the request-time
sites that embed a query (chat, Q&A) or extract concepts must (a) not hold a
pooled connection idle-in-transaction while the provider works and (b) never run
the synchronous `embed_texts` on the event loop thread.

The fake provider sleeps synchronously (a slow local model). A ticker coroutine
counts event-loop turns meanwhile: a loop blocked by an on-loop encode gets ~0.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult, ConceptData, ConceptExtractionResult
from app.models.chat_session import ChatSession


class TxnState:
    """One flag modelling SQLAlchemy autobegin: use opens, commit/rollback closes."""

    def __init__(self) -> None:
        self.open = False
        self.violations: list[str] = []
        self.calls: list[str] = []
        self.threads: list[int] = []  # threads embed_texts ran on
        self.ticks = 0

    def check(self, name: str) -> None:
        self.calls.append(name)
        if name == "embed_texts":
            self.threads.append(threading.get_ident())
        if self.open:
            self.violations.append(f"{name} entered with an open transaction")


class Res:
    def __init__(self, value=None):
        self.value = value

    def unique(self):
        return self

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self.value

    def first(self):
        return self.value

    def all(self):
        return []


def make_session(state: TxnState, chat_session=None):
    session = AsyncMock()
    session.add = MagicMock()

    async def execute(stmt, *a, **kw):
        state.open = True
        if chat_session is not None and "chat_sessions" in str(stmt):
            return Res(chat_session)
        return Res(None)

    async def flush(*a, **kw):
        state.open = True

    async def end(*a, **kw):
        state.open = False

    session.execute = AsyncMock(side_effect=execute)
    session.flush = AsyncMock(side_effect=flush)
    session.commit = AsyncMock(side_effect=end)
    session.rollback = AsyncMock(side_effect=end)
    return session


def slow_provider(state: TxnState, dims: int = 4):
    provider = MagicMock()

    def embed_texts(texts):
        state.check("embed_texts")
        time.sleep(0.3)
        return [[0.1] * dims for _ in texts]

    provider.embed_texts.side_effect = embed_texts
    return provider


async def ticker(state: TxnState, stop: asyncio.Event) -> None:
    while not stop.is_set():
        state.ticks += 1
        await asyncio.sleep(0.01)


async def run_with_ticker(state: TxnState, coro):
    stop = asyncio.Event()
    task = asyncio.create_task(ticker(state, stop))
    await asyncio.sleep(0)
    try:
        return await coro
    finally:
        stop.set()
        await task


def assert_off_loop_and_clean(state: TxnState) -> None:
    assert "embed_texts" in state.calls, "the provider was never reached"
    assert not state.violations, state.violations
    assert threading.get_ident() not in state.threads, "embed_texts ran on the event loop"
    assert state.ticks >= 10, f"event loop starved during the encode ({state.ticks} ticks)"


def chat_session_mock() -> MagicMock:
    chat_session = MagicMock(spec=ChatSession)
    chat_session.course_id = None
    chat_session.message_count = 0
    chat_session.title = "x"
    return chat_session


@pytest.mark.asyncio
async def test_extract_concepts_releases_session_before_agent_and_embeds_off_loop():
    from app.services import concept_service

    state = TxnState()
    session = make_session(state)
    agent = MagicMock()

    async def extract_concepts(**kw):
        state.check("extract_concepts")
        await asyncio.sleep(0)
        return ConceptExtractionResult(
            concepts=[ConceptData(name="ASLR", description="Address randomisation")]
        )

    agent.extract_concepts = AsyncMock(side_effect=extract_concepts)
    provider = slow_provider(state)
    with (
        patch("app.agents.factory.get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_agent_config", AsyncMock(return_value=None)),
        patch("app.services.billing_service.record_ai_call", AsyncMock()),
        patch("app.agents.embeddings.get_embedding_provider", return_value=provider),
    ):
        result = await run_with_ticker(
            state,
            concept_service.extract_and_save_concepts(session, "art-1", "u-1", "c-1", 1, "text"),
        )

    assert result["concept_count"] == 1
    assert "extract_concepts" in state.calls
    assert_off_loop_and_clean(state)


@pytest.mark.asyncio
async def test_send_message_embeds_off_loop_without_open_transaction():
    from app.services import chat_service

    state = TxnState()
    session = make_session(state, chat_session_mock())
    agent = AsyncMock()
    agent.answer_question.return_value = AnswerResult(answer="ok", citations=[])
    provider = slow_provider(state)
    with (
        patch("app.services.chat_service.get_embedding_provider", return_value=provider),
        patch("app.services.chat_service._search", AsyncMock(return_value=[])),
        patch("app.services.chat_service.get_agent", return_value=agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            AsyncMock(return_value=(None, None)),
        ),
    ):
        await run_with_ticker(
            state, chat_service.send_message(session, "s-1", "u-1", "what is ASLR?")
        )

    assert_off_loop_and_clean(state)


@pytest.mark.asyncio
async def test_stream_message_embeds_off_loop_without_open_transaction():
    from app.services import chat_service

    state = TxnState()
    session = make_session(state, chat_session_mock())

    async def stream_answer(q, chunks):
        yield "ok"

    agent = MagicMock()
    agent.stream_answer = stream_answer
    provider = slow_provider(state)

    async def drain():
        return [e async for e in chat_service.stream_message(session, "s-1", "u-1", "what?")]

    with (
        patch("app.services.chat_service.get_embedding_provider", return_value=provider),
        patch("app.services.chat_service._search", AsyncMock(return_value=[])),
        patch("app.services.chat_service.get_agent", return_value=agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            AsyncMock(return_value=(None, None)),
        ),
    ):
        await run_with_ticker(state, drain())

    assert_off_loop_and_clean(state)


@pytest.mark.asyncio
async def test_qa_embeds_off_loop_after_releasing_the_session(async_client, mock_session):
    state = TxnState()

    async def execute(*a, **kw):
        state.open = True
        return MagicMock()

    async def end(*a, **kw):
        state.open = False

    mock_session.execute.side_effect = execute
    mock_session.commit.side_effect = end
    mock_session.rollback = AsyncMock(side_effect=end)

    async def quota(*a, **kw):
        state.open = True

    async def lookup(*a, **kw):
        state.open = True
        return MagicMock(id="course-001")

    provider = slow_provider(state)
    agent = AsyncMock()
    agent.answer_question.return_value = AnswerResult(answer="a", citations=[])
    with (
        patch("app.api.qa.quota_service.check_ai_quota", side_effect=quota),
        patch("app.api.qa.course_service.get_course_by_code", side_effect=lookup),
        patch("app.api.qa.get_embedding_provider", return_value=provider),
        patch("app.api.qa.search_service.search_chunks", AsyncMock(return_value=[])),
        patch("app.api.qa.get_agent", return_value=agent),
    ):
        stop = asyncio.Event()
        task = asyncio.create_task(ticker(state, stop))
        await asyncio.sleep(0)
        response = await async_client.post(
            "/api/qa/ask", json={"question": "What is ASLR?", "course_code": "CSIT302"}
        )
        stop.set()
        await task

    assert response.status_code == 200
    assert_off_loop_and_clean(state)
