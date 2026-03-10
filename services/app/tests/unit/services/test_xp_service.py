"""Tests for XP service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.xp_service import (
    LEVEL_THRESHOLDS,
    XP_AMOUNTS,
    award_xp,
    calculate_level,
    get_leaderboard,
    get_or_create_user_xp,
    get_xp_summary,
    xp_for_next_level,
)


class TestCalculateLevel:
    """Tests for calculate_level."""

    def test_zero_xp_is_level_1(self):
        """Zero XP gives level 1."""
        assert calculate_level(0) == 1

    def test_exactly_at_threshold(self):
        """XP exactly at a threshold gives that level."""
        assert calculate_level(100) == 2
        assert calculate_level(300) == 3
        assert calculate_level(600) == 4

    def test_between_thresholds(self):
        """XP between thresholds gives lower level."""
        assert calculate_level(50) == 1
        assert calculate_level(200) == 2
        assert calculate_level(450) == 3

    def test_above_max_threshold(self):
        """XP above max threshold gives highest level."""
        assert calculate_level(10000) == len(LEVEL_THRESHOLDS)

    def test_negative_xp_is_level_1(self):
        """Negative XP still gives level 1."""
        assert calculate_level(-10) == 1


class TestXPForNextLevel:
    """Tests for xp_for_next_level."""

    def test_level_1(self):
        """Level 1 needs 100 XP to reach level 2."""
        current, next_val = xp_for_next_level(1)
        assert current == 0
        assert next_val == 100

    def test_max_level(self):
        """Max level has no next threshold."""
        max_level = len(LEVEL_THRESHOLDS)
        current, next_val = xp_for_next_level(max_level)
        assert next_val is None


class TestGetOrCreateUserXP:
    """Tests for get_or_create_user_xp."""

    @pytest.mark.asyncio
    async def test_returns_existing(self):
        """Returns existing UserXP record."""
        session = AsyncMock()
        mock_xp = MagicMock()
        mock_xp.total_xp = 500
        mock_xp.level = 3

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_xp
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_or_create_user_xp(session, "user-001")
        assert result.total_xp == 500
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new(self):
        """Creates new UserXP when none exists."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        result = await get_or_create_user_xp(session, "user-001")
        session.add.assert_called_once()
        assert result.total_xp == 0
        assert result.level == 1


class TestAwardXP:
    """Tests for award_xp."""

    @pytest.mark.asyncio
    @patch("app.services.achievement_service")
    async def test_awards_default_amount(self, mock_ach_service):
        """Awards default XP for event type."""
        mock_ach_service.check_achievements = AsyncMock(return_value=[])

        session = AsyncMock()
        mock_xp = MagicMock()
        mock_xp.total_xp = 0
        mock_xp.level = 1
        mock_xp.updated_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_xp
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        user_xp, event, achievements = await award_xp(session, "user-001", "card_reviewed")

        assert user_xp.total_xp == XP_AMOUNTS["card_reviewed"]
        assert event.xp_amount == XP_AMOUNTS["card_reviewed"]
        assert event.event_type == "card_reviewed"

    @pytest.mark.asyncio
    @patch("app.services.achievement_service")
    async def test_awards_custom_amount(self, mock_ach_service):
        """Awards custom XP amount when specified."""
        mock_ach_service.check_achievements = AsyncMock(return_value=[])

        session = AsyncMock()
        mock_xp = MagicMock()
        mock_xp.total_xp = 0
        mock_xp.level = 1
        mock_xp.updated_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_xp
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        user_xp, event, _ = await award_xp(session, "user-001", "card_reviewed", xp_amount=50)

        assert event.xp_amount == 50
        assert user_xp.total_xp == 50

    @pytest.mark.asyncio
    @patch("app.services.achievement_service")
    async def test_detects_level_up(self, mock_ach_service):
        """Detects when user levels up."""
        mock_ach_service.check_achievements = AsyncMock(return_value=[])

        session = AsyncMock()
        mock_xp = MagicMock()
        mock_xp.total_xp = 95  # close to level 2 threshold of 100
        mock_xp.level = 1
        mock_xp.updated_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_xp
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        user_xp, _, _ = await award_xp(
            session,
            "user-001",
            "quiz_correct",  # 10 XP → total 105
        )

        assert user_xp.total_xp == 105
        assert user_xp.level == 2


class TestGetXPSummary:
    """Tests for get_xp_summary."""

    @pytest.mark.asyncio
    async def test_returns_summary_structure(self):
        """Returns complete summary structure."""
        session = AsyncMock()

        # First call: get_or_create_user_xp
        mock_xp = MagicMock()
        mock_xp.user_id = "user-001"
        mock_xp.total_xp = 250
        mock_xp.level = 2

        # Mock for get_or_create + recent events
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_xp

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        summary = await get_xp_summary(session, "user-001")

        assert summary["total_xp"] == 250
        assert summary["level"] == 2
        assert "progress_pct" in summary
        assert "current_threshold" in summary
        assert "next_threshold" in summary
        assert "recent_events" in summary


class TestGetLeaderboard:
    """Tests for get_leaderboard."""

    @pytest.mark.asyncio
    async def test_returns_ranked_users(self):
        """Returns ranked leaderboard entries."""
        session = AsyncMock()

        mock_xp1 = MagicMock()
        mock_xp1.user_id = "user-001"
        mock_xp1.total_xp = 1000
        mock_xp1.level = 5

        mock_xp2 = MagicMock()
        mock_xp2.user_id = "user-002"
        mock_xp2.total_xp = 500
        mock_xp2.level = 3

        mock_result = MagicMock()
        mock_result.all.return_value = [
            (mock_xp1, "alice"),
            (mock_xp2, "bob"),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        board = await get_leaderboard(session)

        assert len(board) == 2
        assert board[0]["rank"] == 1
        assert board[0]["username"] == "alice"
        assert board[0]["total_xp"] == 1000
        assert board[1]["rank"] == 2

    @pytest.mark.asyncio
    async def test_empty_leaderboard(self):
        """Returns empty list when no users have XP."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        board = await get_leaderboard(session)
        assert board == []
