"""Tests for GET /api/exams/{exam_id}/readiness."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestExamReadinessDetail:
    """Tests for the readiness drill-down endpoint."""

    async def test_readiness_detail_returns_topics(self, async_client):
        """Response has overall score and per-topic rows."""
        detail = {
            "exam_id": "exam-001",
            "title": "Midterm",
            "overall": 62,
            "topics": [
                {
                    "topic": "Network Security",
                    "week": 1,
                    "accuracy": 40.0,
                    "weight": 30.0,
                    "card_count": 12,
                },
                {
                    "topic": "Week 2",
                    "week": 2,
                    "accuracy": None,
                    "weight": 100.0,
                    "card_count": 0,
                },
            ],
        }
        with patch(
            "app.api.exams.readiness_service.compute_readiness_detail",
            new_callable=AsyncMock,
            return_value=detail,
        ) as mock_detail:
            response = await async_client.get("/api/exams/exam-001/readiness")

        assert response.status_code == 200
        data = response.json()
        assert data["overall"] == 62
        assert len(data["topics"]) == 2
        assert data["topics"][0]["topic"] == "Network Security"
        assert data["topics"][0]["weight"] == 30.0
        args = mock_detail.call_args.args
        assert args[1] == "exam-001"
        assert args[2] == "00000000-0000-0000-0000-000000000001"

    async def test_readiness_detail_foreign_exam_404(self, async_client):
        """Another user's exam (service returns None) → 404."""
        with patch(
            "app.api.exams.readiness_service.compute_readiness_detail",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/exams/exam-foreign/readiness")

        assert response.status_code == 404
