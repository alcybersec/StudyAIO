"""Calendar service — generate .ics files and markdown task plans from deadlines."""

import io
from datetime import date, datetime, timedelta, timezone

import structlog
from icalendar import Calendar, Event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.course import Course
from app.models.deadline import Deadline

logger = structlog.get_logger()


async def generate_ics(
    session: AsyncSession,
    course_code: str,
) -> tuple[io.BytesIO, str] | None:
    """Generate an .ics calendar file with all deadlines for a course.

    Args:
        session: Database session.
        course_code: Course code.

    Returns:
        Tuple of (ics_bytes_io, filename) or None if course not found.
    """
    result = await session.execute(
        select(Course).where(Course.code == course_code)
    )
    course = result.scalar_one_or_none()
    if not course:
        return None

    deadlines_result = await session.execute(
        select(Deadline)
        .where(Deadline.course_id == course.id)
        .order_by(Deadline.due_date)
    )
    deadlines = list(deadlines_result.scalars().all())

    cal = Calendar()
    cal.add("prodid", "-//StudyAIO//CourseOps//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"{course_code} Deadlines")

    for deadline in deadlines:
        event = Event()
        event.add("uid", f"{deadline.id}@studyaio")
        event.add("summary", f"[{course_code}] {deadline.title}")
        # All-day event on the due date
        event.add("dtstart", deadline.due_date)
        event.add("dtend", deadline.due_date + timedelta(days=1))
        event.add("dtstamp", datetime.now(timezone.utc))

        description_parts = [f"Type: {deadline.deadline_type}"]
        if deadline.description:
            description_parts.append(deadline.description)
        if not deadline.is_confirmed:
            description_parts.append("(Unconfirmed — extracted by AI)")
        event.add("description", "\n".join(description_parts))

        # Set category
        event.add("categories", [deadline.deadline_type])

        cal.add_component(event)

    buf = io.BytesIO(cal.to_ical())
    filename = f"{course_code}_deadlines.ics"

    logger.info(
        "ics_generated",
        course_code=course_code,
        deadline_count=len(deadlines),
        filename=filename,
    )
    return buf, filename


async def generate_task_plan_md(
    session: AsyncSession,
    course_code: str,
) -> tuple[io.BytesIO, str] | None:
    """Generate a markdown task plan from deadlines and assessments.

    Args:
        session: Database session.
        course_code: Course code.

    Returns:
        Tuple of (md_bytes_io, filename) or None if course not found.
    """
    result = await session.execute(
        select(Course).where(Course.code == course_code)
    )
    course = result.scalar_one_or_none()
    if not course:
        return None

    # Fetch assessments and deadlines
    assessments_result = await session.execute(
        select(Assessment)
        .where(Assessment.course_id == course.id)
        .order_by(Assessment.assessment_type, Assessment.title)
    )
    assessments = list(assessments_result.scalars().all())

    deadlines_result = await session.execute(
        select(Deadline)
        .where(Deadline.course_id == course.id)
        .order_by(Deadline.due_date)
    )
    deadlines = list(deadlines_result.scalars().all())

    today = date.today()
    lines = [
        f"# {course_code} — Task Plan",
        "",
        f"*Generated {today.isoformat()} by StudyAIO*",
        "",
    ]

    # Course info
    if course.name:
        lines.append(f"**Course:** {course.name}")
    if course.term:
        lines.append(f"**Term:** {course.term}")
    lines.append("")

    # Assessment overview
    if assessments:
        lines.append("## Assessment Overview")
        lines.append("")
        lines.append("| Assessment | Type | Weight |")
        lines.append("|:-----------|:-----|-------:|")
        for a in assessments:
            weight_str = f"{a.weight_pct:.0f}%" if a.weight_pct is not None else "—"
            lines.append(f"| {a.title} | {a.assessment_type} | {weight_str} |")
        total = sum(a.weight_pct for a in assessments if a.weight_pct is not None)
        if total > 0:
            lines.append(f"| **Total** | | **{total:.0f}%** |")
        lines.append("")

    # Upcoming deadlines
    upcoming = [d for d in deadlines if d.due_date >= today]
    past = [d for d in deadlines if d.due_date < today]

    if upcoming:
        lines.append("## Upcoming Deadlines")
        lines.append("")
        for d in upcoming:
            days_remaining = (d.due_date - today).days
            urgency = ""
            if days_remaining <= 3:
                urgency = " **URGENT**"
            elif days_remaining <= 7:
                urgency = " *Soon*"

            confirmed_marker = "" if d.is_confirmed else " _(unconfirmed)_"
            checkbox = "- [ ]"
            lines.append(
                f"{checkbox} **{d.due_date.isoformat()}** — {d.title} "
                f"({d.deadline_type}, {days_remaining}d){urgency}{confirmed_marker}"
            )
            if d.description:
                lines.append(f"  - {d.description}")
        lines.append("")

    if past:
        lines.append("## Past Deadlines")
        lines.append("")
        for d in past:
            lines.append(f"- [x] ~~{d.due_date.isoformat()} — {d.title}~~")
        lines.append("")

    # Study recommendations
    if upcoming:
        lines.append("## Study Plan")
        lines.append("")
        for d in upcoming:
            days_remaining = (d.due_date - today).days
            if days_remaining > 0:
                lines.append(f"### {d.title} ({d.due_date.isoformat()})")
                lines.append(f"- Days remaining: {days_remaining}")
                lines.append(f"- Type: {d.deadline_type}")
                if d.description:
                    lines.append(f"- Notes: {d.description}")
                lines.append("")

    content = "\n".join(lines)
    buf = io.BytesIO(content.encode("utf-8"))
    filename = f"{course_code}_task_plan.md"

    logger.info(
        "task_plan_generated",
        course_code=course_code,
        deadline_count=len(deadlines),
        filename=filename,
    )
    return buf, filename
