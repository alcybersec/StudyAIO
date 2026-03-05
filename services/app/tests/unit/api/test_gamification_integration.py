"""Tests for gamification integration hooks in existing API routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestReviewAwardsXP:
    """Tests for XP awarding on flashcard review."""

    @pytest.mark.asyncio
    @patch("app.api.study.challenge_service")
    @patch("app.api.study.xp_service")
    @patch("app.api.study.srs_service")
    async def test_review_awards_xp(
        self, mock_srs, mock_xp, mock_challenge, async_client, mock_session
    ):
        """POST /study/review awards XP after successful review."""
        # Mock flashcard exists
        mock_flashcard = MagicMock()
        mock_flashcard.id = "fc-001"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_flashcard
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_review = MagicMock()
        mock_review.id = "rev-001"
        mock_review.flashcard_id = "fc-001"
        mock_review.quality = 4
        mock_review.ease_factor = 2.5
        mock_review.interval = 6
        mock_review.repetitions = 2
        mock_review.next_review_date = "2026-03-11"
        mock_review.created_at = MagicMock()
        mock_review.created_at.isoformat = MagicMock(return_value="2026-03-05T10:00:00")
        mock_srs.record_review = AsyncMock(return_value=mock_review)

        mock_xp.award_xp = AsyncMock(return_value=(MagicMock(), MagicMock(), []))
        mock_challenge.update_challenge_progress = AsyncMock(return_value=None)

        resp = await async_client.post(
            "/api/study/review",
            json={"flashcard_id": "fc-001", "quality": 4},
        )
        assert resp.status_code == 200
        mock_xp.award_xp.assert_called_once()
        mock_challenge.update_challenge_progress.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.study.challenge_service")
    @patch("app.api.study.xp_service")
    @patch("app.api.study.srs_service")
    async def test_xp_failure_does_not_break_review(
        self, mock_srs, mock_xp, mock_challenge, async_client, mock_session
    ):
        """XP failure doesn't prevent review from succeeding."""
        mock_flashcard = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_flashcard
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_review = MagicMock()
        mock_review.id = "rev-001"
        mock_review.flashcard_id = "fc-001"
        mock_review.quality = 4
        mock_review.ease_factor = 2.5
        mock_review.interval = 6
        mock_review.repetitions = 2
        mock_review.next_review_date = "2026-03-11"
        mock_review.created_at = MagicMock()
        mock_review.created_at.isoformat = MagicMock(return_value="2026-03-05T10:00:00")
        mock_srs.record_review = AsyncMock(return_value=mock_review)

        # XP service throws
        mock_xp.award_xp = AsyncMock(side_effect=Exception("XP DB error"))

        resp = await async_client.post(
            "/api/study/review",
            json={"flashcard_id": "fc-001", "quality": 4},
        )
        # Review should still succeed
        assert resp.status_code == 200


class TestQuizAwardsXP:
    """Tests for XP awarding on quiz attempts."""

    @pytest.mark.asyncio
    @patch("app.api.study.challenge_service")
    @patch("app.api.study.xp_service")
    @patch("app.api.study.exam_service")
    async def test_correct_quiz_awards_xp(
        self, mock_exam, mock_xp, mock_challenge, async_client, mock_session
    ):
        """POST /study/quiz-attempt awards XP for correct answers."""
        mock_quiz = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_quiz
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_attempt = MagicMock()
        mock_attempt.id = "qa-001"
        mock_attempt.quiz_question_id = "qq-001"
        mock_attempt.selected_answer = "A"
        mock_attempt.is_correct = True
        mock_attempt.exam_id = None
        mock_attempt.time_spent_ms = 5000
        mock_attempt.created_at = MagicMock()
        mock_attempt.created_at.isoformat = MagicMock(return_value="2026-03-05T10:00:00")
        mock_exam.record_quiz_attempt = AsyncMock(return_value=mock_attempt)

        mock_xp.award_xp = AsyncMock(return_value=(MagicMock(), MagicMock(), []))
        mock_challenge.update_challenge_progress = AsyncMock(return_value=None)

        resp = await async_client.post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": "qq-001",
                "selected_answer": "A",
                "is_correct": True,
            },
        )
        assert resp.status_code == 201
        mock_xp.award_xp.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.study.challenge_service")
    @patch("app.api.study.xp_service")
    @patch("app.api.study.exam_service")
    async def test_incorrect_quiz_no_xp(
        self, mock_exam, mock_xp, mock_challenge, async_client, mock_session
    ):
        """POST /study/quiz-attempt does NOT award XP for incorrect answers."""
        mock_quiz = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_quiz
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_attempt = MagicMock()
        mock_attempt.id = "qa-001"
        mock_attempt.quiz_question_id = "qq-001"
        mock_attempt.selected_answer = "B"
        mock_attempt.is_correct = False
        mock_attempt.exam_id = None
        mock_attempt.time_spent_ms = 3000
        mock_attempt.created_at = MagicMock()
        mock_attempt.created_at.isoformat = MagicMock(return_value="2026-03-05T10:00:00")
        mock_exam.record_quiz_attempt = AsyncMock(return_value=mock_attempt)

        resp = await async_client.post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": "qq-001",
                "selected_answer": "B",
                "is_correct": False,
            },
        )
        assert resp.status_code == 201
        mock_xp.award_xp.assert_not_called()


