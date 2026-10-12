"""GL#34: summarization gets its own sampling temperature; nothing else does."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import base
from app.agents.anthropic_api import AnthropicAPIAdapter
from app.agents.base import ExtractionData, set_summary_temperature, summary_temperature
from app.agents.ollama_adapter import OllamaAdapter
from app.agents.openai_adapter import OpenAIAdapter
from app.agents.zai_adapter import ZaiAdapter

SUMMARY = "# S\n\n## Overview\nx\n---JSON_META---\n{}\n---JSON_META---"


def _extraction() -> ExtractionData:
    return ExtractionData(
        pages=[{"page_number": 1, "text": "Content", "images": []}],
        metadata={"course_code": "CSIT302", "week": 5},
    )


def _openai_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=text))]
    resp.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
    return resp


def _openai_like(cls):
    with patch(
        f"{cls.__module__}.get_effective_setting",
        side_effect=lambda k: {"openai_api_key": "k", "zai_api_key": "k"}.get(k, ""),
    ):
        adapter = cls()
    create = AsyncMock(return_value=_openai_response(SUMMARY))
    client = MagicMock()
    client.chat.completions.create = create
    return adapter, create, client


class TestTemperatureSource:
    def test_defaults_to_point_two_when_setting_absent(self):
        with patch.object(base, "settings", MagicMock(spec=[])):
            assert summary_temperature(OllamaAdapter(base_url="http://x", model="m")) == 0.2

    def test_reads_the_setting(self):
        with patch.object(base, "settings", MagicMock(summary_temperature=0.5)):
            assert summary_temperature(OllamaAdapter(base_url="http://x", model="m")) == 0.5

    def test_instance_override_wins_over_the_setting(self):
        a = OllamaAdapter(base_url="http://x", model="m")
        with patch.object(base, "settings", MagicMock(summary_temperature=0.5)):
            set_summary_temperature(a, 0.0)
            assert summary_temperature(a) == 0.0
            set_summary_temperature(a, None)
            assert summary_temperature(a) == 0.5


@pytest.mark.parametrize("cls", [OpenAIAdapter, ZaiAdapter])
class TestOpenAICompatible:
    async def test_summary_sends_temperature(self, cls):
        adapter, create, client = _openai_like(cls)
        set_summary_temperature(adapter, 0.2)
        with patch.object(cls, "_client", return_value=client):
            await adapter.generate_summary(_extraction(), None)
            await adapter.generate_summary(_extraction(), "# old")
        assert [c.kwargs["temperature"] for c in create.await_args_list] == [0.2, 0.2]

    async def test_other_operations_send_no_temperature(self, cls):
        adapter, create, client = _openai_like(cls)
        with patch.object(cls, "_client", return_value=client):
            for call in (
                adapter.classify_lecture("text", "f.pdf", ["CSIT302"]),
                adapter.generate_flashcards("# s", _extraction(), 3),
                adapter.generate_quiz("# s", _extraction(), 3),
                adapter.answer_question("q", [{"text": "t"}]),
            ):
                with contextlib.suppress(
                    Exception
                ):  # canned reply may not parse; the call is what counts
                    await call
        assert create.await_count == 4
        assert all("temperature" not in c.kwargs for c in create.await_args_list)


class TestAnthropic:
    @pytest.fixture
    def setup(self):
        with patch(
            "app.agents.anthropic_api.get_effective_setting",
            side_effect=lambda k: {"anthropic_api_key": "k", "claude_model": "sonnet"}.get(k, ""),
        ):
            adapter = AnthropicAPIAdapter()
        msg = MagicMock()
        msg.content = [MagicMock(type="text", text=SUMMARY)]
        msg.usage = MagicMock(input_tokens=1, output_tokens=1)
        create = AsyncMock(return_value=msg)
        client = MagicMock()
        client.messages.create = create
        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=client):
            yield adapter, create

    async def test_summary_sends_temperature(self, setup):
        adapter, create = setup
        set_summary_temperature(adapter, 0.3)
        await adapter.generate_summary(_extraction(), None)
        await adapter.generate_summary(_extraction(), "# old")
        assert [c.kwargs["temperature"] for c in create.await_args_list] == [0.3, 0.3]

    async def test_other_operations_send_no_temperature(self, setup):
        adapter, create = setup
        for call in (
            adapter.generate_flashcards("# s", _extraction(), 3),
            adapter.answer_question("q", [{"text": "t"}]),
        ):
            with contextlib.suppress(
                Exception
            ):  # canned reply may not parse; the call is what counts
                await call
        assert create.await_count == 2
        assert all("temperature" not in c.kwargs for c in create.await_args_list)


class TestOllama:
    @pytest.fixture
    def setup(self):
        adapter = OllamaAdapter(base_url="http://localhost:11434", model="m")
        resp = MagicMock()
        resp.message = MagicMock(content=SUMMARY)
        chat = AsyncMock(return_value=resp)
        client = MagicMock()
        client.chat = chat
        with patch("app.agents.ollama_adapter.AsyncClient", return_value=client):
            yield adapter, chat

    async def test_summary_sends_temperature_option(self, setup):
        adapter, chat = setup
        set_summary_temperature(adapter, 0.1)
        await adapter.generate_summary(_extraction(), None)
        await adapter.generate_summary(_extraction(), "# old")
        assert [c.kwargs["options"]["temperature"] for c in chat.await_args_list] == [0.1, 0.1]

    async def test_other_operations_send_no_temperature(self, setup):
        adapter, chat = setup
        for call in (
            adapter.generate_flashcards("# s", _extraction(), 3),
            adapter.answer_question("q", [{"text": "t"}]),
        ):
            with contextlib.suppress(
                Exception
            ):  # canned reply may not parse; the call is what counts
                await call
        assert chat.await_count == 2
        assert all("temperature" not in c.kwargs["options"] for c in chat.await_args_list)
