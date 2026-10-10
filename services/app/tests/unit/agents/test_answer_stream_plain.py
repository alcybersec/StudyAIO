"""GL#16 (AI-04): streamed chat must never show JSON scaffolding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.answer_stream import plain_answer_stream, render_stream_prompt
from app.services.chat_scope import build_sources

CHUNKS = [
    {"course_code": "CSIT302", "week": 5, "page_ref": 2, "text": "Polymorphism lets objects vary."}
]


async def _agen(tokens):
    for t in tokens:
        yield t


async def _collect(tokens):
    return [t async for t in plain_answer_stream(_agen(tokens))]


class TestStreamPrompt:
    def test_prompt_asks_for_prose_not_json(self) -> None:
        prompt = render_stream_prompt("What is polymorphism?", CHUNKS)
        assert '"answer"' not in prompt
        assert '"citations"' not in prompt
        assert "[1] (CSIT302 Week 5, p.2)" in prompt
        assert "plain" in prompt.lower()

    def test_non_stream_prompt_still_json(self) -> None:
        from pathlib import Path

        text = (Path(__file__).resolve().parents[3] / "prompts/answer_question.txt").read_text()
        assert '"answer"' in text  # Q&A path keeps its JSON contract


class TestPlainAnswerStream:
    @pytest.mark.asyncio
    async def test_prose_passes_through_token_by_token(self) -> None:
        tokens = ["It ", "varies", " [1]."]
        assert await _collect(tokens) == tokens

    @pytest.mark.asyncio
    async def test_leading_whitespace_tokens_are_not_lost(self) -> None:
        out = await _collect([" ", "\n", "Hello", " there"])
        assert "".join(out) == " \nHello there"

    @pytest.mark.asyncio
    async def test_json_reply_emits_only_answer_field(self) -> None:
        raw = '{"answer": "It varies [1].", "citations": [{"ref": 1}]}'
        out = await _collect(
            ['{"ans', 'wer": "It varies', ' [1].", "citations"', ': [{"ref": 1}]}']
        )
        assert "".join(out) == "It varies [1]."
        assert "{" not in "".join(out)
        assert '"answer"' not in "".join(out)
        assert raw  # sanity

    @pytest.mark.asyncio
    async def test_fenced_json_reply_unwrapped(self) -> None:
        out = await _collect(['```json\n{"answer": "Hi [1]."', "}\n```"])
        assert "".join(out) == "Hi [1]."

    @pytest.mark.asyncio
    async def test_unparseable_brace_reply_falls_back_to_raw(self) -> None:
        out = await _collect(["{not json"])
        assert "".join(out) == "{not json"

    @pytest.mark.asyncio
    async def test_citations_derived_from_markers_unaffected(self) -> None:
        text = "".join(await _collect(["Objects vary ", "[1]."]))
        assert build_sources(text, [{**CHUNKS[0], "chunk_id": "c1"}]) == build_sources(
            "Objects vary [1].", [{**CHUNKS[0], "chunk_id": "c1"}]
        )


class TestAdaptersStreamPlain:
    @pytest.mark.asyncio
    async def test_openai_stream_strips_json_scaffolding_and_matches_answer(self) -> None:
        with patch(
            "app.agents.openai_adapter.get_effective_setting",
            side_effect=lambda key: {"openai_api_key": "k", "openai_model": "m"}.get(key, ""),
        ):
            from app.agents.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="k", model="m")

        def mk(content):
            c = MagicMock()
            c.choices = [MagicMock()]
            c.choices[0].delta.content = content
            return c

        async def stream():
            for p in ['{"answer": "Objects vary', ' [1].", "citations": []}']:
                yield mk(p)

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=stream())
        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=client):
            streamed = "".join([t async for t in adapter.stream_answer("q", CHUNKS)])

        with patch.object(
            adapter, "_call_api", AsyncMock(return_value='{"answer": "Objects vary [1]."}')
        ):
            non_stream = (await adapter.answer_question("q", CHUNKS)).answer

        assert streamed == non_stream == "Objects vary [1]."
        sent = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert '"answer"' not in sent
