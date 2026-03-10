"""Tests for CourseOps extraction in agent adapters."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base import CourseOpsResult
from app.agents.parsing import parse_course_ops_response
from app.core.exceptions import AgentError


class TestParseCourseOpsResponse:
    """Tests for parse_course_ops_response."""

    def test_parses_valid_response(self):
        """Parses a well-formed JSON response."""
        text = json.dumps(
            {
                "assessments": [
                    {
                        "title": "Final Exam",
                        "assessment_type": "exam",
                        "weight_pct": 40.0,
                        "description": "Covers all weeks",
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
                "course_info": {
                    "course_name": "Software Engineering",
                    "term": "Spring 2026",
                },
                "confidence": 0.85,
            }
        )

        result = parse_course_ops_response(text)
        assert isinstance(result, CourseOpsResult)
        assert len(result.assessments) == 1
        assert result.assessments[0].title == "Final Exam"
        assert result.assessments[0].weight_pct == 40.0
        assert result.assessments[0].weeks_relevant == [1, 2, 3]
        assert len(result.deadlines) == 1
        assert result.deadlines[0].due_date == "2026-04-15"
        assert result.course_info["course_name"] == "Software Engineering"
        assert result.confidence == 0.85

    def test_parses_response_in_code_fence(self):
        """Parses JSON wrapped in markdown code fences."""
        text = """```json
{
  "assessments": [{"title": "Quiz 1", "assessment_type": "quiz"}],
  "deadlines": [],
  "course_info": {},
  "confidence": 0.6
}
```"""
        result = parse_course_ops_response(text)
        assert len(result.assessments) == 1
        assert result.assessments[0].title == "Quiz 1"

    def test_handles_empty_lists(self):
        """Handles response with empty assessments and deadlines."""
        text = json.dumps(
            {
                "assessments": [],
                "deadlines": [],
                "course_info": {},
                "confidence": 0.3,
            }
        )

        result = parse_course_ops_response(text)
        assert result.assessments == []
        assert result.deadlines == []
        assert result.confidence == 0.3

    def test_defaults_missing_fields(self):
        """Uses defaults when fields are missing from items."""
        text = json.dumps(
            {
                "assessments": [{"title": "Exam"}],
                "deadlines": [{"title": "Due", "due_date": "2026-05-01"}],
            }
        )

        result = parse_course_ops_response(text)
        assert result.assessments[0].assessment_type == "other"
        assert result.assessments[0].weight_pct is None
        assert result.assessments[0].weeks_relevant == []
        assert result.deadlines[0].deadline_type == "other"
        assert result.confidence == 0.0

    def test_raises_for_invalid_json(self):
        """Raises AgentError for unparseable response."""
        with pytest.raises(AgentError):
            parse_course_ops_response("not json at all")


class TestClaudeCodeAdapterExtractCourseOps:
    """Tests for ClaudeCodeAdapter.extract_course_ops."""

    @pytest.mark.asyncio
    async def test_calls_cli_and_parses(self):
        """Calls Claude CLI and returns CourseOpsResult."""
        from app.agents.claude_code import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")

        response_json = json.dumps(
            {
                "assessments": [
                    {"title": "Midterm", "assessment_type": "exam", "weight_pct": 30.0}
                ],
                "deadlines": [
                    {"title": "Midterm Date", "due_date": "2026-04-20", "deadline_type": "exam"}
                ],
                "course_info": {"course_name": "Data Structures"},
                "confidence": 0.9,
            }
        )

        with patch.object(
            adapter, "_run_claude_code", new_callable=AsyncMock, return_value=response_json
        ):
            result = await adapter.extract_course_ops("doc text", "CSIT302", "outline")

        assert isinstance(result, CourseOpsResult)
        assert len(result.assessments) == 1
        assert result.assessments[0].title == "Midterm"
        assert len(result.deadlines) == 1

    @pytest.mark.asyncio
    async def test_raises_on_cli_failure(self):
        """Raises AgentError when CLI fails."""
        from app.agents.claude_code import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="sonnet")

        with (
            patch.object(
                adapter,
                "_run_claude_code",
                new_callable=AsyncMock,
                side_effect=AgentError("CLI failed"),
            ),
            pytest.raises(AgentError),
        ):
            await adapter.extract_course_ops("text", "CSIT302", "outline")


class TestAnthropicAPIAdapterExtractCourseOps:
    """Tests for AnthropicAPIAdapter.extract_course_ops."""

    @pytest.mark.asyncio
    async def test_calls_api_and_parses(self):
        """Calls Anthropic API and returns CourseOpsResult."""
        from app.agents.anthropic_api import AnthropicAPIAdapter

        adapter = AnthropicAPIAdapter(api_key="test-key", model="sonnet")

        response_json = json.dumps(
            {
                "assessments": [
                    {"title": "Project", "assessment_type": "project", "weight_pct": 25.0}
                ],
                "deadlines": [],
                "course_info": {},
                "confidence": 0.7,
            }
        )

        with patch.object(adapter, "_call_api", new_callable=AsyncMock, return_value=response_json):
            result = await adapter.extract_course_ops("doc text", "CSIT314", "rubric")

        assert isinstance(result, CourseOpsResult)
        assert len(result.assessments) == 1
        assert result.assessments[0].assessment_type == "project"
