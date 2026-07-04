"""Tests for GET /api/study/plan."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest


def _plan_days(items_per_day: list[dict] | None = None) -> list[dict]:
    today = date.today()
    return [
        {
            "day": (today + timedelta(days=i)).isoformat(),
            "items": list(items_per_day or []),
        }
        for i in range(7)
    ]


@pytest.mark.asyncio
class TestStudyPlan:
    """Tests for the weekly study plan endpoint."""

    async def test_plan_returns_seven_days(self, async_client):
        """Response has 7 day entries with item structure."""
        items = [
            {"course_code": "CSIT302", "kind": "cards", "target": 10, "done": 3},
            {"course_code": "CSIT302", "kind": "quiz", "target": 5, "done": 0},
        ]
        with patch(
            "app.api.study.study_service.build_week_plan",
            new_callable=AsyncMock,
            return_value=_plan_days(items),
        ) as mock_plan:
            response = await async_client.get("/api/study/plan")

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 7
        first = data["days"][0]
        assert first["items"][0]["course_code"] == "CSIT302"
        assert first["items"][0]["kind"] == "cards"
        assert first["items"][0]["target"] == 10
        assert first["items"][0]["done"] == 3
        args = mock_plan.call_args.args
        assert args[1] == "00000000-0000-0000-0000-000000000001"

    async def test_plan_no_exams_returns_empty_items(self, async_client):
        """No exams → 200 with empty items per day."""
        with patch(
            "app.api.study.study_service.build_week_plan",
            new_callable=AsyncMock,
            return_value=_plan_days([]),
        ):
            response = await async_client.get("/api/study/plan")

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 7
        assert all(d["items"] == [] for d in data["days"])
