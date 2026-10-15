"""Rendering of the targeted (weak-spot) generation prompts (ADR 0007 Decision 5).

Every backend's ``generate_quiz`` / ``generate_flashcards`` calls
:func:`render_targeted_prompt` when it is given a ``focus``, so the four AI
backends share one wording and a prompt change applies to all of them. The
untargeted templates (``generate_quiz.txt``, ``generate_flashcards.txt``) are not
involved, which keeps their output and eval baseline unchanged.
"""

from pathlib import Path

from jinja2 import Template

from app.agents.base import GenerationFocus
from app.core.exceptions import AgentError

#: kind -> template file name under ``prompts/``.
TEMPLATES: dict[str, str] = {
    "quiz": "generate_targeted_quiz.txt",
    "flashcards": "generate_targeted_flashcards.txt",
}

#: Where the templates live: the image mounts them at ``/app/prompts``; from a
#: source checkout they sit next to ``app/``.
_PROMPT_DIRS = (Path("/app/prompts"), Path(__file__).resolve().parents[2] / "prompts")


def _template_text(kind: str) -> str:
    name = TEMPLATES.get(kind)
    if name is None:
        raise AgentError(f"unknown targeted generation kind: {kind!r}")
    for directory in _PROMPT_DIRS:
        path = directory / name
        if path.is_file():
            return path.read_text()
    # No fallback: an ad-hoc prompt would drop the citation and no-outside-material
    # rules this feature depends on.
    raise AgentError(f"targeted prompt template missing: {name}")


def render_targeted_prompt(
    kind: str,
    *,
    course_code: str,
    week: int,
    summary: str,
    extraction_text: str,
    count: int,
    focus: GenerationFocus,
) -> str:
    """Render the targeted prompt for one kind.

    Args:
        kind: ``quiz`` or ``flashcards``.
        course_code: Course code, for context.
        week: Week number.
        summary: The unit's summary markdown (may be empty).
        extraction_text: The target extraction with its ``--- Page N [p.N] ---`` markers.
        count: Exact number of items to produce.
        focus: Weak topics, missed stems, items to avoid and pages.

    Returns:
        The prompt text (the caller appends the language directive).

    Raises:
        AgentError: Unknown kind or missing template.
    """
    return Template(_template_text(kind)).render(
        course_code=course_code,
        week=week,
        summary=summary,
        extraction_text=extraction_text,
        count=count,
        topics=focus.topics,
        missed_questions=focus.missed_questions,
        avoid=focus.avoid,
        page_refs=focus.page_refs,
    )
