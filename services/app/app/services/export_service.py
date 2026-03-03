"""Export service -- generates Obsidian-compatible vault as a zip archive."""

import io
import zipfile
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.summary import Summary

logger = structlog.get_logger()


def _yaml_frontmatter(metadata: dict) -> str:
    """Generate YAML frontmatter block."""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _generate_index_md(course: Course, weeks: list[int]) -> str:
    """Generate the course index file with links to all weeks."""
    frontmatter = _yaml_frontmatter({
        "type": "index",
        "course": course.code,
        "name": course.name or course.code,
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
    })

    lines = [
        frontmatter,
        "",
        f"# {course.code}",
        "",
    ]
    if course.name:
        lines.append(f"**{course.name}**")
        lines.append("")

    lines.append("## Weeks")
    lines.append("")
    for week in sorted(weeks):
        lines.append(f"- [[Week{week:02d}|Week {week}]]")

    lines.append("")
    lines.append("## Resources")
    lines.append("")
    lines.append("- [[Flashcards/|Flashcards]]")
    lines.append("- [[Quizzes/|Quizzes]]")

    return "\n".join(lines)


def _generate_week_md(
    course_code: str,
    week: int,
    summary: Summary | None,
) -> str:
    """Generate a week summary file with frontmatter and wiki-links."""
    frontmatter = _yaml_frontmatter({
        "type": "summary",
        "course": course_code,
        "week": week,
        "tags": [course_code, f"week-{week}"],
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
    })

    lines = [frontmatter, ""]

    if summary and summary.content_md:
        lines.append(summary.content_md)
    else:
        lines.append(f"# {course_code} -- Week {week}")
        lines.append("")
        lines.append("*No summary available yet.*")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"**Flashcards:** [[Flashcards/Week{week:02d}|View Flashcards]]")
    lines.append(f"**Quizzes:** [[Quizzes/Week{week:02d}|View Quizzes]]")

    # Navigation links
    lines.append("")
    lines.append(f"[[_Index|Back to {course_code}]]")

    return "\n".join(lines)


def _generate_flashcards_md(
    course_code: str,
    week: int,
    flashcards: list[Flashcard],
) -> str:
    """Generate a flashcards file using Obsidian callout blocks."""
    frontmatter = _yaml_frontmatter({
        "type": "flashcards",
        "course": course_code,
        "week": week,
        "count": len(flashcards),
        "tags": [course_code, f"week-{week}", "flashcards"],
    })

    lines = [
        frontmatter,
        "",
        f"# {course_code} Week {week} -- Flashcards",
        "",
    ]

    for i, card in enumerate(flashcards, 1):
        lines.append(f"## Card {i}")
        lines.append("")
        lines.append(f"> [!question] {card.front}")
        lines.append(f"> {card.back}")
        lines.append("")

    if not flashcards:
        lines.append("*No flashcards available for this week.*")

    lines.append("")
    lines.append(f"[[../Week{week:02d}|Back to Week {week}]]")

    return "\n".join(lines)


def _generate_quizzes_md(
    course_code: str,
    week: int,
    quizzes: list[QuizQuestion],
) -> str:
    """Generate a quizzes file with collapsible answers."""
    frontmatter = _yaml_frontmatter({
        "type": "quiz",
        "course": course_code,
        "week": week,
        "count": len(quizzes),
        "tags": [course_code, f"week-{week}", "quiz"],
    })

    lines = [
        frontmatter,
        "",
        f"# {course_code} Week {week} -- Quiz",
        "",
    ]

    for i, q in enumerate(quizzes, 1):
        q_type = "Multiple Choice" if q.question_type == "multiple_choice" else "Short Answer"
        lines.append(f"## Question {i} ({q_type})")
        lines.append("")
        lines.append(q.question)
        lines.append("")

        if q.options_json and isinstance(q.options_json, list):
            for opt in q.options_json:
                lines.append(f"- {opt}")
            lines.append("")

        # Collapsible answer
        lines.append("> [!success]- Answer")
        lines.append(f"> **{q.correct_answer}**")
        if q.explanation:
            lines.append("> ")
            lines.append(f"> {q.explanation}")
        lines.append("")

    if not quizzes:
        lines.append("*No quiz questions available for this week.*")

    lines.append("")
    lines.append(f"[[../Week{week:02d}|Back to Week {week}]]")

    return "\n".join(lines)


async def generate_obsidian_vault(
    session: AsyncSession,
    course_code: str,
    weeks: list[int] | None = None,
) -> tuple[io.BytesIO, str] | None:
    """Generate an Obsidian-compatible vault as a zip archive.

    Args:
        session: Database session.
        course_code: Course code to export.
        weeks: Optional list of weeks to include. None = all weeks.

    Returns:
        Tuple of (zip_bytes_io, filename) or None if course not found.
    """
    # Look up course
    result = await session.execute(
        select(Course).where(Course.code == course_code)
    )
    course = result.scalar_one_or_none()
    if not course:
        return None

    # Fetch summaries
    summary_query = select(Summary).where(Summary.course_id == course.id)
    if weeks:
        summary_query = summary_query.where(Summary.week.in_(weeks))
    summary_result = await session.execute(summary_query)
    summaries = {s.week: s for s in summary_result.scalars().all()}

    # Fetch flashcards
    fc_query = select(Flashcard).where(Flashcard.course_id == course.id)
    if weeks:
        fc_query = fc_query.where(Flashcard.week.in_(weeks))
    fc_result = await session.execute(fc_query)
    flashcards_by_week: dict[int, list[Flashcard]] = {}
    for fc in fc_result.scalars().all():
        flashcards_by_week.setdefault(fc.week, []).append(fc)

    # Fetch quiz questions
    qq_query = select(QuizQuestion).where(QuizQuestion.course_id == course.id)
    if weeks:
        qq_query = qq_query.where(QuizQuestion.week.in_(weeks))
    qq_result = await session.execute(qq_query)
    quizzes_by_week: dict[int, list[QuizQuestion]] = {}
    for qq in qq_result.scalars().all():
        quizzes_by_week.setdefault(qq.week, []).append(qq)

    # Determine all weeks
    all_weeks = sorted(set(
        list(summaries.keys())
        + list(flashcards_by_week.keys())
        + list(quizzes_by_week.keys())
    ))

    if not all_weeks:
        all_weeks = weeks or []

    # Build zip
    vault_name = course_code
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Index
        zf.writestr(f"{vault_name}/_Index.md", _generate_index_md(course, all_weeks))

        # Per-week files
        for week in all_weeks:
            summary = summaries.get(week)
            week_flashcards = flashcards_by_week.get(week, [])
            week_quizzes = quizzes_by_week.get(week, [])

            zf.writestr(
                f"{vault_name}/Week{week:02d}.md",
                _generate_week_md(course_code, week, summary),
            )
            zf.writestr(
                f"{vault_name}/Flashcards/Week{week:02d}.md",
                _generate_flashcards_md(course_code, week, week_flashcards),
            )
            zf.writestr(
                f"{vault_name}/Quizzes/Week{week:02d}.md",
                _generate_quizzes_md(course_code, week, week_quizzes),
            )

    buf.seek(0)
    filename = f"{course_code}_vault.zip"

    logger.info(
        "obsidian_vault_generated",
        course_code=course_code,
        weeks=len(all_weeks),
        filename=filename,
    )

    return buf, filename
