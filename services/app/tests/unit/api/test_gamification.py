"""Tests for gamification API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


class TestGetXPSummary:
    """Tests for GET /api/gamification/xp."""

    @pytest.mark.asyncio
    @patch("app.api.gamification.xp_service")
    async def test_returns_xp_summary(self, mock_xp_service, async_client):
        """Returns XP summary for current user."""
        mock_xp_service.get_xp_summary = AsyncMock(
            return_value={
                "total_xp": 250,
                "level": 2,
                "progress_pct": 75.0,
                "current_threshold": 100,
                "next_threshold": 300,
                "recent_events": [],
            }
        )

        resp = await async_client.get("/api/gamification/xp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_xp"] == 250
        assert data["level"] == 2
        assert data["progress_pct"] == 75.0
        assert data["recent_events"] == []

    @pytest.mark.asyncio
    @patch("app.api.gamification.xp_service")
    async def test_new_user_returns_defaults(self, mock_xp_service, async_client):
        """New user gets level 1 with 0 XP."""
        mock_xp_service.get_xp_summary = AsyncMock(
            return_value={
                "total_xp": 0,
                "level": 1,
                "progress_pct": 0.0,
                "current_threshold": 0,
                "next_threshold": 100,
                "recent_events": [],
            }
        )

        resp = await async_client.get("/api/gamification/xp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_xp"] == 0
        assert data["level"] == 1


class TestGetAchievements:
    """Tests for GET /api/gamification/achievements."""

    @pytest.mark.asyncio
    @patch("app.api.gamification.achievement_service")
    async def test_returns_all_achievements(self, mock_ach_service, async_client):
        """Returns all achievements with earned status."""
        mock_ach_service.get_all_with_status = AsyncMock(
            return_value=[
                {
                    "id": "ach-001",
                    "code": "first_review",
                    "title": "First Steps",
                    "description": "Review your first flashcard",
                    "icon": "star",
                    "category": "study",
                    "xp_reward": 10,
                    "earned": True,
                    "earned_at": "2026-03-05T10:00:00",
                },
                {
                    "id": "ach-002",
                    "code": "fifty_reviews",
                    "title": "Card Scholar",
                    "description": "Review 50 flashcards",
                    "icon": "book",
                    "category": "study",
                    "xp_reward": 50,
                    "earned": False,
                    "earned_at": None,
                },
            ]
        )

        resp = await async_client.get("/api/gamification/achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["earned"] == 1
        assert len(data["achievements"]) == 2

    @pytest.mark.asyncio
    @patch("app.api.gamification.achievement_service")
    async def test_no_achievements(self, mock_ach_service, async_client):
        """Returns empty list when no achievements exist."""
        mock_ach_service.get_all_with_status = AsyncMock(return_value=[])

        resp = await async_client.get("/api/gamification/achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["earned"] == 0


class TestGetDailyChallenge:
    """Tests for GET /api/gamification/challenges."""

    @pytest.mark.asyncio
    @patch("app.api.gamification.challenge_service")
    async def test_returns_todays_challenge(self, mock_ch_service, async_client):
        """Returns today's challenge with progress."""
        mock_ch_service.get_user_challenge_progress = AsyncMock(
            return_value={
                "challenge_id": "dc-001",
                "challenge_date": "2026-03-05",
                "challenge_type": "review_cards",
                "target": 10,
                "description": "Review 10 flashcards",
                "xp_reward": 25,
                "progress": 4,
                "completed": False,
                "completed_at": None,
            }
        )

        resp = await async_client.get("/api/gamification/challenges")
        assert resp.status_code == 200
        data = resp.json()
        assert data["challenge_type"] == "review_cards"
        assert data["progress"] == 4
        assert data["completed"] is False

    @pytest.mark.asyncio
    @patch("app.api.gamification.challenge_service")
    async def test_completed_challenge(self, mock_ch_service, async_client):
        """Returns completed challenge with timestamp."""
        mock_ch_service.get_user_challenge_progress = AsyncMock(
            return_value={
                "challenge_id": "dc-001",
                "challenge_date": "2026-03-05",
                "challenge_type": "review_cards",
                "target": 10,
                "description": "Review 10 flashcards",
                "xp_reward": 25,
                "progress": 10,
                "completed": True,
                "completed_at": "2026-03-05T14:30:00",
            }
        )

        resp = await async_client.get("/api/gamification/challenges")
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] is True
        assert data["completed_at"] is not None


class TestGetLeaderboard:
    """Tests for GET /api/gamification/leaderboard."""

    @pytest.mark.asyncio
    @patch("app.api.gamification.xp_service")
    async def test_returns_ranked_entries(self, mock_xp_service, async_client):
        """Returns leaderboard entries ranked by XP."""
        mock_xp_service.get_leaderboard = AsyncMock(
            return_value=[
                {"user_id": "u-001", "username": "alice", "total_xp": 1000, "level": 5, "rank": 1},
                {"user_id": "u-002", "username": "bob", "total_xp": 500, "level": 3, "rank": 2},
            ]
        )

        resp = await async_client.get("/api/gamification/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 2
        assert data["entries"][0]["rank"] == 1
        assert data["entries"][0]["username"] == "alice"

    @pytest.mark.asyncio
    @patch("app.api.gamification.xp_service")
    async def test_empty_leaderboard(self, mock_xp_service, async_client):
        """Returns empty entries when no users have XP."""
        mock_xp_service.get_leaderboard = AsyncMock(return_value=[])

        resp = await async_client.get("/api/gamification/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
