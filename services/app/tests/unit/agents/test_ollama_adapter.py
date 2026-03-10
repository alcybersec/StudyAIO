"""Tests for OllamaAdapter."""

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
from app.agents.ollama_adapter import (
    OllamaAdapter,
)
from app.core.exceptions import AgentError


def _mock_ollama_response(text: str) -> MagicMock:
    """Create a mock Ollama chat response."""
    mock_message = MagicMock()
    mock_message.content = text
    mock_response = MagicMock()
    mock_response.message = mock_message
    return mock_response


@pytest.fixture
def mock_settings():
    """Mock get_effective_setting for adapter init."""
    with patch("app.agents.ollama_adapter.get_effective_setting") as mock:
        mock.side_effect = lambda key: {
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "llama3.2",
        }.get(key, "")
        yield mock


@pytest.fixture
def adapter(mock_settings):
    """OllamaAdapter with mocked settings."""
    return OllamaAdapter()


class TestInit:
    """Tests for OllamaAdapter.__init__."""

    def test_reads_settings(self, mock_settings):
        """Adapter reads base_url and model from settings."""
        adapter = OllamaAdapter()

        assert adapter._base_url == "http://localhost:11434"
        assert adapter._model == "llama3.2"

    def test_explicit_params_override_settings(self, mock_settings):
        """Explicit constructor args override settings."""
        adapter = OllamaAdapter(base_url="http://custom:11434", model="mistral")

        assert adapter._base_url == "http://custom:11434"
        assert adapter._model == "mistral"


class TestCallApi:
    """Tests for _call_api()."""

    async def test_raises_on_api_failure(self, adapter):
        """API exception is wrapped in AgentError."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(side_effect=Exception("connection refused"))

        with (
            patch("app.agents.ollama_adapter.AsyncClient", return_value=mock_client),
            pytest.raises(AgentError, match="Ollama API call failed"),
        ):
            await adapter._call_api("test prompt")

    async def test_returns_text_from_response(self, adapter):
        """Successful API call returns text content."""
        mock_response = _mock_ollama_response("Hello world")
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch("app.agents.ollama_adapter.AsyncClient", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == "Hello world"

    async def test_handles_none_content(self, adapter):
        """None content returns empty string."""
        mock_response = _mock_ollama_response("")
        mock_response.message.content = None
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch("app.agents.ollama_adapter.AsyncClient", return_value=mock_client):
            result = await adapter._call_api("test prompt")

        assert result == ""

    async def test_passes_num_predict(self, adapter):
        """num_predict is forwarded to Ollama."""
        mock_response = _mock_ollama_response("result")
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch("app.agents.ollama_adapter.AsyncClient", return_value=mock_client):
            await adapter._call_api("test prompt", num_predict=8192)

        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["options"]["num_predict"] == 8192

    async def test_passes_model(self, adapter):
        """Model is forwarded to Ollama."""
        mock_response = _mock_ollama_response("result")
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch("app.agents.ollama_adapter.AsyncClient", return_value=mock_client):
            await adapter._call_api("test prompt")

        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["model"] == "llama3.2"


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


class TestGenerateFlashcards:
    """Tests for generate_flashcards()."""

    async def test_parses_flashcard_array(self, adapter):
        """Flashcard JSON array is parsed into FlashcardData list."""
        response = json.dumps(
            [
                {"front": "Q1", "back": "A1", "tags": ["t1"], "source_page_ref": 1},
            ]
        )

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.generate_flashcards("# Summary", extraction, 1)

        assert len(result) == 1
        assert isinstance(result[0], FlashcardData)
        assert result[0].front == "Q1"


class TestGenerateQuiz:
    """Tests for generate_quiz()."""

    async def test_parses_quiz_array(self, adapter):
        """Quiz JSON array is parsed into QuizQuestionData list."""
        response = json.dumps(
            [
                {
                    "question_type": "multiple_choice",
                    "question": "What is a firewall?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "explanation": "Correct.",
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


class TestAnswerQuestion:
    """Tests for answer_question()."""

    async def test_parses_answer_response(self, adapter):
        """Answer JSON is parsed into AnswerResult."""
        response = json.dumps(
            {
                "answer": "A firewall is a security system [1].",
                "citations": [
                    {
                        "ref": 1,
                        "chunk_id": "c1",
                        "text_snippet": "...",
                        "course_code": "CSIT302",
                        "week": 5,
                        "page_ref": 1,
                    }
                ],
            }
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.answer_question("What is a firewall?", [])

        assert isinstance(result, AnswerResult)
        assert "firewall" in result.answer


class TestExtractCourseOps:
    """Tests for extract_course_ops()."""

    async def test_parses_course_ops_response(self, adapter):
        """CourseOps JSON is parsed into CourseOpsResult."""
        response = json.dumps(
            {
                "assessments": [
                    {"title": "Final Exam", "assessment_type": "exam", "weight_pct": 40.0}
                ],
                "deadlines": [
                    {"title": "A1 Due", "due_date": "2026-04-15", "deadline_type": "assignment"}
                ],
                "course_info": {"course_name": "SE"},
                "confidence": 0.85,
            }
        )

        with patch.object(adapter, "_call_api", return_value=response):
            result = await adapter.extract_course_ops("doc text", "CSIT302", "outline")

        assert len(result.assessments) == 1
        assert result.confidence == 0.85
