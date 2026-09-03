"""Tests for AI usage metering.

Pipeline AI calls were historically invisible to the quota system: only
`chat.py`, `qa.py`, `concepts.py` and `uploads.py` recorded anything, so the
expensive bulk work (classify, summarize, flashcards, quiz) was uncounted and
the `usage_records.ai_tokens_*` columns were never written to.

These cover the two halves of the fix: adapters accumulating usage, and
`record_agent_usage` persisting it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import TokenUsage


def _openai_response(text: str, prompt_tokens: int, completion_tokens: int) -> MagicMock:
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


class TestTokenUsage:
    def test_starts_empty(self):
        usage = TokenUsage()
        assert (usage.calls, usage.input_tokens, usage.output_tokens) == (0, 0, 0)

    def test_add_accumulates(self):
        usage = TokenUsage()
        usage.add(input_tokens=10, output_tokens=5)
        usage.add(input_tokens=3, output_tokens=2)

        assert usage.calls == 2
        assert usage.input_tokens == 13
        assert usage.output_tokens == 7

    def test_add_without_tokens_still_counts_the_call(self):
        """Backends that report no usage must still be counted."""
        usage = TokenUsage()
        usage.add()
        assert usage.calls == 1
        assert usage.input_tokens == 0


class TestAdapterAccumulatesUsage:
    @pytest.mark.asyncio
    async def test_openai_records_tokens(self):
        from app.agents.openai_adapter import OpenAIAdapter

        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            adapter = OpenAIAdapter(api_key="k", model="gpt-4o")

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_response("hi", 120, 45))
        with patch.object(OpenAIAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        assert adapter.usage.calls == 1
        assert adapter.usage.input_tokens == 120
        assert adapter.usage.output_tokens == 45

    @pytest.mark.asyncio
    async def test_usage_accumulates_across_calls(self):
        """assets.py makes two calls and records once — this is why."""
        from app.agents.openai_adapter import OpenAIAdapter

        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            adapter = OpenAIAdapter(api_key="k", model="gpt-4o")

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_response("hi", 10, 5))
        with patch.object(OpenAIAdapter, "_client", return_value=client):
            await adapter._call_api("one")
            await adapter._call_api("two")

        assert adapter.usage.calls == 2
        assert adapter.usage.input_tokens == 20

    @pytest.mark.asyncio
    async def test_zai_inherits_metering(self):
        from app.agents.zai_adapter import ZaiAdapter

        with patch("app.agents.zai_adapter.get_effective_setting", return_value=""):
            adapter = ZaiAdapter(api_key="k")

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_openai_response("hi", 7, 3))
        with patch.object(ZaiAdapter, "_client", return_value=client):
            await adapter._call_api("prompt")

        assert adapter.usage.calls == 1
        assert adapter.usage.input_tokens == 7

    def test_adapters_start_with_independent_usage(self):
        """A class-level counter would bleed one user's spend into another's."""
        from app.agents.openai_adapter import OpenAIAdapter

        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            first = OpenAIAdapter(api_key="k")
            second = OpenAIAdapter(api_key="k")

        first.usage.add(input_tokens=5)

        assert first.usage.calls == 1
        assert second.usage.calls == 0

    def test_reset_clears(self):
        from app.agents.openai_adapter import OpenAIAdapter

        with patch("app.agents.openai_adapter.get_effective_setting", return_value=""):
            adapter = OpenAIAdapter(api_key="k")

        adapter.usage.add(input_tokens=5)
        adapter.reset_usage()

        assert adapter.usage.calls == 0


class TestRecordAgentUsage:
    @pytest.mark.asyncio
    async def test_persists_calls_and_tokens(self, mock_session):
        from app.services.billing_service import record_agent_usage

        agent = MagicMock()
        agent.usage = TokenUsage(calls=2, input_tokens=100, output_tokens=40)

        recorder = AsyncMock()
        with patch("app.services.billing_service.record_usage", recorder):
            await record_agent_usage(mock_session, "user-1", agent)

        kwargs = recorder.await_args.kwargs
        assert kwargs["ai_calls"] == 2
        assert kwargs["tokens_input"] == 100
        assert kwargs["tokens_output"] == 40

    @pytest.mark.asyncio
    async def test_no_calls_records_nothing(self, mock_session):
        from app.services.billing_service import record_agent_usage

        agent = MagicMock()
        agent.usage = TokenUsage()

        recorder = AsyncMock()
        with patch("app.services.billing_service.record_usage", recorder):
            await record_agent_usage(mock_session, "user-1", agent)

        recorder.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resets_so_usage_is_not_double_counted(self, mock_session):
        from app.services.billing_service import record_agent_usage

        agent = MagicMock()
        agent.usage = TokenUsage(calls=1, input_tokens=10, output_tokens=5)
        agent.reset_usage = MagicMock()

        with patch("app.services.billing_service.record_usage", AsyncMock()):
            await record_agent_usage(mock_session, "user-1", agent)

        agent.reset_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_never_raises_into_the_pipeline(self, mock_session):
        """The stage has already produced its output; metering must not undo it."""
        from app.services.billing_service import record_agent_usage

        agent = MagicMock()
        agent.usage = TokenUsage(calls=1)

        with patch(
            "app.services.billing_service.record_usage",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            await record_agent_usage(mock_session, "user-1", agent)

    @pytest.mark.asyncio
    async def test_tolerates_an_agent_without_usage(self, mock_session):
        from app.services.billing_service import record_agent_usage

        await record_agent_usage(mock_session, "user-1", object())
