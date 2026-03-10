"""Tests for shared parsing helpers."""

import pytest

from app.agents.base import ExtractionData
from app.agents.parsing import (
    _clean_json_text,
    build_extraction_text,
    collect_image_references,
    parse_json_array_response,
    parse_json_response,
    parse_summary_response,
)
from app.core.exceptions import AgentError


class TestParseJsonResponse:
    """Tests for parse_json_response()."""

    def test_direct_json(self):
        """Direct JSON string is parsed."""
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_code_fence(self):
        """JSON in code fences is extracted."""
        text = 'Here is the result:\n```json\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_code_fence_without_language(self):
        """Code fences without language identifier work."""
        text = '```\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_invalid_json_raises_agent_error(self):
        """Non-JSON text raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON"):
            parse_json_response("This is not JSON at all")

    def test_json_with_prose_preamble(self):
        """JSON preceded by prose text is extracted."""
        text = 'Sure, here is the JSON:\n{"course_code": "CSIT302", "week": 5}'
        result = parse_json_response(text)
        assert result["course_code"] == "CSIT302"
        assert result["week"] == 5

    def test_json_with_trailing_comma(self):
        """Trailing comma before } is handled."""
        text = '{"key": "value", "num": 42,}'
        result = parse_json_response(text)
        assert result == {"key": "value", "num": 42}

    def test_json_with_trailing_text(self):
        """JSON followed by explanation text is extracted."""
        text = '{"key": "value"}\n\nThis is the classification result above.'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_nested_in_explanation(self):
        """JSON buried in explanation paragraphs."""
        text = (
            "Based on my analysis, I determined the following:\n\n"
            '{"course_code": "TEST101", "confidence": 0.85}\n\n'
            "The confidence is high because..."
        )
        result = parse_json_response(text)
        assert result["course_code"] == "TEST101"

    def test_json_with_multiple_trailing_commas(self):
        """Multiple trailing commas are cleaned."""
        text = '{"a": [1, 2, 3,], "b": {"c": 4,},}'
        result = parse_json_response(text)
        assert result == {"a": [1, 2, 3], "b": {"c": 4}}


class TestParseJsonArrayResponse:
    """Tests for parse_json_array_response()."""

    def test_direct_array(self):
        """Direct JSON array is parsed."""
        result = parse_json_array_response('[{"front": "Q1", "back": "A1"}]')
        assert result == [{"front": "Q1", "back": "A1"}]

    def test_array_in_code_fence(self):
        """JSON array in code fences is extracted."""
        text = 'Here are the flashcards:\n```json\n[{"front": "Q1", "back": "A1"}]\n```'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q1", "back": "A1"}]

    def test_invalid_json_raises_agent_error(self):
        """Non-JSON text raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON array"):
            parse_json_array_response("not an array")

    def test_dict_instead_of_array_raises(self):
        """A JSON object (not array) raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON array"):
            parse_json_array_response('{"key": "value"}')

    def test_array_with_prose_preamble(self):
        """Array preceded by prose text is extracted."""
        text = 'Here are the flashcards:\n[{"front": "Q1", "back": "A1"}]'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q1", "back": "A1"}]

    def test_array_with_trailing_comma(self):
        """Trailing comma before ] is handled."""
        text = '[{"front": "Q1", "back": "A1"},]'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q1", "back": "A1"}]

    def test_array_with_trailing_text(self):
        """Array followed by explanation text is extracted."""
        text = '[{"front": "Q1", "back": "A1"}]\n\nThese flashcards cover the basics.'
        result = parse_json_array_response(text)
        assert result == [{"front": "Q1", "back": "A1"}]

    def test_array_nested_in_explanation(self):
        """Array buried in explanation."""
        text = (
            "I generated these flashcards for you:\n\n"
            '[{"front": "Q1", "back": "A1"}]\n\n'
            "Let me know if you need more."
        )
        result = parse_json_array_response(text)
        assert result == [{"front": "Q1", "back": "A1"}]


class TestCleanJsonText:
    """Tests for _clean_json_text()."""

    def test_removes_trailing_comma_before_brace(self):
        """Trailing comma before } is removed."""
        result = _clean_json_text('{"a": 1,}')
        assert '"a": 1}' in result

    def test_removes_trailing_comma_before_bracket(self):
        """Trailing comma before ] is removed."""
        result = _clean_json_text("[1, 2, 3,]")
        assert "3]" in result

    def test_strips_prose_preamble(self):
        """Prose before JSON is stripped."""
        result = _clean_json_text('Sure, here it is: {"key": "value"}')
        assert result.startswith("{")
        assert result.endswith("}")

    def test_single_quotes_converted(self):
        """Single quotes are converted to double when no double quotes present."""
        result = _clean_json_text("{'key': 'value'}")
        assert '"key"' in result
        assert '"value"' in result

    def test_double_quotes_preserved(self):
        """Existing double quotes are not changed."""
        text = '{"key": "value"}'
        result = _clean_json_text(text)
        assert '"key"' in result


class TestParseSummaryResponse:
    """Tests for parse_summary_response()."""

    def test_with_meta_block(self):
        """Response with JSON_META block is parsed correctly."""
        text = """# Summary content here

