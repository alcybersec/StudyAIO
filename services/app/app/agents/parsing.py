"""Shared parsing helpers for agent adapters.

Extracts structured data from raw AI responses. Used by both
ClaudeCodeAdapter and AnthropicAPIAdapter.
"""

import json

import structlog

from app.agents.base import ExtractionData
from app.core.exceptions import AgentError

logger = structlog.get_logger()


def parse_json_response(text: str) -> dict:
    """Extract and parse a JSON object from an AI response.

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


def parse_json_array_response(text: str) -> list[dict]:
    """Extract and parse a JSON array from an AI response.

    Handles responses that may contain markdown code fences.

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

    raise AgentError(f"Failed to parse JSON array from Claude response: {text[:200]}...")


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
