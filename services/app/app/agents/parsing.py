"""Shared parsing helpers for agent adapters.

Extracts structured data from raw AI responses. Used by
ClaudeCodeAdapter, AnthropicAPIAdapter, OpenAIAdapter, and OllamaAdapter.
Includes resilient parsing for less reliable LLMs (trailing commas,
single quotes, prose preamble, etc.).
"""

import json
import re

import structlog

from app.agents.base import (
    ConceptData,
    ConceptExtractionResult,
    ConceptRelationData,
    CourseOpsAssessment,
    CourseOpsDeadline,
    CourseOpsResult,
    ExtractionData,
)
from app.core.exceptions import AgentError

logger = structlog.get_logger()


def _clean_json_text(text: str) -> str:
    """Apply best-effort fixes to malformed JSON from LLMs.

    Handles:
    - Trailing commas before ] or }
    - Single-quoted strings
    - Prose preamble (e.g. "Sure, here's the JSON:")

    Args:
        text: Raw text that should contain JSON.

    Returns:
        Cleaned text more likely to parse as JSON.
    """
    # Strip prose preamble before JSON
    # Find the first { or [ — whichever comes first is the JSON start
    brace_idx = text.find("{")
    bracket_idx = text.find("[")

    candidates: list[tuple[int, str, str]] = []
    if brace_idx != -1:
        rbrace = text.rfind("}")
        if rbrace > brace_idx:
            candidates.append((brace_idx, "{", "}"))
    if bracket_idx != -1:
        rbracket = text.rfind("]")
        if rbracket > bracket_idx:
            candidates.append((bracket_idx, "[", "]"))

    if candidates:
        # Pick the one that starts earliest
        candidates.sort(key=lambda x: x[0])
        idx, start_char, end_char = candidates[0]
        ridx = text.rfind(end_char)
        text = text[idx : ridx + 1]

    # Remove trailing commas before closing brackets
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Replace single quotes with double quotes (basic heuristic)
    # Only if there are no double quotes already (to avoid breaking valid JSON)
    if '"' not in text and "'" in text:
        text = text.replace("'", '"')

    return text


def parse_json_response(text: str) -> dict:
    """Extract and parse a JSON object from an AI response.

    Handles responses that may contain markdown code fences, prose preamble,
    trailing commas, and single-quoted strings.

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

    # Fallback: extract first { to last } with cleaning
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        # Try with cleaning
        cleaned = _clean_json_text(candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Last resort: clean entire text
    cleaned = _clean_json_text(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    raise AgentError(f"Failed to parse JSON from AI response: {text[:200]}...")


def parse_json_array_response(text: str) -> list[dict]:
    """Extract and parse a JSON array from an AI response.

    Handles responses that may contain markdown code fences, prose preamble,
    trailing commas, and single-quoted strings.

    Args:
        text: Raw response text.

    Returns:
        Parsed list of dicts.

    Raises:
        AgentError: If JSON parsing fails or result is not a list.
    """
    # Try direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                continue

    # Fallback: extract first [ to last ] with cleaning
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket : last_bracket + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        # Try with cleaning
        cleaned = _clean_json_text(candidate)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Last resort: clean entire text
    cleaned = _clean_json_text(text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    raise AgentError(f"Failed to parse JSON array from AI response: {text[:200]}...")


def parse_summary_response(text: str) -> tuple[str, list[str]]:
    """Split summary markdown from ---JSON_META--- block.

    Args:
        text: Raw response from the AI.

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


def build_extraction_text(extraction: ExtractionData) -> str:
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


def collect_image_references(extraction: ExtractionData) -> list[str]:
    """Gather image filenames with page context from extraction pages.

    Returns each image as a string with filename and surrounding text context
    so the AI can correctly identify what each image depicts.

    Args:
        extraction: Extraction data with pages.

    Returns:
        List of image reference strings with context.
    """
    images: list[str] = []
    for page in extraction.pages:
        page_dict = page if isinstance(page, dict) else page.__dict__
        page_num = page_dict.get("page_number", "?")
        page_text = page_dict.get("text", "")
        # Extract a short context snippet (first 150 chars of page text)
        context = page_text[:150].replace("\n", " ").strip()
        if len(page_text) > 150:
            context += "..."

        page_images = page_dict.get("images", [])
        for img in page_images:
            filename = img.get("filename", "") if isinstance(img, dict) else img.filename
            if filename:
                images.append(f"{filename} (page {page_num}: {context})")
    return images


def parse_course_ops_response(text: str) -> CourseOpsResult:
    """Parse a CourseOps extraction response from the AI.

    Args:
        text: Raw AI response text.

    Returns:
        CourseOpsResult with assessments, deadlines, and metadata.

    Raises:
        AgentError: If JSON parsing fails.
    """
    parsed = parse_json_response(text)

    assessments = [
        CourseOpsAssessment(
            title=a.get("title", ""),
            assessment_type=a.get("assessment_type", "other"),
            weight_pct=a.get("weight_pct"),
            description=a.get("description", ""),
            weeks_relevant=a.get("weeks_relevant", []),
        )
        for a in parsed.get("assessments", [])
    ]

    deadlines = [
        CourseOpsDeadline(
            title=d.get("title", ""),
            due_date=d.get("due_date", ""),
            deadline_type=d.get("deadline_type", "other"),
            description=d.get("description", ""),
        )
        for d in parsed.get("deadlines", [])
    ]

    return CourseOpsResult(
        assessments=assessments,
        deadlines=deadlines,
        course_info=parsed.get("course_info", {}),
        confidence=parsed.get("confidence", 0.0),
    )


VALID_CONCEPT_CATEGORIES = {
    "theory",
    "algorithm",
    "data_structure",
    "pattern",
    "tool",
    "language",
    "protocol",
    "principle",
    "method",
    "general",
}

VALID_RELATION_TYPES = {
    "prerequisite",
    "extends",
    "uses",
    "related_to",
    "part_of",
}


def parse_concept_extraction_response(text: str) -> ConceptExtractionResult:
    """Parse a concept extraction response from the AI.

    Args:
        text: Raw AI response text.

    Returns:
        ConceptExtractionResult with concepts and relations.

    Raises:
        AgentError: If JSON parsing fails.
    """
    parsed = parse_json_response(text)

    concepts = [
        ConceptData(
            name=c.get("name", "").strip(),
            description=c.get("description", "").strip(),
            category=(
                c.get("category", "general")
                if c.get("category", "general") in VALID_CONCEPT_CATEGORIES
                else "general"
            ),
        )
        for c in parsed.get("concepts", [])
        if c.get("name", "").strip()
    ]

    relations = [
        ConceptRelationData(
            source=r.get("source", "").strip(),
            target=r.get("target", "").strip(),
            relation_type=(
                r.get("relation_type", "related_to")
                if r.get("relation_type", "related_to") in VALID_RELATION_TYPES
                else "related_to"
            ),
            confidence=max(0.0, min(1.0, float(r.get("confidence", 0.8)))),
        )
        for r in parsed.get("relations", [])
        if r.get("source", "").strip() and r.get("target", "").strip()
    ]

    return ConceptExtractionResult(concepts=concepts, relations=relations)
