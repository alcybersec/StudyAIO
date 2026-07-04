"""Tests for study_service — weekly planner."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import study_service


def _make_exam(exam_id: str, course_id: str) -> MagicMock:
    exam = MagicMock()
    exam.id = exam_id
    exam.course_id = course_id
    return exam


def _schedule(days: int, card_target: int, quiz_target: int, priority: str = "low") -> list[dict]:
    today = date.today()
    return [
        {
            "date": (today + timedelta(days=i)).isoformat(),
            "days_until_exam": 9 - i,
            "priority": priority,
            "card_target": card_target,
            "quiz_target": quiz_target,
            "focus_weeks": [1],
        }
        for i in range(days)
    ]


def _sessions_result(rows: list) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


def _course_codes_result(mapping: dict[str, str]) -> MagicMock:
    result = MagicMock()
    rows = []
    for course_id, code in mapping.items():
        row = MagicMock()
        row.id = course_id
        row.code = code
        rows.append(row)
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
class TestBuildWeekPlan:
    """Tests for build_week_plan."""

    async def test_returns_seven_day_entries(self, mock_session):
        """An exam in 9 days yields 7 day entries with cards+quiz items."""
        exam = _make_exam("exam-001", "course-001")

        with (
            patch(
                "app.services.study_service.exam_service.list_exams",
                new_callable=AsyncMock,
                return_value=[exam],
            ),
            patch(
                "app.services.study_service.schedule_service.generate_study_schedule",
                new_callable=AsyncMock,
                return_value=_schedule(7, card_target=10, quiz_target=5),
            ),
        ):
            mock_session.execute = AsyncMock(
                side_effect=[
                    _course_codes_result({"course-001": "CSIT302"}),
                    _sessions_result([]),
                ]
            )
            plan = await study_service.build_week_plan(mock_session, "user-001")

        assert len(plan) == 7
        today = date.today()
        assert plan[0]["day"] == today.isoformat()
        first_items = plan[0]["items"]
        kinds = {i["kind"] for i in first_items}
        assert {"cards", "quiz"} <= kinds
        cards_item = next(i for i in first_items if i["kind"] == "cards")
        assert cards_item["course_code"] == "CSIT302"
        assert cards_item["target"] == 10
        assert cards_item["done"] == 0

    async def test_nearer_exam_gets_higher_weekly_card_total(self, mock_session):
        """A course with a nearer exam gets a larger weekly card total."""
        near_exam = _make_exam("exam-near", "course-near")
        far_exam = _make_exam("exam-far", "course-far")

        async def fake_schedule(session, exam_id, days_ahead=7):
            if exam_id == "exam-near":
                return _schedule(7, card_target=20, quiz_target=8, priority="critical")
            return _schedule(7, card_target=6, quiz_target=5, priority="low")

        with (
            patch(
                "app.services.study_service.exam_service.list_exams",
                new_callable=AsyncMock,
                return_value=[near_exam, far_exam],
            ),
            patch(
                "app.services.study_service.schedule_service.generate_study_schedule",
                side_effect=fake_schedule,
            ),
        ):
            mock_session.execute = AsyncMock(
                side_effect=[
                    _course_codes_result({"course-near": "NEAR101", "course-far": "FAR101"}),
                    _sessions_result([]),
                ]
            )
            plan = await study_service.build_week_plan(mock_session, "user-001")

        def weekly_cards(code: str) -> int:
            return sum(
                i["target"]
                for day in plan
                for i in day["items"]
                if i["kind"] == "cards" and i["course_code"] == code
            )

        assert weekly_cards("NEAR101") > weekly_cards("FAR101")

    async def test_no_exams_returns_empty_items_per_day(self, mock_session):
        """No active exams → 7 day entries with empty items."""
        with patch(
            "app.services.study_service.exam_service.list_exams",
            new_callable=AsyncMock,
            return_value=[],
        ):
            plan = await study_service.build_week_plan(mock_session, "user-001")

        assert len(plan) == 7
        assert all(day["items"] == [] for day in plan)

    async def test_done_computed_from_study_sessions(self, mock_session):
        """cards/quiz done counts come from this week's study sessions."""
        exam = _make_exam("exam-001", "course-001")
        today = date.today()

        session_row = MagicMock()
        session_row.course_id = "course-001"
        session_row.session_date = today
        session_row.cards_reviewed = 4
        session_row.quiz_questions_answered = 2

        with (
            patch(
                "app.services.study_service.exam_service.list_exams",
                new_callable=AsyncMock,
                return_value=[exam],
            ),
            patch(
                "app.services.study_service.schedule_service.generate_study_schedule",
                new_callable=AsyncMock,
                return_value=_schedule(7, card_target=10, quiz_target=5),
            ),
        ):
            mock_session.execute = AsyncMock(
                side_effect=[
                    _course_codes_result({"course-001": "CSIT302"}),
                    _sessions_result([session_row]),
                ]
            )
            plan = await study_service.build_week_plan(mock_session, "user-001")

        cards_today = next(i for i in plan[0]["items"] if i["kind"] == "cards")
        quiz_today = next(i for i in plan[0]["items"] if i["kind"] == "quiz")
        assert cards_today["done"] == 4
        assert quiz_today["done"] == 2
        # Other days untouched
        cards_tomorrow = next(i for i in plan[1]["items"] if i["kind"] == "cards")
        assert cards_tomorrow["done"] == 0

    async def test_critical_day_includes_mock_item(self, mock_session):
        """Critical-priority days include a mock exam item."""
        exam = _make_exam("exam-001", "course-001")

        with (
            patch(
                "app.services.study_service.exam_service.list_exams",
                new_callable=AsyncMock,
                return_value=[exam],
            ),
            patch(
                "app.services.study_service.schedule_service.generate_study_schedule",
                new_callable=AsyncMock,
                return_value=_schedule(7, card_target=20, quiz_target=8, priority="critical"),
            ),
        ):
            mock_session.execute = AsyncMock(
                side_effect=[
                    _course_codes_result({"course-001": "CSIT302"}),
                    _sessions_result([]),
                ]
            )
            plan = await study_service.build_week_plan(mock_session, "user-001")

        kinds = {i["kind"] for i in plan[0]["items"]}
        assert "mock" in kinds
