"""The additive ``focus`` keyword and the targeted templates (ADR 0007 Decision 5)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.anthropic_api import AnthropicAPIAdapter
from app.agents.base import ExtractionData, GenerationFocus
from app.agents.claude_code import ClaudeCodeAdapter
from app.agents.ollama_adapter import OllamaAdapter
from app.agents.openai_adapter import OpenAIAdapter
from app.agents.targeted_prompts import render_targeted_prompt
from app.agents.zai_adapter import ZaiAdapter
from app.core.exceptions import AgentError

EXTRACTION = ExtractionData(
    pages=[
        {"page_number": 1, "text": "A hash table maps keys to buckets."},
        {"page_number": 2, "text": "Open addressing probes the next bucket on a collision."},
    ],
    metadata={"course_code": "CSIT302", "week": 5},
)
FOCUS = GenerationFocus(
    topics=["Open addressing", "Load factor"],
    missed_questions=["What does linear probing do on a collision?"],
    avoid=["Define a hash table."],
    page_refs=[2],
)
QUIZ_REPLY = json.dumps(
    [
        {
            "question_type": "short_answer",
            "question": "What is primary clustering?",
            "options": None,
            "correct_answer": "Runs of occupied buckets grow.",
            "explanation": "Probing extends runs.",
            "source_page_ref": 2,
        }
    ]
)
CARD_REPLY = json.dumps(
    [{"front": "Primary clustering?", "back": "Runs grow.", "tags": ["open addressing"]}]
)


def _adapters():
    return [
        pytest.param(lambda: ClaudeCodeAdapter(model="test"), "_run_claude_code", id="claude_code"),
        pytest.param(lambda: OpenAIAdapter(api_key="k", model="m"), "_call_api", id="openai"),
        pytest.param(lambda: AnthropicAPIAdapter(api_key="k"), "_call_api", id="anthropic"),
        pytest.param(
            lambda: OllamaAdapter(base_url="http://ollama.test", model="m"),
            "_call_api",
            id="ollama",
        ),
    ]


def test_generation_focus_defaults():
    focus = GenerationFocus(topics=["a"])
    assert focus.missed_questions == [] and focus.avoid == [] and focus.page_refs == []


def test_zai_inherits_the_openai_overrides():
    assert ZaiAdapter.generate_quiz is OpenAIAdapter.generate_quiz
    assert ZaiAdapter.generate_flashcards is OpenAIAdapter.generate_flashcards


class TestRender:
    @pytest.mark.parametrize("kind", ["quiz", "flashcards"])
    def test_carries_topics_pages_and_avoid(self, kind):
        prompt = render_targeted_prompt(
            kind,
            course_code="CSIT302",
            week=5,
            summary="# S",
            extraction_text="--- Page 2 [p.2] ---\nOpen addressing probes.",
            count=5,
            focus=FOCUS,
        )
        for needle in (
            "Open addressing",
            "Load factor",
            "What does linear probing do on a collision?",
            "Define a hash table.",
            "[p.2]",
            "exactly 5",
        ):
            assert needle in prompt
        assert "plain text" in prompt.lower()
        assert "source_page_ref" in prompt

    def test_untrusted_spans_are_delimited(self):
        prompt = render_targeted_prompt(
            "quiz",
            course_code="X",
            week=1,
            summary="",
            extraction_text="t",
            count=1,
            focus=FOCUS,
        )
        assert "untrusted" in prompt.lower()

    def test_unknown_kind_raises(self):
        with pytest.raises(AgentError):
            render_targeted_prompt(
                "essay",
                course_code="X",
                week=1,
                summary="",
                extraction_text="",
                count=1,
                focus=FOCUS,
            )


@pytest.mark.parametrize(("make", "transport"), _adapters())
class TestBackends:
    async def test_quiz_with_focus_uses_the_targeted_prompt(self, make, transport):
        adapter = make()
        with patch.object(adapter, transport, new=AsyncMock(return_value=QUIZ_REPLY)) as call:
            result = await adapter.generate_quiz("# S", EXTRACTION, 5, focus=FOCUS)
        prompt = call.await_args.args[0]
        assert "Open addressing" in prompt and "What does linear probing" in prompt
        assert result[0].source_page_ref == 2

    async def test_flashcards_with_focus_uses_the_targeted_prompt(self, make, transport):
        adapter = make()
        with patch.object(adapter, transport, new=AsyncMock(return_value=CARD_REPLY)) as call:
            result = await adapter.generate_flashcards("# S", EXTRACTION, 5, focus=FOCUS)
        prompt = call.await_args.args[0]
        assert "Load factor" in prompt and "Define a hash table." in prompt
        assert result[0].tags == ["open addressing"]

    async def test_no_focus_is_the_untargeted_prompt(self, make, transport):
        adapter = make()
        with patch.object(adapter, transport, new=AsyncMock(return_value=QUIZ_REPLY)) as call:
            await adapter.generate_quiz("# S", EXTRACTION, 5)
            await adapter.generate_quiz("# S", EXTRACTION, 5, focus=None)
        plain, explicit = (c.args[0] for c in call.await_args_list)
        assert plain == explicit
        assert FOCUS.missed_questions[0] not in plain
        assert "weak topics" not in plain.lower()
