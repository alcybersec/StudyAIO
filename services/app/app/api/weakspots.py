"""Weak-spot engine API (ADR 0007 Decision 7): heatmap, diagnostic, targeted practice, plan.

Thin routes: validate, call ``weakspot_service`` with the caller's identity, shape the
response. Targeted generation is the only route that spends AI; it records a job row and
enqueues the worker task by name after the commit. It never obtains an adapter.
"""

from datetime import date, datetime
from typing import Literal

import structlog
from celery import current_app
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default, get_user_tz, require_ai_consent
from app.core.clock import user_today, utc_now
from app.core.database import get_session
from app.core.exceptions import TargetedUnitNotFoundError
from app.models.user import User
from app.services import course_service, usage_service, weakspot_service

logger = structlog.get_logger()

router = APIRouter()

#: The worker task (``app/pipeline/targeted_task.py``), enqueued by name: pipeline.targeted_generation v1.
TARGETED_TASK_NAME = "app.pipeline.targeted_task.generate_targeted_items"


class EvidenceResponse(BaseModel):
    """The evidence counts behind one week's score."""

    quiz_attempts: int
    quiz_accuracy: float | None
    cards_reviewed: int
    avg_ease: float | None
    lapsed_cards: int
    overdue_cards: int


class NextExamResponse(BaseModel):
    """The soonest upcoming exam covering a week."""

    exam_id: str
    days_to_exam: int


class WeekResponse(BaseModel):
    """One (course, week) unit of the heatmap."""

    week: int
    status: str
    weakness: float | None
    confidence: float
    urgency: float
    priority: float
    evidence: EvidenceResponse
    next_exam: NextExamResponse | None


class CourseWeeksResponse(BaseModel):
    """A course's weeks in ranked order."""

    course_id: str
    course_code: str
    weeks: list[WeekResponse]


class WeakSpotsResponse(BaseModel):
    """The heatmap: per course, per week."""

    local_date: str
    courses: list[CourseWeeksResponse]


class DiagnosticItem(BaseModel):
    """A diagnostic question with the labels the runner shows."""

    id: str
    course_code: str
    week: int


class DiagnosticResponse(BaseModel):
    """Existing questions to diagnose an unknown week."""

    course_id: str
    week: int
    question_ids: list[str]
    items: list[DiagnosticItem]
    needs_generation: bool


class TargetedRequest(BaseModel):
    """Body of a targeted-generation request."""

    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=36)
    week: int = Field(ge=1, le=1000)
    kind: Literal["quiz", "flashcards"]


class TargetedGenerationResponse(BaseModel):
    """A targeted-generation job. Only a machine ``error_code`` is ever stored, not returned."""

    id: str
    course_id: str
    week: int
    kind: str
    status: str
    requested_count: int
    created_count: int
    dropped_duplicate_count: int
    dropped_uncited_count: int
    item_ids: list[str]
    error_code: str | None
    created_at: datetime | None
    completed_at: datetime | None


class PlanItemResponse(BaseModel):
    """One step of tonight's plan; run through the existing study flows by id."""

    item_type: Literal["card", "quiz"]
    item_id: str
    course_id: str
    course_code: str
    week: int
    reason: Literal["diagnostic", "missed", "review", "new", "targeted"]
    minutes: int
    done: bool


class PlanFocusResponse(BaseModel):
    """A focus week and its score when the plan was built."""

    course_id: str
    course_code: str
    week: int
    status: str
    weakness: float | None
    priority: float
    days_to_exam: int | None


class PlanDiagnosticResponse(BaseModel):
    """The week the plan diagnoses, if any."""

    course_id: str
    course_code: str
    week: int


class StudyPlanResponse(BaseModel):
    """Today's frozen plan with live ``done`` flags."""

    plan_date: date
    minutes: int
    version: int
    algorithm_version: int
    built_at: datetime
    total_minutes: int
    done_count: int
    items: list[PlanItemResponse]
    focus: list[PlanFocusResponse]
    diagnostic: PlanDiagnosticResponse | None


class RefreshRequest(BaseModel):
    """Optional new budget for a rebuild."""

    model_config = ConfigDict(extra="forbid")

    minutes: int | None = Field(default=None, ge=10, le=90)


