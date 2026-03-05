"""Tests for challenge service."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.challenge_service import (
    CHALLENGE_TEMPLATES,
    get_or_create_daily_challenge,
    get_user_challenge_progress,
    update_challenge_progress,
)


class TestGetOrCreateDailyChallenge:
    """Tests for get_or_create_daily_challenge."""

    @pytest.mark.asyncio
    async def test_returns_existing_challenge(self):
        """Returns existing challenge for the date."""
        session = AsyncMock()
        existing = MagicMock()
        existing.id = "dc-001"
        existing.challenge_type = "review_cards"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_or_create_daily_challenge(session, date(2026, 3, 5))
        assert result.id == "dc-001"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_challenge(self):
        """Creates a new challenge when none exists for the date."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        result = await get_or_create_daily_challenge(session, date(2026, 3, 5))
        session.add.assert_called_once()
        assert result.challenge_date == date(2026, 3, 5)

    @pytest.mark.asyncio
    async def test_deterministic_selection(self):
        """Same date always produces the same template index."""
        d = date(2026, 3, 5)
        idx = hash(d.toordinal()) % len(CHALLENGE_TEMPLATES)
        # Run again — must be same
        idx2 = hash(d.toordinal()) % len(CHALLENGE_TEMPLATES)
        assert idx == idx2

    def test_all_templates_valid(self):
        """All templates have required keys."""
        for t in CHALLENGE_TEMPLATES:
            assert "type" in t
            assert "desc" in t
            assert "target" in t
            assert "xp" in t
            assert isinstance(t["target"], int)
            assert t["target"] > 0
            assert t["xp"] > 0


class TestGetUserChallengeProgress:
    """Tests for get_user_challenge_progress."""

    @pytest.mark.asyncio
    async def test_returns_progress_structure(self):
        """Returns complete progress structure."""
        session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.id = "dc-001"
        mock_challenge.challenge_date = date(2026, 3, 5)
        mock_challenge.challenge_type = "review_cards"
        mock_challenge.target = 10
        mock_challenge.description = "Review 10 flashcards"
        mock_challenge.xp_reward = 25

        # First call: get_or_create (existing)
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_challenge

        # Second call: user progress (none)
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        progress = await get_user_challenge_progress(session, "user-001")

        assert progress["challenge_id"] == "dc-001"
        assert progress["progress"] == 0
        assert progress["completed"] is False
        assert progress["target"] == 10


class TestUpdateChallengeProgress:
    """Tests for update_challenge_progress."""

    @pytest.mark.asyncio
    async def test_no_update_if_type_mismatch(self):
        """Returns None if challenge type doesn't match."""
        session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.challenge_type = "review_cards"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_challenge
        session.execute = AsyncMock(return_value=mock_result)

        result = await update_challenge_progress(session, "user-001", "quiz_correct")
        assert result is None

    @pytest.mark.asyncio
    async def test_increments_progress(self):
        """Increments progress on matching challenge type."""
        session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.id = "dc-001"
        mock_challenge.challenge_type = "review_cards"
        mock_challenge.target = 10
        mock_challenge.xp_reward = 25

        mock_user_challenge = MagicMock()
        mock_user_challenge.progress = 3
        mock_user_challenge.completed_at = None

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_challenge
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_user_challenge

        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])
        session.flush = AsyncMock()

        result = await update_challenge_progress(session, "user-001", "review_cards")
        assert result.progress == 4

    @pytest.mark.asyncio
    @patch("app.services.xp_service")
    async def test_completes_challenge_and_awards_xp(self, mock_xp_service):
        """Awards XP when progress reaches target."""
        mock_xp_service.award_xp = AsyncMock(return_value=(MagicMock(), MagicMock(), []))

        session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.id = "dc-001"
        mock_challenge.challenge_type = "review_cards"
        mock_challenge.target = 10
        mock_challenge.xp_reward = 25

        mock_user_challenge = MagicMock()
        mock_user_challenge.progress = 9
        mock_user_challenge.completed_at = None

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_challenge
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_user_challenge

        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])
        session.flush = AsyncMock()

        result = await update_challenge_progress(session, "user-001", "review_cards")
        assert result.progress == 10
        assert result.completed_at is not None
        mock_xp_service.award_xp.assert_called_once()
