"""API routes for exam management."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.exam_schemas import (
    DailyPlanResponse,
    ExamCreateRequest,
    ExamProgressResponse,
    ExamResponse,
    ExamUpdateRequest,
    ReadinessDetailResponse,
    ReadinessTopicRow,
    StudyHistoryDayResponse,
    StudySessionRequest,
    StudySessionResponse,
    WeakTopicResponse,
)
from app.core.database import get_session
from app.models.user import User
from app.services import (
    challenge_service,
    exam_service,
    readiness_service,
    schedule_service,
    streak_service,
    xp_service,
)

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/exams",
    response_model=ExamResponse,
    status_code=201,
    summary="Create an exam",
    description="Create a new exam with date, scope, and mastery target.",
)
async def create_exam(
    body: ExamCreateRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ExamResponse:
    """Create a new exam."""
    try:
        exam = await exam_service.create_exam(
            session,
            course_code=body.course_code,
            title=body.title,
            exam_date=body.exam_date,
            weeks_scope=body.weeks_scope,
            target_mastery_pct=body.target_mastery_pct,
            user_id=user.id,
        )
        await session.commit()
        return ExamResponse.model_validate(exam)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/exams",
    response_model=list[ExamResponse],
    summary="List exams",
    description="List exams with optional course and status filters.",
)
async def list_exams(
    course_code: str | None = Query(None, description="Course code filter"),
    status: str | None = Query(None, description="Status filter (active/completed/archived)"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[ExamResponse]:
    """List exams."""
    exams = await exam_service.list_exams(session, course_code, status, user_id=user.id)
    await session.commit()  # persist auto-completions
    return [ExamResponse.model_validate(e) for e in exams]


@router.get(
    "/exams/{exam_id}",
    response_model=ExamProgressResponse,
    summary="Get exam detail with progress",
    description="Returns exam info plus progress metrics, quiz accuracy, and weak topics.",
)
async def get_exam(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ExamProgressResponse:
    """Get exam detail with progress."""
    progress = await exam_service.get_exam_progress(session, exam_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Exam not found")
    await session.commit()  # persist auto-completions
    return ExamProgressResponse(**progress)


@router.put(
    "/exams/{exam_id}",
    response_model=ExamResponse,
    summary="Update an exam",
    description="Update exam fields (title, date, scope, target).",
)
async def update_exam(
    exam_id: str,
    body: ExamUpdateRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ExamResponse:
    """Update an exam."""
    update_data = body.model_dump(exclude_unset=True)
    exam = await exam_service.update_exam(session, exam_id, **update_data)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await session.commit()
    return ExamResponse.model_validate(exam)


@router.delete(
    "/exams/{exam_id}",
    status_code=204,
    summary="Archive an exam",
    description="Soft-delete (archive) an exam.",
)
async def delete_exam(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Archive an exam."""
    archived = await exam_service.delete_exam(session, exam_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Exam not found")
    await session.commit()


@router.get(
    "/exams/{exam_id}/schedule",
    response_model=list[DailyPlanResponse],
    summary="Get study schedule",
    description="Get adaptive study schedule for the next 7 days.",
)
async def get_schedule(
    exam_id: str,
    days: int = Query(7, ge=1, le=30, description="Days to plan ahead"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[DailyPlanResponse]:
    """Get study schedule."""
    schedule = await schedule_service.generate_study_schedule(session, exam_id, days)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return [DailyPlanResponse(**day) for day in schedule]


@router.get(
    "/exams/{exam_id}/today",
    response_model=DailyPlanResponse,
    summary="Get today's study plan",
    description="Get today's adaptive study plan for an exam.",
)
async def get_today(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> DailyPlanResponse:
    """Get today's study plan."""
    plan = await schedule_service.get_daily_study_plan(session, exam_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return DailyPlanResponse(**plan)


@router.get(
    "/exams/{exam_id}/weak-topics",
    response_model=list[WeakTopicResponse],
    summary="Get weak topic analysis",
    description="Identify weak topics by quiz accuracy and flashcard ease.",
)
async def get_weak_topics(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[WeakTopicResponse]:
    """Get weak topics for an exam."""
    exam = await exam_service.get_exam(session, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    topics = await exam_service.get_weak_topics(session, exam.course_id, exam.weeks_scope)
    return [WeakTopicResponse(**t) for t in topics]


@router.post(
    "/exams/{exam_id}/sessions",
    response_model=StudySessionResponse,
    status_code=201,
    summary="Record a study session",
    description="Record a completed study session for an exam.",
)
async def record_session(
    exam_id: str,
    body: StudySessionRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StudySessionResponse:
    """Record a study session."""
    exam = await exam_service.get_exam(session, exam_id, user_id=user.id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    study = await streak_service.record_study_session(
        session,
        course_id=exam.course_id,
        exam_id=exam_id,
        cards_reviewed=body.cards_reviewed,
        quiz_questions_answered=body.quiz_questions_answered,
        quiz_correct=body.quiz_correct,
        duration_seconds=body.duration_seconds,
        user_id=user.id,
    )
    await session.commit()

    # Award XP for study session (best-effort)
    try:
        await xp_service.award_xp(session, user.id, "streak_day")
        await challenge_service.update_challenge_progress(
            session, user.id, "study_minutes", body.duration_seconds // 60
        )
    except Exception:
        logger.warning("gamification_xp_failed", exc_info=True)

    return StudySessionResponse(
        id=study.id,
        exam_id=study.exam_id,
        course_id=study.course_id,
        session_date=study.session_date.isoformat(),
        cards_reviewed=study.cards_reviewed,
        quiz_questions_answered=study.quiz_questions_answered,
        quiz_correct=study.quiz_correct,
        duration_seconds=study.duration_seconds,
    )


@router.get(
    "/exams/{exam_id}/history",
    response_model=list[StudyHistoryDayResponse],
    summary="Get study history",
    description="Get daily study session aggregates for the last 30 days.",
)
async def get_history(
    exam_id: str,
    days: int = Query(30, ge=1, le=365, description="Days of history"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[StudyHistoryDayResponse]:
    """Get study history for an exam."""
    history = await streak_service.get_study_history(
        session, exam_id=exam_id, days=days, user_id=user.id
    )
    return [StudyHistoryDayResponse(**h) for h in history]


@router.get(
    "/exams/{exam_id}/readiness",
    response_model=ReadinessDetailResponse,
    summary="Get readiness drill-down",
    description="Returns overall readiness plus topic-level breakdown "
    "(accuracy, weakness weight, card count per week).",
)
async def get_readiness_detail(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ReadinessDetailResponse:
    """Get topic-level readiness detail for an exam."""
    detail = await readiness_service.compute_readiness_detail(session, exam_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="Exam not found")
    return ReadinessDetailResponse(
        exam_id=detail["exam_id"],
        title=detail["title"],
        overall=detail["overall"],
        topics=[ReadinessTopicRow(**t) for t in detail["topics"]],
    )