# ── heatmap ────────────────────────────────────────────────────────────


@router.get(
    "/weak-spots",
    response_model=WeakSpotsResponse,
    summary="Weakness heatmap",
    description="Per course and week: status, weakness, confidence, priority and evidence.",
)
async def get_weak_spots(
    course_id: str | None = Query(None, max_length=36),
    user: User = Depends(get_current_user_or_default),
    tz: str = Depends(get_user_tz),
    session: AsyncSession = Depends(get_session),
) -> WeakSpotsResponse:
    """Derive the caller's weak spots on read."""
    details = await weakspot_service.get_weak_spot_details(
        session, user_id=user.id, tz=tz, course_id=course_id
    )
    courses: dict[str, CourseWeeksResponse] = {}
    for detail in details:
        spot, summary = detail.spot, detail.summary
        course = courses.setdefault(
            spot.course_id,
            CourseWeeksResponse(course_id=spot.course_id, course_code=spot.course_code, weeks=[]),
        )
        course.weeks.append(
            WeekResponse(
                week=spot.week,
                status=spot.score.status,
                weakness=spot.score.weakness,
                confidence=spot.score.confidence,
                urgency=spot.score.urgency,
                priority=spot.score.priority,
                evidence=EvidenceResponse(**vars(summary)),
                next_exam=(
                    NextExamResponse(exam_id=spot.exam_id, days_to_exam=spot.days_to_exam)
                    if spot.exam_id is not None and spot.days_to_exam is not None
                    else None
                ),
            )
        )
    return WeakSpotsResponse(local_date=user_today(tz).isoformat(), courses=list(courses.values()))


