"""Weekly study planner — aggregates per-exam schedules into a 7-day plan."""

from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.study_session import StudySession
from app.services import exam_service, schedule_service

logger = structlog.get_logger()

PLAN_DAYS = 7


async def build_week_plan(session: AsyncSession, user_id: str) -> list[dict]:
    """Build a 7-day study plan across all active exams for a user.

    Wraps the existing adaptive schedule algorithm (priority multipliers by
    exam proximity) and computes `done` counts from this week's study
    sessions.

    Args:
        session: Database session.
        user_id: The user's UUID.

    Returns:
        List of 7 day dicts: {"day": ISO date, "items": [{course_code,
        kind ("cards" | "quiz" | "mock"), target, done}]}.
    """
    today = date.today()
    days = [today + timedelta(days=i) for i in range(PLAN_DAYS)]
    plan: list[dict] = [{"day": d.isoformat(), "items": []} for d in days]

    exams = await exam_service.list_exams(session, status="active", user_id=user_id)
    if not exams:
        return plan

    # Resolve course codes for all exam courses in one query
    course_ids = list({e.course_id for e in exams})
    course_rows = await session.execute(
        select(Course.id, Course.code).where(Course.id.in_(course_ids))
    )
    code_by_course = {row.id: row.code for row in course_rows.all()}

    # Done counts from this week's study sessions: (course_id, date) → sums
    sessions_result = await session.execute(
        select(
            StudySession.course_id,
            StudySession.session_date,
            StudySession.cards_reviewed,
            StudySession.quiz_questions_answered,
        ).where(
            StudySession.user_id == user_id,
            StudySession.session_date >= days[0],
            StudySession.session_date <= days[-1],
        )
    )
    done: dict[tuple[str, date], dict[str, int]] = {}
    for row in sessions_result.all():
        key = (row.course_id, row.session_date)
        entry = done.setdefault(key, {"cards": 0, "quiz": 0})
        entry["cards"] += row.cards_reviewed or 0
        entry["quiz"] += row.quiz_questions_answered or 0

    for exam in exams:
        course_code = code_by_course.get(exam.course_id, "")
        schedule = await schedule_service.generate_study_schedule(
            session, exam.id, days_ahead=PLAN_DAYS
        )
        if not schedule:
            continue

        for day_index, entry in enumerate(schedule[:PLAN_DAYS]):
            day = days[day_index]
            done_entry = done.get((exam.course_id, day), {"cards": 0, "quiz": 0})

            items = plan[day_index]["items"]
            items.append(
                {
                    "course_code": course_code,
                    "kind": "cards",
                    "target": entry["card_target"],
                    "done": done_entry["cards"],
                }
            )
            items.append(
                {
                    "course_code": course_code,
                    "kind": "quiz",
                    "target": entry["quiz_target"],
                    "done": done_entry["quiz"],
                }
            )
            if entry.get("priority") == "critical":
                items.append(
                    {
                        "course_code": course_code,
                        "kind": "mock",
                        "target": 1,
                        "done": 0,
                    }
                )

    logger.info("week_plan_built", user_id=user_id, exam_count=len(exams))
    return plan
