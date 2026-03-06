"""OpenAI API adapter — calls the OpenAI SDK directly."""

from collections.abc import AsyncIterator

import structlog
from openai import AsyncOpenAI

from app.agents import parsing
from app.agents.base import (
    AgentAdapter,
    AnswerResult,
    ClassificationResult,
    ConceptExtractionResult,
    CourseOpsResult,
    ExtractionData,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)
from app.core.exceptions import AgentError
from app.services.settings_service import get_effective_setting

logger = structlog.get_logger()

# Token limits
_DEFAULT_MAX_TOKENS = 4096
_SUMMARY_MAX_TOKENS = 8192


class OpenAIAdapter(AgentAdapter):
    """Calls the OpenAI Chat Completions API via the official SDK."""

    def __init__(self, api_key: str = "", model: str = ""):
        self._api_key = api_key or get_effective_setting("openai_api_key")
        self._model = model or get_effective_setting("openai_model")

    async def _call_api(self, prompt: str, max_tokens: int = _DEFAULT_MAX_TOKENS) -> str:
        """Send a prompt to the OpenAI API and return the text response.

        Args:
            prompt: The full prompt text.
            max_tokens: Maximum tokens in response.

        Returns:
            Response text content.

        Raises:
            AgentError: If the API call fails.
        """
        if not self._api_key:
            raise AgentError(
                "OpenAI API key not configured. Set it in Settings > AI Configuration."
            )

        client = AsyncOpenAI(api_key=self._api_key)
        logger.info(
            "openai_api_call",
            prompt_length=len(prompt),
            model=self._model,
            max_tokens=max_tokens,
        )

        try:
            response = await client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AgentError(f"OpenAI API call failed: {e}") from e

        choice = response.choices[0]
        result = (choice.message.content or "").strip()

        usage = response.usage
        logger.info(
            "openai_api_response",
            response_length=len(result),
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
        return result

    async def classify_lecture(
        self, text_preview: str, filename: str, known_courses: list[str]
    ) -> ClassificationResult:
        """Classify a lecture by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        template_path = Path("/app/prompts/classify.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                text_preview=text_preview,
                filename=filename,
                known_courses=known_courses,
            )
        else:
            courses_str = ", ".join(known_courses) if known_courses else "none known yet"
            prompt = f"""Analyze this lecture file and classify it.

Filename: {filename}

Known courses in the system: {courses_str}

Text from first pages:
---
{text_preview[:3000]}
---

Respond with ONLY a JSON object (no other text):
{{"course_code": "e.g. CSIT302", "week": 5, "title": "Lecture title", "confidence": 0.85, "reasoning": "Brief explanation"}}
"""

        result_text = await self._call_api(prompt)
        parsed = parsing.parse_json_response(result_text)

        return ClassificationResult(
            course_code=parsed.get("course_code", "UNKNOWN"),
            week=parsed.get("week", 0),
            title=parsed.get("title", ""),
            confidence=parsed.get("confidence", 0.0),
            reasoning=parsed.get("reasoning", ""),
        )

    async def generate_summary(
        self, extraction: ExtractionData, existing_summary: str | None
    ) -> SummaryResult:
        """Generate a summary by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        extraction_text = parsing.build_extraction_text(extraction)
        image_references = parsing.collect_image_references(extraction)
        course_code = extraction.metadata.get("course_code", "UNKNOWN")
        week = extraction.metadata.get("week", 0)

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
            images_block = ""
            if image_references:
                images_block = "\nReferenced images: " + ", ".join(image_references)
            existing_block = ""
            if existing_summary:
                existing_block = (
                    f"\n\nExisting summary to update:\n---\n{existing_summary}\n---\n\n"
                    "Merge the new content with the existing summary."
                )
            prompt = f"""Generate a comprehensive study summary for {course_code} Week {week}.
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

        result_text = await self._call_api(prompt, max_tokens=_SUMMARY_MAX_TOKENS)
        markdown, embedded_images = parsing.parse_summary_response(result_text)

        return SummaryResult(content_md=markdown, embedded_images=embedded_images)

    async def generate_flashcards(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[FlashcardData]:
        """Generate flashcards by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        extraction_text = parsing.build_extraction_text(extraction)
        course_code = extraction.metadata.get("course_code", "UNKNOWN")
        week = extraction.metadata.get("week", 0)

        template_path = Path("/app/prompts/generate_flashcards.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                course_code=course_code,
                week=week,
                summary=summary,
                extraction_text=extraction_text,
                count=count,
            )
        else:
            summary_block = f"\nSummary:\n---\n{summary}\n---\n" if summary else ""
            prompt = f"""Generate exactly {count} flashcards for {course_code} Week {week}.
{summary_block}
Lecture content:
---
{extraction_text}
---

Respond with ONLY a JSON array:
[{{"front": "question", "back": "answer", "tags": ["topic"], "source_page_ref": 1}}]
"""

        result_text = await self._call_api(prompt, max_tokens=_SUMMARY_MAX_TOKENS)
        items = parsing.parse_json_array_response(result_text)

        return [
            FlashcardData(
                front=item.get("front", ""),
                back=item.get("back", ""),
                tags=item.get("tags", []),
                source_page_ref=item.get("source_page_ref", 1),
            )
            for item in items
        ]

    async def generate_quiz(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[QuizQuestionData]:
        """Generate quiz questions by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        extraction_text = parsing.build_extraction_text(extraction)
        course_code = extraction.metadata.get("course_code", "UNKNOWN")
        week = extraction.metadata.get("week", 0)

        template_path = Path("/app/prompts/generate_quiz.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                course_code=course_code,
                week=week,
                summary=summary,
                extraction_text=extraction_text,
                count=count,
            )
        else:
            summary_block = f"\nSummary:\n---\n{summary}\n---\n" if summary else ""
            prompt = f"""Generate exactly {count} quiz questions for {course_code} Week {week}.
Mix ~60% multiple_choice and ~40% short_answer.
{summary_block}
Lecture content:
---
{extraction_text}
---

Respond with ONLY a JSON array:
[{{"question_type": "multiple_choice", "question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "B", "explanation": "...", "source_page_ref": 1}}]
"""

        result_text = await self._call_api(prompt, max_tokens=_SUMMARY_MAX_TOKENS)
        items = parsing.parse_json_array_response(result_text)

        return [
            QuizQuestionData(
                question_type=item.get("question_type", "short_answer"),
                question=item.get("question", ""),
                options=item.get("options"),
                correct_answer=item.get("correct_answer", ""),
                explanation=item.get("explanation", ""),
                source_page_ref=item.get("source_page_ref", 1),
            )
            for item in items
        ]

    async def answer_question(self, question: str, context_chunks: list[dict]) -> AnswerResult:
        """Answer a question by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        template_path = Path("/app/prompts/answer_question.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(question=question, chunks=context_chunks)
        else:
            chunks_text = ""
            for i, chunk in enumerate(context_chunks, 1):
                course = chunk.get("course_code", "Unknown")
                week = chunk.get("week", 0)
                page = chunk.get("page_ref", 0)
                text = chunk.get("text", "")
                chunks_text += f"[{i}] ({course} Week {week}, p.{page})\n{text}\n\n"
            prompt = f"""Answer the following question using ONLY the provided context chunks.

Question: {question}

Context:
{chunks_text}

Respond with ONLY a JSON object:
{{
  "answer": "Your answer with [1] citation markers.",
  "citations": [{{"ref": 1, "chunk_id": "", "text_snippet": "brief quote", "course_code": "CSIT302", "week": 5, "page_ref": 1}}]
}}"""

        result_text = await self._call_api(prompt)
        parsed = parsing.parse_json_response(result_text)

        return AnswerResult(
            answer=parsed.get("answer", ""),
            citations=parsed.get("citations", []),
        )

    async def stream_answer(
        self, question: str, context_chunks: list[dict]
    ) -> AsyncIterator[str]:
        """Stream answer tokens using OpenAI's streaming API.

        Args:
            question: The user's question.
            context_chunks: Relevant text chunks with metadata.

        Yields:
            Text token strings as they arrive from the API.
        """
        from pathlib import Path

        from jinja2 import Template

        template_path = Path("/app/prompts/answer_question.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(question=question, chunks=context_chunks)
        else:
            chunks_text = ""
            for i, chunk in enumerate(context_chunks, 1):
                course = chunk.get("course_code", "Unknown")
                week = chunk.get("week", 0)
                page = chunk.get("page_ref", 0)
                text = chunk.get("text", "")
                chunks_text += f"[{i}] ({course} Week {week}, p.{page})\n{text}\n\n"
            prompt = f"""Answer the following question using ONLY the provided context chunks.

Question: {question}

Context:
{chunks_text}

Respond with ONLY a JSON object:
{{
  "answer": "Your answer with [1] citation markers.",
  "citations": [{{"ref": 1, "chunk_id": "", "text_snippet": "brief quote", "course_code": "CSIT302", "week": 5, "page_ref": 1}}]
}}"""

        if not self._api_key:
            raise AgentError(
                "OpenAI API key not configured. Set it in Settings > AI Configuration."
            )

        client = AsyncOpenAI(api_key=self._api_key)
        logger.info(
            "openai_stream_start",
            prompt_length=len(prompt),
            model=self._model,
        )

        try:
            stream = await client.chat.completions.create(
                model=self._model,
                max_tokens=_DEFAULT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            raise AgentError(f"OpenAI streaming failed: {e}") from e

    async def extract_course_ops(
        self, document_text: str, course_code: str, document_type: str
    ) -> CourseOpsResult:
        """Extract course logistics by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        template_path = Path("/app/prompts/extract_course_ops.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                document_text=document_text,
                course_code=course_code,
                document_type=document_type,
            )
        else:
            prompt = f"""Extract assessments, deadlines, and course information from this {document_type} for {course_code}.

Document content:
---
{document_text[:8000]}
---

Respond with ONLY a JSON object:
{{
  "assessments": [{{"title": "Final Exam", "assessment_type": "exam", "weight_pct": 40.0, "description": "Covers weeks 1-13", "weeks_relevant": [1, 2, 3]}}],
  "deadlines": [{{"title": "Assignment 1 Due", "due_date": "2026-04-15", "deadline_type": "assignment", "description": "Submit via Moodle"}}],
  "course_info": {{"course_name": "Software Engineering", "term": "Spring 2026", "instructor": "Dr. Smith"}},
  "confidence": 0.85
}}

Rules:
- assessment_type/deadline_type: one of "exam", "assignment", "quiz", "project", "lab", "presentation", "other"
- due_date: ISO format YYYY-MM-DD
- weight_pct: percentage as a float (e.g., 40.0 for 40%). null if not specified.
- confidence: 0.0 to 1.0
"""

        result_text = await self._call_api(prompt, max_tokens=_SUMMARY_MAX_TOKENS)
        return parsing.parse_course_ops_response(result_text)

    async def extract_concepts(
        self, text: str, existing_concepts: list[str] | None = None
    ) -> ConceptExtractionResult:
        """Extract concepts and relationships by calling the OpenAI API."""
        from pathlib import Path

        from jinja2 import Template

        template_path = Path("/app/prompts/extract_concepts.txt")
        if template_path.exists():
            template = Template(template_path.read_text())
            prompt = template.render(
                text=text[:8000],
                existing_concepts=", ".join(existing_concepts) if existing_concepts else "",
            )
        else:
            existing_block = ""
            if existing_concepts:
                existing_block = f"\nExisting concepts: {', '.join(existing_concepts)}\n"
            prompt = f"""Extract key concepts and relationships from this lecture content.
{existing_block}
Content:
---
{text[:8000]}
---

Respond with ONLY a JSON object:
{{"concepts": [{{"name": "...", "description": "...", "category": "general"}}], "relations": [{{"source": "...", "target": "...", "relation_type": "related_to", "confidence": 0.8}}]}}
"""

        result_text = await self._call_api(prompt)
        return parsing.parse_concept_extraction_response(result_text)