@router.get(
    "/weak-spots/diagnostic",
    response_model=DiagnosticResponse,
    summary="Diagnostic questions for a week",
    description="Existing active questions to answer; needs_generation when fewer than three.",
)
async def get_diagnostic(
    course_id: str = Query(..., max_length=36),
    week: int = Query(..., ge=1, le=1000),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> DiagnosticResponse:
    """Pick the diagnostic questions for one of the caller's weeks."""
    course = await course_service.get_course_by_id(session, course_id, user_id=user.id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    questions = await weakspot_service.get_diagnostic_questions(
        session, user_id=user.id, course_id=course_id, week=week
    )
    return DiagnosticResponse(
        course_id=course_id,
        week=week,
        question_ids=[q.id for q in questions],
        items=[DiagnosticItem(id=q.id, course_code=course.code, week=week) for q in questions],
        needs_generation=len(questions) < weakspot_service.DIAGNOSTIC_QUESTIONS,
    )


# ── targeted generation ────────────────────────────────────────────────


def _enqueue_targeted(generation_id: str) -> None:
    """Enqueue the worker task by name (ADR 0002: api reaches pipeline only to enqueue)."""
    current_app.signature(TARGETED_TASK_NAME, args=[generation_id]).delay()


def _generation_response(row, item_ids: list[str]) -> TargetedGenerationResponse:
    return TargetedGenerationResponse(
        id=row.id,
        course_id=row.course_id,
        week=row.week,
        kind=row.kind,
        status=row.status,
        requested_count=row.requested_count,
        created_count=row.created_count,
        dropped_duplicate_count=row.dropped_duplicate_count,
        dropped_uncited_count=row.dropped_uncited_count,
        item_ids=item_ids,
        error_code=row.error_code,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


@router.post(
    "/weak-spots/targeted",
    status_code=202,
    response_model=TargetedGenerationResponse,
    dependencies=[Depends(require_ai_consent)],
    summary="Request targeted practice for a weak week",
    description=(
        "Queues a worker job that writes new items aimed at the caller's own mistakes. "
        "202 for a new job; 200 with the existing one while a job for the same unit is in flight. "
        "429 targeted_daily_cap at six requests per UTC day."
    ),
)
async def request_targeted(
    body: TargetedRequest,
    response: Response,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TargetedGenerationResponse:
    """Record the request, commit, then enqueue; the worker generates."""
    try:
        row, created = await weakspot_service.request_targeted_generation(
            session,
            user_id=user.id,
            user_tier=user.tier,
            course_id=body.course_id,
            week=body.week,
            kind=body.kind,
        )
    except TargetedUnitNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not created:
        response.status_code = 200
        return _generation_response(row, [])

    await usage_service.record(
        session,
        user.id,
        "targeted_generation_requested",
        course_id=row.course_id,
        properties={"count": row.requested_count, "week": row.week},
    )
    await session.commit()
    try:
        _enqueue_targeted(row.id)
    except Exception as exc:
        # Free the in-flight slot, or the unit could never be requested again.
        logger.error("targeted_generation_enqueue_failed", generation_id=row.id, exc_info=True)
        row.status = "failed"
        row.error_code = "enqueue_failed"
        row.completed_at = utc_now()
        await session.commit()
        raise HTTPException(status_code=503, detail="Could not queue the request") from exc
    return _generation_response(row, [])


@router.get(
    "/weak-spots/targeted/{generation_id}",
    response_model=TargetedGenerationResponse,
    summary="Status of a targeted generation",
    description="Status and counts of one of the caller's requests, with the created item ids.",
)
async def get_targeted(
    generation_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TargetedGenerationResponse:
    """Poll one generation."""
    row = await weakspot_service.get_targeted_generation(session, generation_id, user_id=user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    item_ids: list[str] = []
    if row.status == "completed":
        item_ids = await weakspot_service.get_generated_item_ids(session, row, user_id=user.id)
    return _generation_response(row, item_ids)


# ── study tonight ──────────────────────────────────────────────────────


async def _plan_response(session: AsyncSession, plan, user: User) -> StudyPlanResponse:
    items = await weakspot_service.resolve_plan_items(session, plan, user_id=user.id)
    focus = [f for f in plan.focus if f.get("role") == "focus"]
    diagnostic = next((f for f in plan.focus if f.get("role") == "diagnostic"), None)
    return StudyPlanResponse(
        plan_date=plan.plan_date,
        minutes=plan.minutes,
        version=plan.version,
        algorithm_version=plan.algorithm_version,
        built_at=plan.built_at,
        total_minutes=sum(i["minutes"] for i in items),
        done_count=sum(1 for i in items if i["done"]),
        items=[PlanItemResponse(**i) for i in items],
        focus=[PlanFocusResponse(**{k: v for k, v in f.items() if k != "role"}) for f in focus],
        diagnostic=(
            PlanDiagnosticResponse(
                course_id=diagnostic["course_id"],
                course_code=diagnostic["course_code"],
                week=diagnostic["week"],
            )
            if diagnostic
            else None
        ),
    )


@router.get(
    "/study-plan/tonight",
    response_model=StudyPlanResponse,
    summary="Today's study plan",
    description="Built on the first read of the local day, then frozen; done flags are live.",
)
async def get_tonight(
    minutes: int = Query(weakspot_service.DEFAULT_PLAN_MINUTES, ge=10, le=90),
    user: User = Depends(get_current_user_or_default),
    tz: str = Depends(get_user_tz),
    session: AsyncSession = Depends(get_session),
) -> StudyPlanResponse:
    """Return (building if needed) today's plan."""
    plan, built = await weakspot_service.get_or_build_tonight_plan(
        session, user_id=user.id, tz=tz, minutes=minutes
    )
    if built:
        await usage_service.record(
            session,
            user.id,
            "study_plan_built",
            properties={"count": len(plan.items), "duration_seconds": plan.minutes * 60},
        )
    result = await _plan_response(session, plan, user)
    await session.commit()
    return result


@router.post(
    "/study-plan/tonight/refresh",
    response_model=StudyPlanResponse,
    summary="Rebuild today's study plan",
    description="Rebuilds from the current evidence and increments the plan version.",
)
async def refresh_tonight(
    body: RefreshRequest | None = Body(None),
    user: User = Depends(get_current_user_or_default),
    tz: str = Depends(get_user_tz),
    session: AsyncSession = Depends(get_session),
) -> StudyPlanResponse:
    """Rebuild today's plan on demand."""
    plan = await weakspot_service.refresh_tonight_plan(
        session, user_id=user.id, tz=tz, minutes=body.minutes if body else None
    )
    await usage_service.record(
        session,
        user.id,
        "study_plan_built",
        properties={"count": len(plan.items), "duration_seconds": plan.minutes * 60},
    )
    result = await _plan_response(session, plan, user)
    await session.commit()
    return result
