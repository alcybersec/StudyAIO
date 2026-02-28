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
_TIMEOUT = 120


class ClaudeCodeAdapter(AgentAdapter):
    """Calls Claude Code CLI via subprocess.

    Uses `claude -p <prompt>` to run prompts. Parses JSON responses
    from Claude for structured output.
    """

    def __init__(self, cli_path: str = "", model: str = ""):
        self._cli_path = cli_path or settings.claude_code_path
        self._model = model or settings.claude_model

    async def _run_claude_code(self, prompt: str) -> str:
        """Execute claude CLI with the given prompt and return output.

        Args:
            prompt: The full prompt text to send.

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
                process.communicate(), timeout=_TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            raise AgentError(f"Claude Code timed out after {_TIMEOUT}s")
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

    async def generate_summary(
        self, extraction: ExtractionData, existing_summary: str | None
    ) -> SummaryResult:
        """Generate a summary by calling Claude Code CLI."""
        # TODO: Implement in summarize stage (Task 1.7)
        raise NotImplementedError("Summary generation not yet implemented")

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
