"""Tests for AnthropicAPIAdapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.anthropic_api import (
    _DEFAULT_MAX_TOKENS,
    _SUMMARY_MAX_TOKENS,
    MODEL_MAP,
    AnthropicAPIAdapter,
)
from app.agents.base import (
    AnswerResult,
    ClassificationResult,
    ExtractionData,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)
from app.core.exceptions import AgentError


def _mock_api_response(text: str) -> MagicMock:
    """Create a mock Anthropic API response."""
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = text
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_message.usage = MagicMock()
    mock_message.usage.input_tokens = 100
    mock_message.usage.output_tokens = 50
    return mock_message


@pytest.fixture
def mock_settings():
    """Mock get_effective_setting for adapter init."""
    with patch("app.agents.anthropic_api.get_effective_setting") as mock:
        mock.side_effect = lambda key: {
            "anthropic_api_key": "test-key-123",
            "claude_model": "sonnet",
        }.get(key, "")
        yield mock


@pytest.fixture
def adapter(mock_settings):
    """AnthropicAPIAdapter with mocked settings."""
    return AnthropicAPIAdapter()


class TestInit:
    """Tests for AnthropicAPIAdapter.__init__."""

    def test_reads_settings(self, mock_settings):
        """Adapter reads API key and model from settings."""
        adapter = AnthropicAPIAdapter()

        assert adapter._api_key == "test-key-123"
        assert adapter._model == MODEL_MAP["sonnet"]

    def test_explicit_params_override_settings(self, mock_settings):
        """Explicit constructor args override settings."""
        adapter = AnthropicAPIAdapter(api_key="override-key", model="haiku")

        assert adapter._api_key == "override-key"
        assert adapter._model == MODEL_MAP["haiku"]

    def test_unknown_model_defaults_to_sonnet(self, mock_settings):
        """Unknown model name falls back to sonnet."""
        adapter = AnthropicAPIAdapter(model="unknown-model")

        assert adapter._model == MODEL_MAP["sonnet"]


class TestModelMap:
    """Tests for MODEL_MAP constant."""

    def test_contains_opus(self):
        """MODEL_MAP has opus."""
        assert "opus" in MODEL_MAP

    def test_contains_sonnet(self):
        """MODEL_MAP has sonnet."""
        assert "sonnet" in MODEL_MAP

    def test_contains_haiku(self):
        """MODEL_MAP has haiku."""
        assert "haiku" in MODEL_MAP

    def test_model_ids_are_strings(self):
        """All model IDs are non-empty strings."""
        for _key, value in MODEL_MAP.items():
            assert isinstance(value, str)
            assert len(value) > 0


class TestCallApi:
    """Tests for _call_api()."""

    async def test_raises_on_missing_api_key(self, mock_settings):
        """Missing API key raises AgentError."""
        adapter = AnthropicAPIAdapter(api_key="")
        adapter._api_key = ""

        with pytest.raises(AgentError, match="API key not configured"):
            await adapter._call_api("test prompt")

    async def test_raises_on_api_failure(self, adapter):
        """API exception is wrapped in AgentError."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("connection error"))

        with (
            patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client),
            pytest.raises(AgentError, match="Anthropic API call failed"),
        ):
            await adapter._call_api("test prompt")

    async def test_returns_text_from_response(self, adapter):
        """Successful API call returns text content."""
        mock_response = _mock_api_response("Hello world")
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == "Hello world"

    async def test_concatenates_multiple_text_blocks(self, adapter):
        """Multiple text blocks in response are joined."""
        block1 = MagicMock()
        block1.type = "text"
        block1.text = "Part 1"
        block2 = MagicMock()
        block2.type = "text"
        block2.text = "Part 2"
        mock_message = MagicMock()
        mock_message.content = [block1, block2]
        mock_message.usage = MagicMock()
        mock_message.usage.input_tokens = 100
        mock_message.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == "Part 1\nPart 2"

    async def test_passes_max_tokens(self, adapter):
        """max_tokens parameter is forwarded to API."""
        mock_response = _mock_api_response("result")
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.anthropic_api.AsyncAnthropic", return_value=mock_client):
            await adapter._call_api("test prompt", max_tokens=8192)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 8192


