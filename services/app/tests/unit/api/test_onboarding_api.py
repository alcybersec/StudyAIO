"""Onboarding routes: the caller's id reaches the service (assert the wiring)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services import onboarding_service
from app.services.onboarding_service import SummaryTarget


def _status(checklist: str = "auto", target: SummaryTarget | None = None):
    return onboarding_service.derive_status(
        uploaded=True,
        summary_target=target,
        summary_read=False,
        check_in_done=False,
        checklist=checklist,
    )


@pytest.mark.asyncio
class TestOnboardingApi:
    async def test_get_returns_the_derived_shape(self, async_client, default_test_user):
        target = SummaryTarget(course_id="c1", course_code="CSIT302", week=2)
        with patch.object(
            onboarding_service, "get_status", new=AsyncMock(return_value=_status(target=target))
        ) as mock:
            response = await async_client.get("/api/onboarding")

        assert response.status_code == 200
        assert response.json() == {
            "phase": "has_summary",
            "steps": {"upload": "done", "summary": "active", "check_in": "active"},
            "summary_target": {"course_id": "c1", "course_code": "CSIT302", "week": 2},
            "checklist": "auto",
            "visible": True,
        }
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing

    async def test_patch_passes_caller_and_value(self, async_client, default_test_user):
        with patch.object(
            onboarding_service,
            "set_checklist",
            new=AsyncMock(return_value=_status(checklist="dismissed")),
        ) as mock:
            response = await async_client.patch("/api/onboarding", json={"checklist": "dismissed"})

        assert response.status_code == 200
        assert response.json()["visible"] is False
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing
        assert mock.await_args.kwargs.get("checklist") == "dismissed"

    @pytest.mark.parametrize("body", [{"checklist": "gone"}, {}, {"checklist": "auto", "x": 1}])
    async def test_patch_rejects_values_outside_the_states(self, async_client, body):
        with patch.object(onboarding_service, "set_checklist", new=AsyncMock()) as mock:
            response = await async_client.patch("/api/onboarding", json=body)

        assert response.status_code == 422
        mock.assert_not_awaited()  # the cause is validation, not the service
