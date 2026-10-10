"""Tests for chat scope parsing, source derivation and quiz intent (issue #10)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from app.models.chat_session import ChatSession
from app.services.chat_scope import build_sources, detect_quiz_intent, parse_scope
from app.services.chat_service import send_message, stream_message


class TestParseScope:
    """parse_scope is a pure function over the message text."""

    @pytest.mark.parametrize(
        ("text", "code", "week"),
        [
            ("create me a test based on CSCI369 lecture 2", "CSCI369", 2),
            ("quiz me on CSIT302 week 10", "CSIT302", 10),
            ("summarise CSIT314 W3 please", "CSIT314", 3),
            ("what is in CSCI369?", "CSCI369", None),
            ("CSIT302, lec 4", "CSIT302", 4),
        ],
    )
    def test_parses_code_and_week(self, text, code, week):
        scope = parse_scope(text)
        assert scope.code == code
        assert scope.week == week

    @pytest.mark.parametrize(
        "text",
        [
            "explain how SHA256 works",
            "what is W3C",
            "tell me about week 2 and the AES128 cipher",
            "hello there, how are things",
            "the answer is 42 in lecture notes",
            "csci is a prefix",
        ],
    )
    def test_no_false_positives(self, text):
        assert parse_scope(text).code is None

    def test_week_without_code_is_reported(self):
        scope = parse_scope("what about week 2?")
        assert scope.code is None
        assert scope.week == 2

    def test_week_out_of_range_ignored(self):
        assert parse_scope("CSIT302 week 0").week is None
        assert parse_scope("CSIT302 week 99").week is None


class TestDetectQuizIntent:
    @pytest.mark.parametrize(
        "text",
        [
            "create me a test based on CSCI369 lecture 2",
            "Make a quiz for CSIT302 week 3",
            "generate an exam on firewalls",
            "can you build me a practice test",
            "quiz me on CSIT314 W2",
            "test me on lecture 4",
        ],
    )
    def test_detects_requests(self, text):
        assert detect_quiz_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "what is a unit test?",
            "explain what an exam board does",
            "how do I write a unit test in pytest",
            "what is the quiz format on the final",
            "summarise CSCI369 lecture 2",
            "I have a test tomorrow, what is a firewall?",
        ],
    )
    def test_no_false_positives(self, text):
        assert detect_quiz_intent(text) is False


class TestBuildSources:
    """Sources are derived from the chunk list, keyed by inline [n]."""

    CHUNKS = [
        {
            "chunk_id": f"c{i}",
            "text": f"text {i}",
            "page_ref": i,
            "course_code": "CSIT302",
            "week": i,
            "artifact_id": f"a{i}",
        }
        for i in range(1, 6)
    ]

    def test_every_used_index_is_listed_in_order(self):
        out = build_sources("A [1] B [3] C [5] D [2]", self.CHUNKS)
        assert [s["ref"] for s in out] == [1, 2, 3, 5]
        assert out[2]["chunk_id"] == "c3"
        assert out[2]["week"] == 3
        assert out[2]["artifact_id"] == "a3"
        assert out[2]["text_snippet"] == "text 3"

    def test_grouped_and_out_of_range_indices(self):
        out = build_sources("see [1, 4] and [9] and [0]", self.CHUNKS)
        assert [s["ref"] for s in out] == [1, 4]

    def test_no_citations_gives_empty(self):
        assert build_sources("no markers", self.CHUNKS) == []
        assert build_sources("[1]", []) == []


def _session_mock(chat_session):
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    own = MagicMock()
    own.scalar_one_or_none.return_value = chat_session
    hist = MagicMock()
    hist.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[own, hist])
    return session


def _chat_session(course_id=None):
    s = MagicMock(spec=ChatSession)
    s.id = "s1"
    s.user_id = "u1"
    s.course_id = course_id
    s.title = "New Chat"
    s.message_count = 0
    return s


CHUNKS = [
    {"chunk_id": f"c{i}", "text": f"t{i}", "page_ref": i, "course_code": "CSCI369", "week": 2}
    for i in range(1, 6)
]


def _patches(agent, search, get_course):
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 4]
    return (
        patch("app.services.chat_service.get_embedding_provider", return_value=provider),
        patch("app.services.chat_service.search_service.search_chunks", search),
        patch("app.services.chat_service.course_service.get_course_by_code", get_course),
        patch("app.services.chat_service.get_agent", return_value=agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
    )


async def _run_send(content, search, get_course, agent, **kw):
    session = _session_mock(_chat_session())
    ps = _patches(agent, search, get_course)
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        return await send_message(session, "s1", "u1", content, **kw)


async def _run_stream(content, search, get_course, agent, **kw):
    session = _session_mock(_chat_session())
    ps = _patches(agent, search, get_course)
    events = []
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        async for e in stream_message(session, "s1", "u1", content, **kw):
            events.append(e)
    return events


def _course(id_="course-369"):
    c = MagicMock()
    c.id = id_
    return c


class TestSendMessageScope:
    @pytest.mark.asyncio
    async def test_named_course_and_week_scope_retrieval(self):
        get_course = AsyncMock(return_value=_course())
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ok [1]", citations=[])

        await _run_send("summarise CSCI369 lecture 2", search, get_course, agent)

        assert get_course.await_args.args[1] == "CSCI369"
        assert get_course.await_args.kwargs.get("user_id") == "u1"
        assert search.await_args.kwargs["course_id"] == "course-369"
        assert search.await_args.kwargs["week"] == 2
        assert search.await_args.kwargs["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_unowned_code_is_not_found_and_not_searched(self):
        get_course = AsyncMock(return_value=None)
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()

        _, reply = await _run_send("summarise CSCI369 lecture 2", search, get_course, agent)

        assert get_course.await_args.kwargs.get("user_id") == "u1"
        search.assert_not_awaited()
        agent.answer_question.assert_not_awaited()
        assert "no course CSCI369" in reply.content
        assert reply.citations_json is None

    @pytest.mark.asyncio
    async def test_no_indexed_chunks_says_so_without_ai_call(self):
        get_course = AsyncMock(return_value=_course())
        search = AsyncMock(return_value=[])
        agent = AsyncMock()

        _, reply = await _run_send("summarise CSCI369 lecture 2", search, get_course, agent)

        assert search.await_args.kwargs["course_id"] == "course-369"
        assert search.await_args.kwargs["week"] == 2
        agent.answer_question.assert_not_awaited()
        assert "CSCI369" in reply.content
        assert "Week 2" in reply.content

    @pytest.mark.asyncio
    async def test_explicit_course_id_skips_message_parsing(self):
        get_course = AsyncMock()
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="ok", citations=[])

        await _run_send(
            "summarise CSCI369 lecture 2", search, get_course, agent, course_id="explicit", week=7
        )

        get_course.assert_not_awaited()
        assert search.await_args.kwargs["course_id"] == "explicit"
        assert search.await_args.kwargs["week"] == 7

    @pytest.mark.asyncio
    async def test_sources_map_every_used_marker_despite_adapter_omissions(self):
        get_course = AsyncMock()
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(
            answer="A [1] B [2] C [3] D [4] E [5]",
            citations=[{"ref": 1}, {"ref": 2}, {"ref": 4}],
        )

        _, reply = await _run_send("explain firewalls", search, get_course, agent)

        assert [c["ref"] for c in reply.citations_json] == [1, 2, 3, 4, 5]
        assert reply.citations_json[2]["chunk_id"] == "c3"


class TestSendMessageQuizIntent:
    @pytest.mark.asyncio
    async def test_returns_action_without_ai_or_search(self):
        get_course = AsyncMock(return_value=_course())
        search = AsyncMock()
        agent = AsyncMock()

        _, reply = await _run_send(
            "create me a test based on CSCI369 lecture 2", search, get_course, agent
        )

        assert get_course.await_args.kwargs.get("user_id") == "u1"
        search.assert_not_awaited()
        agent.answer_question.assert_not_awaited()
        assert reply.action_json == {
            "type": "open_quiz_builder",
            "course_code": "CSCI369",
            "course_id": "course-369",
            "week": 2,
        }
        assert "CSCI369" in reply.content

    @pytest.mark.asyncio
    async def test_unowned_course_gives_not_found_and_no_action(self):
        get_course = AsyncMock(return_value=None)
        search = AsyncMock()
        agent = AsyncMock()

        _, reply = await _run_send("create me a test on CSCI369 week 2", search, get_course, agent)

        assert get_course.await_args.kwargs.get("user_id") == "u1"
        assert "no course CSCI369" in reply.content
        assert getattr(reply, "action_json", None) is None

    @pytest.mark.asyncio
    async def test_no_code_uses_explicit_scope(self):
        get_course = AsyncMock()
        search = AsyncMock()
        agent = AsyncMock()

        _, reply = await _run_send(
            "make me a quiz", search, get_course, agent, course_id="c-x", week=4
        )

        get_course.assert_not_awaited()
        assert reply.action_json == {
            "type": "open_quiz_builder",
            "course_code": None,
            "course_id": "c-x",
            "week": 4,
        }


class TestStreamMessageScope:
    @pytest.mark.asyncio
    async def test_named_course_and_week_scope_retrieval(self):
        get_course = AsyncMock(return_value=_course())
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()

        async def stream(q, c):
            yield "hi [1]"

        agent.stream_answer = stream

        await _run_stream("explain CSCI369 W2", search, get_course, agent)

        assert get_course.await_args.kwargs.get("user_id") == "u1"
        assert search.await_args.kwargs["course_id"] == "course-369"
        assert search.await_args.kwargs["week"] == 2
        assert search.await_args.kwargs["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_unowned_code_short_circuits(self):
        get_course = AsyncMock(return_value=None)
        search = AsyncMock()
        agent = MagicMock()
        agent.stream_answer = MagicMock(side_effect=AssertionError("no AI call"))

        events = await _run_stream("explain CSCI369 W2", search, get_course, agent)

        search.assert_not_awaited()
        done = events[-1]
        assert done["event"] == "done"
        assert "no course CSCI369" in done["data"]["content"]
        assert done["data"]["citations_json"] is None

    @pytest.mark.asyncio
    async def test_done_event_sources_come_from_chunks(self):
        get_course = AsyncMock()
        search = AsyncMock(return_value=CHUNKS)
        agent = AsyncMock()

        async def stream(q, c):
            yield '{"answer": "A [1] B [3] C [5]", "citations": [{"ref": 1}]}'

        agent.stream_answer = stream

        events = await _run_stream("explain firewalls", search, get_course, agent)

        done = events[-1]["data"]
        assert [c["ref"] for c in done["citations_json"]] == [1, 3, 5]
        assert done["content"] == "A [1] B [3] C [5]"

    @pytest.mark.asyncio
    async def test_quiz_intent_done_event_carries_action(self):
        get_course = AsyncMock(return_value=_course())
        search = AsyncMock()
        agent = MagicMock()
        agent.stream_answer = MagicMock(side_effect=AssertionError("no AI call"))

        events = await _run_stream(
            "create me a test based on CSCI369 lecture 2", search, get_course, agent
        )

        search.assert_not_awaited()
        done = events[-1]["data"]
        assert done["action"] == {
            "type": "open_quiz_builder",
            "course_code": "CSCI369",
            "course_id": "course-369",
            "week": 2,
        }
