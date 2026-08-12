"""Tests for ClaudeCodeAdapter."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ExtractionData, SummaryResult
from app.agents.claude_code import ClaudeCodeAdapter
from app.agents.parsing import (
    build_extraction_text,
    collect_image_references,
    parse_json_response,
    parse_summary_response,
)
from app.core.exceptions import AgentError


@pytest.fixture
def adapter():
    """ClaudeCodeAdapter with test config."""
    return ClaudeCodeAdapter(cli_path="/usr/bin/claude", model="test")


class TestRunClaudeCode:
    """Tests for _run_claude_code()."""

    async def test_success(self, adapter):
        """Successful CLI call returns stdout."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output text", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await adapter._run_claude_code("test prompt")

        assert result == "output text"

    async def test_timeout_raises_agent_error(self, adapter):
        """Timeout raises AgentError."""
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = TimeoutError()
        mock_process.kill = MagicMock()

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("asyncio.wait_for", side_effect=TimeoutError()),
            pytest.raises(AgentError, match="timed out"),
        ):
            await adapter._run_claude_code("test prompt")

    async def test_cli_not_found_raises_agent_error(self, adapter):
        """FileNotFoundError raises AgentError."""
        with (
            patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()),
            pytest.raises(AgentError, match="not found"),
        ):
            await adapter._run_claude_code("test prompt")

    async def test_nonzero_exit_raises_agent_error(self, adapter):
        """Non-zero exit code raises AgentError."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"some error")
        mock_process.returncode = 1

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            pytest.raises(AgentError, match="failed"),
        ):
            await adapter._run_claude_code("test prompt")

    async def test_prompt_sent_on_stdin_not_argv(self, adapter):
        """Prompt goes to stdin so it never counts against ARG_MAX."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output text", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await adapter._run_claude_code("test prompt")

        args = mock_exec.call_args[0]
        assert "test prompt" not in args
        assert args == ("/usr/bin/claude", "-p", "--output-format", "text")
        assert mock_exec.call_args[1]["stdin"] is asyncio.subprocess.PIPE
        assert mock_process.communicate.call_args[1]["input"] == b"test prompt"

    async def test_large_prompt_does_not_hit_arg_max(self, adapter):
        """A prompt far larger than ARG_MAX is accepted (regression: Errno 7)."""
        huge_prompt = "x" * (4 * 1024 * 1024)
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"ok", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await adapter._run_claude_code(huge_prompt)

        assert result == "ok"
        assert all(len(arg) < 1024 for arg in mock_exec.call_args[0])
        assert mock_process.communicate.call_args[1]["input"] == huge_prompt.encode()


class TestParseJsonResponse:
    """Tests for parse_json_response() — now in parsing module."""

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

    def test_invalid_json_raises(self):
        """Non-JSON text raises AgentError."""
        with pytest.raises(AgentError, match="Failed to parse JSON"):
            parse_json_response("This is not JSON at all")


class TestClassifyLecture:
    """Tests for classify_lecture()."""

    async def test_classify_success(self, adapter):
        """Successful classification returns ClassificationResult."""
        response = json.dumps(
            {
                "course_code": "CSIT302",
                "week": 5,
                "title": "Network Security",
                "confidence": 0.92,
                "reasoning": "Found in header",
            }
        )

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.classify_lecture(
                "CSIT302 Week 5", "CSIT302_Week5.pdf", ["CSIT302"]
            )

        assert result.course_code == "CSIT302"
        assert result.week == 5
        assert result.confidence == 0.92


class TestParseSummaryResponse:
    """Tests for parse_summary_response() — now in parsing module."""

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


class TestGenerateSummary:
    """Tests for generate_summary()."""

    async def test_generate_new_summary(self, adapter):
        """New summary (no existing) uses summarize.txt template."""
        response = """# CSIT302 — Week 5: Network Security

## Key Concepts
- Firewalls
---JSON_META---
{"embedded_images": []}
---JSON_META---"""

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )

        with patch.object(adapter, "_run_claude_code", return_value=response):
            result = await adapter.generate_summary(extraction, None)

        assert isinstance(result, SummaryResult)
        assert "CSIT302" in result.content_md
        assert "Key Concepts" in result.content_md

    async def test_generate_update_summary(self, adapter):
        """Update summary (with existing) calls with different template."""
        response = """# CSIT302 — Week 5: Network Security (Updated)

## Key Concepts
- Firewalls
- IDS
---JSON_META---
{"embedded_images": []}
---JSON_META---"""

        extraction = ExtractionData(
            pages=[{"page_number": 1, "text": "New content", "images": []}],
            metadata={"course_code": "CSIT302", "week": 5},
        )
        existing = "# Old summary"

        with patch.object(adapter, "_run_claude_code", return_value=response) as mock_run:
            result = await adapter.generate_summary(extraction, existing)

        assert "Updated" in result.content_md or "IDS" in result.content_md
        # Verify it used the longer summary timeout
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("timeout", 120) == 600


class TestBuildExtractionText:
    """Tests for build_extraction_text() — now in parsing module."""

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
    """Tests for collect_image_references() — now in parsing module."""

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
