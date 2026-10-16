"""First-run onboarding status (`api.onboarding v1`)."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.models.user import User
from app.services import onboarding_service

router = APIRouter()


class SummaryTargetResponse(BaseModel):
    """The summary the checklist points the user at."""

    course_id: str
    course_code: str
    week: int


class OnboardingSteps(BaseModel):
    """Per-step state: done, active or locked."""

    upload: str
    summary: str
    check_in: str


class OnboardingResponse(BaseModel):
    """Derived first-run status plus the stored checklist preference."""

    phase: str
    steps: OnboardingSteps
    summary_target: SummaryTargetResponse | None
    checklist: str
    visible: bool


class OnboardingPatch(BaseModel):
    """Change the checklist preference."""

    model_config = ConfigDict(extra="forbid")

    checklist: Literal["auto", "dismissed", "pinned"]


def _to_response(status: onboarding_service.OnboardingStatus) -> OnboardingResponse:
    target = status.summary_target
    return OnboardingResponse(
        phase=status.phase,
        steps=OnboardingSteps(
            upload=status.upload, summary=status.summary, check_in=status.check_in
        ),
        summary_target=(
            SummaryTargetResponse(
                course_id=target.course_id, course_code=target.course_code, week=target.week
            )
            if target
            else None
        ),
        checklist=status.checklist,
        visible=status.visible,
    )


@router.get("/onboarding", response_model=OnboardingResponse, summary="First-run status")
async def get_onboarding(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> OnboardingResponse:
    """Return the caller's onboarding status."""
    return _to_response(await onboarding_service.get_status(session, user_id=user.id))


@router.patch("/onboarding", response_model=OnboardingResponse, summary="Set checklist state")
async def patch_onboarding(
    body: OnboardingPatch,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> OnboardingResponse:
    """Dismiss, pin or reset the caller's checklist."""
    return _to_response(
        await onboarding_service.set_checklist(session, user_id=user.id, checklist=body.checklist)
    )
