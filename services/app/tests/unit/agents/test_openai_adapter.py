"""Tests for OpenAIAdapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import (
    AnswerResult,
    ClassificationResult,
    ExtractionData,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)
from app.agents.openai_adapter import (
    _DEFAULT_MAX_TOKENS,
    _SUMMARY_MAX_TOKENS,
    OpenAIAdapter,
)
from app.core.exceptions import AgentError


def _mock_openai_response(text: str) -> MagicMock:
    """Create a mock OpenAI chat completion response."""
    mock_message = MagicMock()
    mock_message.content = text
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    return mock_response


@pytest.fixture
def mock_settings():
    """Mock get_effective_setting for adapter init."""
    with patch("app.agents.openai_adapter.get_effective_setting") as mock:
        mock.side_effect = lambda key: {
            "openai_api_key": "test-key-123",
            "openai_model": "gpt-4o",
        }.get(key, "")
        yield mock


@pytest.fixture
def adapter(mock_settings):
    """OpenAIAdapter with mocked settings."""
    return OpenAIAdapter()


class TestInit:
    """Tests for OpenAIAdapter.__init__."""

    def test_reads_settings(self, mock_settings):
        """Adapter reads API key and model from settings."""
        adapter = OpenAIAdapter()

        assert adapter._api_key == "test-key-123"
        assert adapter._model == "gpt-4o"

    def test_explicit_params_override_settings(self, mock_settings):
        """Explicit constructor args override settings."""
        adapter = OpenAIAdapter(api_key="override-key", model="gpt-4o-mini")

        assert adapter._api_key == "override-key"
        assert adapter._model == "gpt-4o-mini"


class TestCallApi:
    """Tests for _call_api()."""

    async def test_raises_on_missing_api_key(self, mock_settings):
        """Missing API key raises AgentError."""
        adapter = OpenAIAdapter(api_key="")
        adapter._api_key = ""

        with pytest.raises(AgentError, match="OpenAI API key not configured"):
            await adapter._call_api("test prompt")

    async def test_raises_on_api_failure(self, adapter):
        """API exception is wrapped in AgentError."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("connection error"))

        with (
            patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client),
            pytest.raises(AgentError, match="OpenAI API call failed"),
        ):
            await adapter._call_api("test prompt")

    async def test_returns_text_from_response(self, adapter):
        """Successful API call returns text content."""
        mock_response = _mock_openai_response("Hello world")
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == "Hello world"

    async def test_handles_none_content(self, adapter):
        """None content returns empty string."""
        mock_response = _mock_openai_response("")
        mock_response.choices[0].message.content = None
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == ""

    async def test_passes_max_tokens(self, adapter):
        """max_tokens parameter is forwarded to API."""
        mock_response = _mock_openai_response("result")
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            await adapter._call_api("test prompt", max_tokens=8192)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 8192

    async def test_passes_model(self, adapter):
        """Model is forwarded to API."""
        mock_response = _mock_openai_response("result")
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            await adapter._call_api("test prompt")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"

    async def test_handles_none_usage(self, adapter):
        """None usage doesn't crash logging."""
        mock_response = _mock_openai_response("result")
        mock_response.usage = None
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.agents.openai_adapter.AsyncOpenAI", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == "result"


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

    async def test_handles_missing_fields(self, adapter):
        """Missing fields get defaults."""
        response_json = json.dumps({"course_code": "TEST101"})

        with patch.object(adapter, "_call_api", return_value=response_json):
            result = await adapter.classify_lecture("text", "file.pdf", [])

        assert result.course_code == "TEST101"
        assert result.week == 0
        assert result.title == ""
        assert result.confidence == 0.0


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


class TestExtractCourseOps:
    """Tests for extract_course_ops()."""

    async def test_parses_course_ops_response(self, adapter):
        """CourseOps JSON is parsed into CourseOpsResult."""
        response = json.dumps(
            {
                "assessments": [
                    {
                        "title": "Final Exam",
                        "assessment_type": "exam",
                        "weight_pct": 40.0,
                        "description": "Covers weeks 1-13",
                        "weeks_relevant": [1, 2, 3],
                    }
                ],
                "deadlines": [
                    {
                        "title": "Assignment 1 Due",
                        "due_date": "2026-04-15",
                        "deadline_type": "assignment",
                        "description": "Submit via Moodle",
                    }
                ],
                "course_info": {"course_name": "Software Engineering"},
                "confidence": 0.85,
            }
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.extract_course_ops("doc text", "CSIT302", "outline")

        assert len(result.assessments) == 1
        assert result.assessments[0].title == "Final Exam"
        assert len(result.deadlines) == 1
        assert result.confidence == 0.85