class TestSessionAwardsXP:
    """Tests for XP awarding on exam session recording."""

    @pytest.mark.asyncio
    @patch("app.api.exams.challenge_service")
    @patch("app.api.exams.xp_service")
    @patch("app.api.exams.streak_service")
    @patch("app.api.exams.exam_service")
    async def test_session_awards_streak_xp(
        self, mock_exam, mock_streak, mock_xp, mock_challenge, async_client, mock_session
    ):
        """POST /exams/{id}/sessions awards streak XP."""
        mock_exam_obj = MagicMock()
        mock_exam_obj.id = "exam-001"
        mock_exam_obj.course_id = "course-001"
        mock_exam.get_exam = AsyncMock(return_value=mock_exam_obj)

        mock_study = MagicMock()
        mock_study.id = "ss-001"
        mock_study.exam_id = "exam-001"
        mock_study.course_id = "course-001"
        mock_study.session_date = MagicMock()
        mock_study.session_date.isoformat.return_value = "2026-03-05"
        mock_study.cards_reviewed = 10
        mock_study.quiz_questions_answered = 5
        mock_study.quiz_correct = 4
        mock_study.duration_seconds = 600
        mock_streak.record_study_session = AsyncMock(return_value=mock_study)

        mock_xp.award_xp = AsyncMock(return_value=(MagicMock(), MagicMock(), []))
        mock_challenge.update_challenge_progress = AsyncMock(return_value=None)

        resp = await async_client.post(
            "/api/exams/exam-001/sessions",
            json={
                "cards_reviewed": 10,
                "quiz_questions_answered": 5,
                "quiz_correct": 4,
                "duration_seconds": 600,
            },
        )
        assert resp.status_code == 201
        mock_xp.award_xp.assert_called_once()


class TestDashboardGamification:
    """Tests for gamification in dashboard."""

    @pytest.mark.asyncio
    @patch("app.api.dashboard.achievement_service")
    @patch("app.api.dashboard.challenge_service")
    @patch("app.api.dashboard.xp_service")
    @patch("app.api.dashboard.courseops_service")
    @patch("app.api.dashboard.streak_service")
    @patch("app.api.dashboard.exam_service")
    @patch("app.api.dashboard.srs_service")
    @patch("app.api.dashboard.pipeline_service")
    @patch("app.api.dashboard.review_service")
    @patch("app.api.dashboard.course_service")
    async def test_dashboard_includes_gamification(
        self,
        mock_course,
        mock_review,
        mock_pipeline,
        mock_srs,
        mock_exam,
        mock_streak,
        mock_courseops,
        mock_xp,
        mock_challenge,
        mock_achievement,
        async_client,
    ):
        """GET /dashboard includes gamification summary."""
        mock_review.count_pending_reviews = AsyncMock(return_value=0)
        mock_pipeline.get_recent_activity = AsyncMock(return_value=[])
        mock_course.list_courses_with_stats = AsyncMock(return_value=[])
        mock_srs.get_global_study_stats = AsyncMock(side_effect=Exception("skip"))
        mock_exam.list_exams = AsyncMock(return_value=[])
        mock_streak.get_streak = AsyncMock(side_effect=Exception("skip"))
        mock_courseops.get_upcoming_deadlines_all_courses = AsyncMock(return_value=[])

        mock_xp.get_xp_summary = AsyncMock(return_value={
            "total_xp": 100,
            "level": 2,
            "progress_pct": 50.0,
            "current_threshold": 100,
            "next_threshold": 300,
            "recent_events": [],
        })
        mock_challenge.get_user_challenge_progress = AsyncMock(return_value={
            "challenge_id": "dc-001",
            "challenge_date": "2026-03-05",
            "challenge_type": "review_cards",
            "target": 10,
            "description": "Review 10 flashcards",
            "xp_reward": 25,
            "progress": 3,
            "completed": False,
            "completed_at": None,
        })
        mock_achievement.get_unnotified = AsyncMock(return_value=[])

        resp = await async_client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gamification"] is not None
        assert data["gamification"]["total_xp"] == 100
        assert data["gamification"]["level"] == 2
        assert data["gamification"]["daily_challenge_description"] == "Review 10 flashcards"

    @pytest.mark.asyncio
    @patch("app.api.dashboard.achievement_service")
    @patch("app.api.dashboard.challenge_service")
    @patch("app.api.dashboard.xp_service")
    @patch("app.api.dashboard.courseops_service")
    @patch("app.api.dashboard.streak_service")
    @patch("app.api.dashboard.exam_service")
    @patch("app.api.dashboard.srs_service")
    @patch("app.api.dashboard.pipeline_service")
    @patch("app.api.dashboard.review_service")
    @patch("app.api.dashboard.course_service")
    async def test_dashboard_gamification_failure_is_best_effort(
        self,
        mock_course,
        mock_review,
        mock_pipeline,
        mock_srs,
        mock_exam,
        mock_streak,
        mock_courseops,
        mock_xp,
        mock_challenge,
        mock_achievement,
        async_client,
    ):
        """Gamification failure doesn't break dashboard."""
        mock_review.count_pending_reviews = AsyncMock(return_value=0)
        mock_pipeline.get_recent_activity = AsyncMock(return_value=[])
        mock_course.list_courses_with_stats = AsyncMock(return_value=[])
        mock_srs.get_global_study_stats = AsyncMock(side_effect=Exception("skip"))
        mock_exam.list_exams = AsyncMock(return_value=[])
        mock_streak.get_streak = AsyncMock(side_effect=Exception("skip"))
        mock_courseops.get_upcoming_deadlines_all_courses = AsyncMock(return_value=[])

        # Gamification completely fails
        mock_xp.get_xp_summary = AsyncMock(side_effect=Exception("XP service down"))

        resp = await async_client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gamification"] is None
