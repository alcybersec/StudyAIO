"""Tests for ClaudeCodeAdapter flashcard and quiz generation."""

import json
from unittest.mock import patch

import pytest

from app.agents.base import ExtractionData, FlashcardData, QuizQuestionData
from app.agents.claude_code import ClaudeCodeAdapter
from app.agents.parsing import parse_json_array_response
from app.core.exceptions import AgentError


@pytest.fixture
def adapter():
    """ClaudeCodeAdapter with test config."""
    return ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="test")


@pytest.fixture
def sample_extraction():
    """Sample extraction data for tests."""
    return ExtractionData(
        pages=[
            {"page_number": 1, "text": "Firewalls and IDS", "images": []},
            {"page_number": 2, "text": "Network security basics", "images": []},
        ],
        metadata={"course_code": "CSIT302", "week": 5},
    )


class TestParseJsonArrayResponse:
    """Tests for parse_json_array_response() — now in parsing module."""

    def test_direct_json_array(self):
        """Direct JSON array is parsed."""
        text = '[{"front": "Q", "back": "A"}]'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q", "back": "A"}]

    def test_json_array_in_code_fence(self):
        """JSON array in code fences is extracted."""
        text = 'Here are the flashcards:\n```json\n[{"front": "Q", "back": "A"}]\n```'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q", "back": "A"}]

    def test_code_fence_without_language(self):
        """Code fences without language identifier work."""
        text = '```\n[{"key": "value"}]\n```'
        result = parse_json_array_response(text)
        assert result == [{"key": "value"}]

    def test_invalid_json_raises(self):
        """Non-JSON text raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON array"):
            parse_json_array_response("This is not JSON")

    def test_json_object_not_array_raises(self):
        """JSON object (not array) raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON array"):
            parse_json_array_response('{"key": "value"}')

    def test_empty_array(self):
        """Empty JSON array is valid."""
        result = parse_json_array_response("[]")
        assert result == []

    def test_multiple_code_fences_picks_array(self):
        """When multiple code fences exist, picks the one with a JSON array."""
        text = '```\nnot json\n```\n\n```json\n[{"a": 1}]\n```'
        result = parse_json_array_response(text)
        assert result == [{"a": 1}]


class TestGenerateFlashcards:
    """Tests for generate_flashcards()."""

    async def test_generate_flashcards_success(self, adapter, sample_extraction):
        """Successful flashcard generation returns FlashcardData list."""
        response = json.dumps(
            [
                {
                    "front": "What is a firewall?",
                    "back": "A network security system.",
                    "tags": ["firewalls"],
                    "source_page_ref": 1,
                },
                {
                    "front": "Define IDS.",
                    "back": "Intrusion Detection System.",
                    "tags": ["ids"],
                    "source_page_ref": 2,
                },
            ]
        )

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_flashcards(
                summary="# Summary", extraction=sample_extraction, count=2
            )

        assert len(result) == 2
        assert isinstance(result[0], FlashcardData)
        assert result[0].front == "What is a firewall?"
        assert result[0].tags == ["firewalls"]

    async def test_generate_flashcards_code_fenced(self, adapter, sample_extraction):
        """Flashcards in code fences are parsed correctly."""
        response = '```json\n[{"front": "Q", "back": "A", "tags": [], "source_page_ref": 1}]\n```'

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_flashcards(
                summary="", extraction=sample_extraction, count=1
            )

        assert len(result) == 1
        assert result[0].front == "Q"

    async def test_generate_flashcards_defaults(self, adapter, sample_extraction):
        """Missing fields use defaults."""
        response = json.dumps([{"front": "Q", "back": "A"}])

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_flashcards(
                summary="", extraction=sample_extraction, count=1
            )

        assert result[0].tags == []
        assert result[0].source_page_ref == 1


class TestGenerateQuiz:
    """Tests for generate_quiz()."""

    async def test_generate_quiz_success(self, adapter, sample_extraction):
        """Successful quiz generation returns QuizQuestionData list."""
        response = json.dumps(
            [
                {
                    "question_type": "multiple_choice",
                    "question": "What is a firewall?",
                    "options": ["A. Router", "B. Security system", "C. Switch", "D. Hub"],
                    "correct_answer": "B",
                    "explanation": "Firewalls filter traffic.",
                    "source_page_ref": 1,
                },
                {
                    "question_type": "short_answer",
                    "question": "Explain IDS.",
                    "options": None,
                    "correct_answer": "Monitors for threats.",
                    "explanation": "IDS is passive.",
                    "source_page_ref": 2,
                },
            ]
        )

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_quiz(
                summary="# Summary", extraction=sample_extraction, count=2
            )

        assert len(result) == 2
        assert isinstance(result[0], QuizQuestionData)
        assert result[0].question_type == "multiple_choice"
        assert result[0].options is not None
        assert result[1].question_type == "short_answer"
        assert result[1].options is None

    async def test_generate_quiz_defaults(self, adapter, sample_extraction):
        """Missing fields use defaults."""
        response = json.dumps([{"question": "Q?"}])

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_quiz(summary="", extraction=sample_extraction, count=1)

        assert result[0].question_type == "short_answer"
        assert result[0].correct_answer == ""
        assert result[0].source_page_ref == 1

    async def test_generate_quiz_invalid_json_raises(self, adapter, sample_extraction):
        """Invalid JSON response raises AgentError."""
        with (
            patch.object(adapter, "_run_claude_code", return_value="not json at all"),
            pytest.raises(AgentError, match="Failed to parse JSON array"),
        ):
            await adapter.generate_quiz(summary="", extraction=sample_extraction, count=1)
