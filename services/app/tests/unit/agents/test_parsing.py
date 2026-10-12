"""Tests for shared parsing helpers."""

import pytest

from app.agents import parsing
from app.agents.base import ExtractionData
from app.agents.parsing import (
    _clean_json_text,
    build_extraction_text,
    collect_image_references,
    find_must_keep_items,
    normalise_summary_footer,
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


class TestExtractionCitationMarkers:
    """Page headers carry a citation marker the summary can copy (GL#34)."""

    def test_single_document_marker(self):
        extraction = ExtractionData(
            pages=[{"page_number": 3, "text": "Body", "images": []}], metadata={}
        )
        assert "--- Page 3 [p.3] ---" in build_extraction_text(extraction)

    def test_multiple_documents_get_distinct_markers(self):
        """Page numbers restart per file after a merge, so markers must not collide."""
        extraction = ExtractionData(
            pages=[
                {"page_number": 1, "text": "a", "images": []},
                {"page_number": 2, "text": "b", "images": []},
                {"page_number": 1, "text": "c", "images": []},
            ],
            metadata={},
        )
        result = build_extraction_text(extraction)
        assert "[D1 p.2]" in result
        assert "[D2 p.1]" in result
        assert "[p.1]" not in result

    def test_source_key_groups_documents(self):
        extraction = ExtractionData(
            pages=[
                {"page_number": 1, "text": "a", "source": "x"},
                {"page_number": 1, "text": "b", "source": "y"},
            ],
            metadata={},
        )
        result = build_extraction_text(extraction)
        assert "[D1 p.1]" in result and "[D2 p.1]" in result


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

        assert result == [
            "img1.png (page 1: Content)",
            "img2.jpg (page 1: Content)",
        ]

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

        assert result == ["real.png (page 1: Content)"]


class TestFindMustKeepItems:
    """Formula / recurrence / worked-example lines the summary must not drop (GL#34)."""

    def _extraction(self, *texts: str) -> ExtractionData:
        pages = [{"page_number": i, "text": t, "images": []} for i, t in enumerate(texts, 1)]
        return ExtractionData(pages=pages, metadata={})

    def test_formula_and_example_lines_carry_their_page_marker(self):
        ex = self._extraction(
            "Intro prose with no maths in it at all.",
            "Recurrence:\nbest[i][c] = best[i-1][c] if w_i > c\nBase case: best[0][c] = 0 for all c.",
            "Worked example: W = 5, items (w=2, v=3). Best value 7.\nTime is O(nW).",
        )
        items = find_must_keep_items(ex)
        assert "[p.2] best[i][c] = best[i-1][c] if w_i > c" in items
        assert "[p.2] Base case: best[0][c] = 0 for all c." in items
        assert any(i.startswith("[p.3] Worked example: W = 5") for i in items)
        assert "[p.3] Time is O(nW)." in items
        assert not any("Intro prose" in i for i in items)

    def test_markers_follow_merged_documents(self):
        ex = ExtractionData(
            pages=[
                {"page_number": 1, "text": "x = 1 + 2", "source": "a.pdf", "images": []},
                {"page_number": 1, "text": "y = 3 + 4", "source": "b.pdf", "images": []},
            ],
            metadata={},
        )
        assert find_must_keep_items(ex) == ["[D1 p.1] x = 1 + 2", "[D2 p.1] y = 3 + 4"]

    def test_capped_deduplicated_and_truncated(self):
        long_line = "a = " + "b" * 400
        ex = self._extraction("\n".join([f"v{i} = {i}" for i in range(80)] + [long_line, "v1 = 1"]))
        items = find_must_keep_items(ex)
        assert len(items) <= 40
        assert all(len(i) <= 260 for i in items)
        assert len(items) == len(set(items))

    def test_no_formulas_gives_empty_list(self):
        assert find_must_keep_items(self._extraction("Just words here.")) == []


class TestNormaliseSummaryFooter:
    """The footer is exactly `---` then the Sources line (GL#34)."""

    GOOD = "## Connections\n\nText.\n\n---\n*Sources: Notes (pp. 1-3). Version: 1.*"

    def test_glued_separator_is_split(self):
        """Observed shape: `---*Sources: ...` on one line."""
        out = normalise_summary_footer(
            "## Connections\n\nText.\n\n---*Sources: Notes (pp. 1-3). Version: 1.*\n"
        )
        assert out == self.GOOD

    def test_missing_separator_is_added(self):
        """Observed shape: a Sources line with no `---` above it."""
        out = normalise_summary_footer(
            "## Connections\n\nText.\n*Sources: Notes (pp. 1-3). Version: 1.*"
        )
        assert out == self.GOOD

    def test_blank_lines_and_trailing_whitespace_are_tidied(self):
        out = normalise_summary_footer(
            "## Connections\n\nText.\n\n\n---  \n\n  *Sources: Notes (pp. 1-3). Version: 1.*   \n\n"
        )
        assert out == self.GOOD

    def test_separator_jammed_under_paragraph_gets_a_blank_line(self):
        """`Text.\n---` would render as a setext heading."""
        out = normalise_summary_footer("Text.\n---\n*Sources: Notes. Version: 1.*")
        assert out == "Text.\n\n---\n*Sources: Notes. Version: 1.*"

    def test_well_formed_footer_is_unchanged_and_idempotent(self):
        assert normalise_summary_footer(self.GOOD) == self.GOOD
        assert normalise_summary_footer(
            normalise_summary_footer("a\n---*Sources: x. Version: 2.*")
        ) == ("a\n\n---\n*Sources: x. Version: 2.*")

    def test_no_sources_line_is_left_alone_and_counted(self):
        text = "## Connections\n\nText."
        counter = parsing.SUMMARY_FOOTER.labels(outcome="no_sources")
        before = counter._value.get()
        assert normalise_summary_footer(text) == text
        assert counter._value.get() == before + 1

    def test_parse_summary_response_normalises_before_meta(self):
        raw = '# T\n\nbody\n\n---*Sources: n. Version: 1.*\n---JSON_META---\n{"embedded_images": []}\n---JSON_META---'
        markdown, _ = parse_summary_response(raw)
        assert markdown.endswith("\n\n---\n*Sources: n. Version: 1.*")