class TestClassifyLecture:
    """Tests for classify_lecture()."""

    async def test_parses_classification_response(self, adapter):
        """Successful classification returns ClassificationResult."""
        response_json = json.dumps(
            {
                "course_code": "CSIT302",
                "week": 5,
                "title": "Network Security",
                "confidence": 0.92,
                "reasoning": "Found in header",
            }
        )

        with patch.object(adapter, "_call_api", return_value=response_json):
            result = await adapter.classify_lecture(
                "CSIT302 Week 5", "CSIT302_Week5.pdf", ["CSIT302"]
            )

        assert isinstance(result, ClassificationResult)
        assert result.course_code == "CSIT302"
        assert result.week == 5
        assert result.title == "Network Security"
        assert result.confidence == 0.92


class TestGenerateSummary:
    """Tests for generate_summary()."""

    async def test_parses_summary_with_meta(self, adapter):
        """Summary with JSON_META is parsed correctly."""
        response = """# CSIT302 — Week 5: Network Security

## Key Concepts
- Firewalls
---JSON_META---
{"embedded_images": ["diagram.png"]}
---JSON_META---"""

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.generate_summary(extraction, None)

        assert isinstance(result, SummaryResult)
        assert "CSIT302" in result.content_md
        assert result.embedded_images == ["diagram.png"]

    async def test_uses_summary_max_tokens(self, adapter):
        """Summary calls use _SUMMARY_MAX_TOKENS."""
        response = "# Summary\n---JSON_META---\n{}\n---JSON_META---"

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_call_api", return_value=response) as mock_call:
            await adapter.generate_summary(extraction, None)

        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs.get("max_tokens", _DEFAULT_MAX_TOKENS) == _SUMMARY_MAX_TOKENS


class TestGenerateFlashcards:
    """Tests for generate_flashcards()."""

    async def test_parses_flashcard_array(self, adapter):
        """Flashcard JSON array is parsed into FlashcardData list."""
        response = json.dumps(
            [
                {
                    "front": "What is a firewall?",
                    "back": "A network security system",
                    "tags": ["security"],
                    "source_page_ref": 1,
                },
                {
                    "front": "What is IDS?",
                    "back": "Intrusion Detection System",
                    "tags": ["security"],
                    "source_page_ref": 2,
                },
            ]
        )

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.generate_flashcards("# Summary", extraction, 2)

        assert len(result) == 2
        assert all(isinstance(f, FlashcardData) for f in result)
        assert result[0].front == "What is a firewall?"
        assert result[1].tags == ["security"]


class TestGenerateQuiz:
    """Tests for generate_quiz()."""

    async def test_parses_quiz_array(self, adapter):
        """Quiz JSON array is parsed into QuizQuestionData list."""
        response = json.dumps(
            [
                {
                    "question_type": "multiple_choice",
                    "question": "What is a firewall?",
                    "options": ["A. Router", "B. Security system", "C. Cable", "D. Switch"],
                    "correct_answer": "B",
                    "explanation": "Firewalls are security systems.",
                    "source_page_ref": 1,
                },
            ]
        )

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.generate_quiz("# Summary", extraction, 1)

        assert len(result) == 1
        assert isinstance(result[0], QuizQuestionData)
        assert result[0].question_type == "multiple_choice"
        assert result[0].correct_answer == "B"


class TestAnswerQuestion:
    """Tests for answer_question()."""

    async def test_parses_answer_response(self, adapter):
        """Answer JSON is parsed into AnswerResult."""
        response = json.dumps(
            {
                "answer": "A firewall is a network security system [1].",
                "citations": [
                    {
                        "ref": 1,
                        "chunk_id": "abc_p1_c0",
                        "text_snippet": "Firewalls are security systems",
                        "course_code": "CSIT302",
                        "week": 5,
                        "page_ref": 1,
                    }
                ],
            }
        )

        chunks = [
            {
                "text": "Firewalls are security systems that monitor traffic.",
                "course_code": "CSIT302",
                "week": 5,
                "page_ref": 1,
                "chunk_id": "abc_p1_c0",
            }
        ]

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.answer_question("What is a firewall?", chunks)

        assert isinstance(result, AnswerResult)
        assert "firewall" in result.answer
        assert len(result.citations) == 1
        assert result.citations[0]["ref"] == 1
