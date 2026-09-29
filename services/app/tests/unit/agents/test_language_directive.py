"""Tests for the output-language directive appended to content prompts.

The load-bearing pair is `TestEveryAdapter`: a directive must reach every
prompt a *human* reads, and must reach none of the prompts the *app* parses.
`classify` emits the course code and week the pipeline routes on,
`extract_course_ops` emits dates and assessment records, `extract_concepts`
emits a fixed category enum — a translated one of those is a parse failure
that would look like a bad lecture file rather than a language bug.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.anthropic_api import AnthropicAPIAdapter
from app.agents.base import ExtractionData
from app.agents.claude_code import ClaudeCodeAdapter
from app.agents.ollama_adapter import OllamaAdapter
from app.agents.openai_adapter import OpenAIAdapter

EXTRACTION = ExtractionData(
    pages=[{"page_number": 1, "text": "Firewalls and IDS", "images": []}],
    metadata={"course_code": "CSIT302", "week": 5},
)

CHUNKS = [{"chunk_id": "c1", "text": "A firewall filters traffic.", "course_code": "CSIT302"}]

#: What each method must be handed back so its parser succeeds. The prompt is
#: what is under test; the response only has to be well-formed.
RESPONSES = {
    "generate_summary": "# CSIT302 — Week 5\n\n## Overview\n\nBody.",
    "generate_flashcards": '[{"front": "Q", "back": "A", "tags": [], "source_page_ref": 1}]',
    "generate_quiz": (
        '[{"question_type": "short_answer", "question": "Q", '
        '"correct_answer": "A", "explanation": "", "source_page_ref": 1}]'
    ),
    "answer_question": '{"answer": "An answer.", "citations": []}',
    "classify_lecture": (
        '{"course_code": "CSIT302", "week": 5, "title": "T", "confidence": 0.9, "reasoning": ""}'
    ),
    "extract_course_ops": (
        '{"assessments": [], "deadlines": [], "course_info": {}, "confidence": 0.5}'
    ),
    "extract_concepts": '{"concepts": [], "relations": []}',
}

CALLS = {
    "generate_summary": lambda a: a.generate_summary(EXTRACTION, None),
    "generate_flashcards": lambda a: a.generate_flashcards("summary", EXTRACTION, 5),
    "generate_quiz": lambda a: a.generate_quiz("summary", EXTRACTION, 5),
    "answer_question": lambda a: a.answer_question("What is a firewall?", CHUNKS),
    "classify_lecture": lambda a: a.classify_lecture("preview", "w5.pdf", ["CSIT302"]),
    "extract_course_ops": lambda a: a.extract_course_ops("text", "CSIT302", "outline"),
    "extract_concepts": lambda a: a.extract_concepts("lecture text", None),
}

#: A human reads these.
CONTENT_METHODS = [
    "generate_summary",
    "generate_flashcards",
    "generate_quiz",
    "answer_question",
]

#: The app parses these.
METADATA_METHODS = [
    "classify_lecture",
    "extract_course_ops",
    "extract_concepts",
]

ADAPTERS = {
    "anthropic": (lambda: AnthropicAPIAdapter(api_key="k", model="sonnet"), "_call_api"),
    "openai": (lambda: OpenAIAdapter(api_key="k", model="gpt-4o"), "_call_api"),
    "ollama": (lambda: OllamaAdapter(base_url="http://ollama:11434", model="m"), "_call_api"),
    "claude_code": (
        lambda: ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet"),
        "_run_claude_code",
    ),
}


async def _capture_prompt(adapter_name: str, method: str, language: str | None) -> str:
    """Run one adapter method with the model mocked and return the prompt sent."""
    build, call_attr = ADAPTERS[adapter_name]
    adapter = build()
    adapter.set_output_language(language)

    mock = AsyncMock(return_value=RESPONSES[method])
    with patch.object(adapter, call_attr, new=mock):
        await CALLS[method](adapter)

    assert mock.await_count == 1, f"{adapter_name}.{method} did not call the model once"
    return mock.await_args.args[0]


class TestLanguageDirective:
    """The directive text itself, on the base adapter."""

    def test_empty_by_default(self):
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        assert adapter.output_language is None
        assert adapter.language_directive() == ""

    def test_empty_for_english(self):
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        adapter.set_output_language("en")
        assert adapter.language_directive() == ""

    def test_names_the_language_for_russian(self):
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        adapter.set_output_language("ru")
        directive = adapter.language_directive()
        assert "Russian" in directive
        assert "Output language" in directive

    def test_protects_headings_and_json_field_names(self):
        """The two things whose translation would break parsing, named explicitly."""
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        adapter.set_output_language("ru")
        directive = adapter.language_directive()
        assert "section headings" in directive
        assert "JSON field names" in directive

    def test_unsupported_tag_is_ignored(self):
        """A tag that slipped past validation must not reach the prompt."""
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        adapter.set_output_language("xx")
        assert adapter.output_language is None
        assert adapter.language_directive() == ""

    def test_with_language_leaves_english_prompts_byte_identical(self):
        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")
        assert adapter.with_language("Summarise this.") == "Summarise this."


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_name", sorted(ADAPTERS))
class TestEveryAdapter:
    """Every adapter applies the same rule to the same set of methods."""

    @pytest.mark.parametrize("method", CONTENT_METHODS)
    async def test_content_prompt_carries_the_directive(self, adapter_name, method):
        prompt = await _capture_prompt(adapter_name, method, "ru")
        assert "Write your response in Russian." in prompt, (
            f"{adapter_name}.{method} sent no language directive"
        )

    @pytest.mark.parametrize("method", METADATA_METHODS)
    async def test_metadata_prompt_never_carries_the_directive(self, adapter_name, method):
        prompt = await _capture_prompt(adapter_name, method, "ru")
        assert "Write your response in Russian." not in prompt, (
            f"{adapter_name}.{method} is parsed by the app and must stay English"
        )

    @pytest.mark.parametrize("method", CONTENT_METHODS)
    async def test_english_prompt_is_unchanged(self, adapter_name, method):
        """No language set must leave the prompt exactly as it was before."""
        with_none = await _capture_prompt(adapter_name, method, None)
        with_english = await _capture_prompt(adapter_name, method, "en")
        assert with_none == with_english
        assert "Output language" not in with_none