## Key Concepts
- Item 1
---JSON_META---
{"embedded_images": ["img1.png", "img2.png"]}
---JSON_META---"""

        markdown, images = parse_summary_response(text)

        assert "# Summary content here" in markdown
        assert images == ["img1.png", "img2.png"]

    def test_without_meta_block(self):
        """Response without JSON_META returns full text."""
        text = "# Summary content here\n\n## Key Concepts\n- Item 1"

        markdown, images = parse_summary_response(text)

        assert markdown == text
        assert images == []

    def test_with_invalid_meta_json(self):
        """Invalid JSON in meta block returns empty images."""
        text = """# Summary
---JSON_META---
not json
---JSON_META---"""

        markdown, images = parse_summary_response(text)

        assert "# Summary" in markdown
        assert images == []


class TestBuildExtractionText:
    """Tests for build_extraction_text()."""

    def test_dict_pages(self):
        """Works with dict pages (from manifest)."""
        extraction = ExtractionData(
            pages=[
                {"page_number": 1, "text": "First page", "images": []},
                {"page_number": 2, "text": "Second page", "images": []},
            ],
            metadata={},
        )

        result = build_extraction_text(extraction)

        assert "Page 1" in result
        assert "First page" in result
        assert "Page 2" in result
        assert "Second page" in result

    def test_empty_pages_skipped(self):
        """Pages with empty text are skipped."""
        extraction = ExtractionData(
            pages=[
                {"page_number": 1, "text": "Content", "images": []},
                {"page_number": 2, "text": "   ", "images": []},
            ],
            metadata={},
        )

        result = build_extraction_text(extraction)

        assert "Page 1" in result
        assert "Page 2" not in result


class TestCollectImageReferences:
    """Tests for collect_image_references()."""

    def test_collects_from_dict_pages(self):
        """Collects image filenames from dict pages."""
        extraction = ExtractionData(
            pages=[
                {
                    "page_number": 1,
                    "text": "Content",
                    "images": [
                        {"filename": "img1.png", "caption": "", "position": "page_1"},
                        {"filename": "img2.jpg", "caption": "", "position": "page_1"},
                    ],
                },
            ],
            metadata={},
        )

        result = collect_image_references(extraction)

        assert result == ["img1.png", "img2.jpg"]

    def test_empty_images(self):
        """No images returns empty list."""
        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={},
        )

        result = collect_image_references(extraction)

        assert result == []

    def test_skips_empty_filenames(self):
        """Images with empty filename are skipped."""
        extraction = ExtractionData(
            pages=[
                {
                    "page_number": 1,
                    "text": "Content",
                    "images": [
                        {"filename": "", "caption": "", "position": "page_1"},
                        {"filename": "real.png", "caption": "", "position": "page_1"},
                    ],
                },
            ],
            metadata={},
        )

        result = collect_image_references(extraction)

        assert result == ["real.png"]
