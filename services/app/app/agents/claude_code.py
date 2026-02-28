"""Claude Code CLI adapter — calls `claude -p` via subprocess."""

import asyncio
import json

import structlog

from app.config import settings
from app.core.exceptions import AgentError
from app.agents.base import (
    AgentAdapter,
    AnswerResult,
    ClassificationResult,
    ExtractionData,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)

logger = structlog.get_logger()

# Timeout for Claude Code CLI calls (seconds)
_DEFAULT_TIMEOUT = 120
_SUMMARY_TIMEOUT = 300


class ClaudeCodeAdapter(AgentAdapter):
    """Calls Claude Code CLI via subprocess.

    Uses `claude -p <prompt>` to run prompts. Parses JSON responses
    from Claude for structured output.
    """

    def __init__(self, cli_path: str = "", model: str = ""):
        self._cli_path = cli_path or settings.claude_code_path
        self._model = model or settings.claude_model

    async def _run_claude_code(self, prompt: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
        """Execute claude CLI with the given prompt and return output.

        Args:
            prompt: The full prompt text to send.
            timeout: Timeout in seconds (default 120, use 300 for summaries).

        Returns:
            Raw stdout from the CLI.

        Raises:
            AgentError: If the CLI fails or times out.
        """
        cmd = [self._cli_path, "-p", prompt, "--output-format", "text"]
        logger.info(
            "claude_code_call",
            prompt_length=len(prompt),
            model=self._model,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise AgentError(f"Claude Code timed out after {timeout}s")
        except FileNotFoundError:
            raise AgentError(
                f"Claude Code CLI not found at '{self._cli_path}'. "
                "Ensure it is installed and accessible."
            )

        if process.returncode != 0:
            error_text = stderr.decode().strip() if stderr else "Unknown error"
            raise AgentError(f"Claude Code failed (exit {process.returncode}): {error_text}")

        result = stdout.decode().strip()
        logger.info("claude_code_response", response_length=len(result))
        return result

    def _parse_json_response(self, text: str) -> dict:
        """Extract and parse JSON from Claude's response.

        Handles responses that may contain markdown code fences.

        Args:
            text: Raw response text.

        Returns:
            Parsed dict.

        Raises:
            AgentError: If JSON parsing fails.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code fences
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                # Skip language identifier lines
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

        raise AgentError(f"Failed to parse JSON from Claude response: {text[:200]}...")

    async def classify_lecture(
        self, text_preview: str, filename: str, known_courses: list[str]
    ) -> ClassificationResult:
        """Classify a lecture by calling Claude Code CLI."""
        from jinja2 import Template
        from pathlib import Path

        template_path = Path("/app/prompts/classify.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                text_preview=text_preview,
                filename=filename,
                known_courses=known_courses,
            )
        else:
            prompt = self._build_classification_prompt(
                text_preview, filename, known_courses
            )

        result_text = await self._run_claude_code(prompt)
        parsed = self._parse_json_response(result_text)

        return ClassificationResult(
            course_code=parsed.get("course_code", "UNKNOWN"),
            week=parsed.get("week", 0),
            title=parsed.get("title", ""),
            confidence=parsed.get("confidence", 0.0),
            reasoning=parsed.get("reasoning", ""),
        )

    def _build_classification_prompt(
        self, text_preview: str, filename: str, known_courses: list[str]
    ) -> str:
        """Build classification prompt as fallback when template is missing."""
        courses_str = ", ".join(known_courses) if known_courses else "none known yet"
        return f"""Analyze this lecture file and classify it.

Filename: {filename}

Known courses in the system: {courses_str}

Text from first pages:
---
{text_preview[:3000]}
---

Respond with ONLY a JSON object (no other text):
{{
  "course_code": "e.g. CSIT302",
  "week": 5,
  "title": "Lecture title",
  "confidence": 0.85,
  "reasoning": "Brief explanation of how you determined the classification"
}}

Rules:
- course_code: Extract from filename or content. Use format like CSIT302, ISIT312, etc.
- week: Extract week/lecture number. Use 0 if unknown.
- title: Extract or infer the lecture topic title.
- confidence: 0.0 to 1.0. High if course+week clearly stated, low if guessing.
"""

    def _build_extraction_text(self, extraction: ExtractionData) -> str:
        """Format extraction pages into a text block for prompts.

        Args:
            extraction: Extraction data with pages.

        Returns:
            Formatted text string.
        """
        parts: list[str] = []
        for page in extraction.pages:
            text = page.get("text", "") if isinstance(page, dict) else page.text
            page_num = page.get("page_number", 0) if isinstance(page, dict) else page.page_number
            if text.strip():
                parts.append(f"--- Page {page_num} ---\n{text}")
        return "\n\n".join(parts)

    def _collect_image_references(self, extraction: ExtractionData) -> list[str]:
        """Gather image filenames from extraction pages.

        Args:
            extraction: Extraction data with pages.

        Returns:
            List of image filenames.
        """
        images: list[str] = []
        for page in extraction.pages:
            page_images = page.get("images", []) if isinstance(page, dict) else page.images
            for img in page_images:
                filename = img.get("filename", "") if isinstance(img, dict) else img.filename
                if filename:
                    images.append(filename)
        return images

    def _parse_summary_response(self, text: str) -> tuple[str, list[str]]:
        """Split summary markdown from JSON_META block.

        Args:
            text: Raw response from Claude.

        Returns:
            Tuple of (markdown_content, embedded_images list).
        """
        embedded_images: list[str] = []

        if "---JSON_META---" in text:
            parts = text.split("---JSON_META---")
            markdown = parts[0].strip()
            if len(parts) >= 2:
                meta_text = parts[1].strip()
                try:
                    meta = json.loads(meta_text)
                    embedded_images = meta.get("embedded_images", [])
                except json.JSONDecodeError:
                    logger.warning("failed_to_parse_summary_meta", meta_text=meta_text[:100])
        else:
            markdown = text.strip()

        return markdown, embedded_images

    def _build_summary_prompt(
        self,
        extraction_text: str,
        image_references: list[str],
        course_code: str,
        week: int,
        existing_summary: str | None,
    ) -> str:
        """Build summary prompt as fallback when template is missing.

        Args:
            extraction_text: Formatted text from extraction.
            image_references: List of image filenames.
            course_code: Course code.
            week: Week number.
            existing_summary: Previous summary if updating.

        Returns:
            Complete prompt string.
        """
        images_block = ""
        if image_references:
            images_block = "\nReferenced images: " + ", ".join(image_references)

        existing_block = ""
        if existing_summary:
            existing_block = f"\n\nExisting summary to update:\n---\n{existing_summary}\n---\n\nMerge the new content with the existing summary."

        return f"""Generate a comprehensive study summary for {course_code} Week {week}.
{existing_block}
Lecture content:
---
{extraction_text}
---
{images_block}

Create a markdown summary with these sections:
1. # {course_code} — Week {week}: <Topic>
2. ## Key Concepts
3. ## Definitions (table: Term | Definition)
4. ## Code Examples
5. ## Diagrams & Figures
6. ## Potential Exam Topics
7. ## Summary (2-3 paragraphs)
8. Footer with sources and version

After the summary, emit:
---JSON_META---
{{"embedded_images": []}}
---JSON_META---
"""

    async def generate_summary(
        self, extraction: ExtractionData, existing_summary: str | None
    ) -> SummaryResult:
        """Generate a summary by calling Claude Code CLI.

        Args:
            extraction: Extraction data with pages and metadata.
            existing_summary: Previous summary markdown if updating.

        Returns:
            SummaryResult with markdown content and embedded images.
        """
        from jinja2 import Template
        from pathlib import Path

        extraction_text = self._build_extraction_text(extraction)
        image_references = self._collect_image_references(extraction)
        course_code = extraction.metadata.get("course_code", "UNKNOWN")
        week = extraction.metadata.get("week", 0)

        # Select template based on whether we're updating
        if existing_summary:
            template_path = Path("/app/prompts/summarize_update.txt")
        else:
            template_path = Path("/app/prompts/summarize.txt")

        if template_path.exists():
            template = Template(template_path.read_text())
            render_vars = {
                "course_code": course_code,
                "week": week,
                "extraction_text": extraction_text,
                "image_references": image_references,
            }
            if existing_summary:
                render_vars["existing_summary"] = existing_summary
            prompt = template.render(**render_vars)
        else:
            prompt = self._build_summary_prompt(
                extraction_text, image_references, course_code, week, existing_summary
            )

        result_text = await self._run_claude_code(prompt, timeout=_SUMMARY_TIMEOUT)
        markdown, embedded_images = self._parse_summary_response(result_text)

        return SummaryResult(
            content_md=markdown,
            embedded_images=embedded_images,
        )

    async def generate_flashcards(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[FlashcardData]:
        """Generate flashcards by calling Claude Code CLI."""
        # TODO: Implement in assets stage (Task 1.9)
        raise NotImplementedError("Flashcard generation not yet implemented")

    async def generate_quiz(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[QuizQuestionData]:
        """Generate quiz questions by calling Claude Code CLI."""
        # TODO: Implement in assets stage (Task 1.9)
        raise NotImplementedError("Quiz generation not yet implemented")

    async def answer_question(
        self, question: str, context_chunks: list[dict]
    ) -> AnswerResult:
        """Answer a question by calling Claude Code CLI."""
        # TODO: Implement in Q&A feature (Milestone 2)
        raise NotImplementedError("Q&A not yet implemented")
