"""Tests for achievement service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.achievement_service import (
    _evaluate_criteria,
    check_achievements,
    get_all_with_status,
    get_unnotified,
    mark_notified,
)


class TestEvaluateCriteria:
    """Tests for _evaluate_criteria."""

    @pytest.mark.asyncio
    async def test_count_criteria_met(self):
        """Count criteria evaluates to True when threshold met."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 50
        session.execute = AsyncMock(return_value=mock_result)

        criteria = {"type": "count", "event_type": "card_reviewed", "threshold": 50}
        result = await _evaluate_criteria(session, "user-001", criteria)
        assert result is True

    @pytest.mark.asyncio
    async def test_count_criteria_not_met(self):
        """Count criteria evaluates to False when below threshold."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        session.execute = AsyncMock(return_value=mock_result)

        criteria = {"type": "count", "event_type": "card_reviewed", "threshold": 50}
        result = await _evaluate_criteria(session, "user-001", criteria)
        assert result is False

    @pytest.mark.asyncio
    async def test_total_xp_criteria(self):
        """Total XP criteria checks user_xp table."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1500
        session.execute = AsyncMock(return_value=mock_result)

        criteria = {"type": "total_xp", "threshold": 1000}
        result = await _evaluate_criteria(session, "user-001", criteria)
        assert result is True

    @pytest.mark.asyncio
    async def test_level_criteria(self):
        """Level criteria checks user level."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        session.execute = AsyncMock(return_value=mock_result)

        criteria = {"type": "level", "threshold": 5}
        result = await _evaluate_criteria(session, "user-001", criteria)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_criteria_returns_false(self):
        """Unknown criteria type returns False."""
        session = AsyncMock()
        criteria = {"type": "unknown", "threshold": 1}
        result = await _evaluate_criteria(session, "user-001", criteria)
        assert result is False


class TestCheckAchievements:
    """Tests for check_achievements."""

    @pytest.mark.asyncio
    async def test_skips_already_earned(self):
        """Does not re-award already earned achievements."""
        session = AsyncMock()
        # Return no unearned achievements (all earned)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await check_achievements(session, "user-001", "card_reviewed")
        assert result == []


class TestGetAllWithStatus:
    """Tests for get_all_with_status."""

    @pytest.mark.asyncio
    async def test_returns_achievements_with_earned_status(self):
        """Returns all achievements with earned marker."""
        session = AsyncMock()

        # Mock achievement
        mock_ach = MagicMock()
        mock_ach.id = "ach-001"
        mock_ach.code = "first_review"
        mock_ach.title = "First Steps"
        mock_ach.description = "Review your first flashcard"
        mock_ach.icon = "star"
        mock_ach.category = "study"
        mock_ach.xp_reward = 10

        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [mock_ach]

        # Mock earned — user hasn't earned it
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        items = await get_all_with_status(session, "user-001")
        assert len(items) == 1
        assert items[0]["code"] == "first_review"
        assert items[0]["earned"] is False
        assert items[0]["earned_at"] is None


class TestGetUnnotified:
    """Tests for get_unnotified."""

    @pytest.mark.asyncio
    async def test_returns_unnotified_achievements(self):
        """Returns achievements earned but not yet shown."""
        session = AsyncMock()

        mock_ua = MagicMock()
        mock_ua.id = "ua-001"
        mock_ua.earned_at = MagicMock()
        mock_ua.earned_at.isoformat.return_value = "2026-03-05T10:00:00"

        mock_ach = MagicMock()
        mock_ach.code = "first_review"
        mock_ach.title = "First Steps"
        mock_ach.description = "Review your first flashcard"
        mock_ach.icon = "star"
        mock_ach.xp_reward = 10

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_ua, mock_ach)]
        session.execute = AsyncMock(return_value=mock_result)

        items = await get_unnotified(session, "user-001")
        assert len(items) == 1
        assert items[0]["user_achievement_id"] == "ua-001"
        assert items[0]["code"] == "first_review"


class TestMarkNotified:
    """Tests for mark_notified."""

    @pytest.mark.asyncio
    async def test_marks_achievements_as_notified(self):
        """Sets notified=True on given UserAchievement IDs."""
        session = AsyncMock()

        mock_ua = MagicMock()
        mock_ua.notified = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_ua]
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        await mark_notified(session, ["ua-001"])
        assert mock_ua.notified is True

    @pytest.mark.asyncio
    async def test_empty_list_does_nothing(self):
        """Empty list is a no-op."""
        session = AsyncMock()
        await mark_notified(session, [])
        session.execute.assert_not_called()


class TestAchievementUnlockEmitsInbox:
    """Achievement unlock emits a kind='achievement' inbox notification."""

    @pytest.mark.asyncio
    async def test_unlock_emits_notification(self):
        """Newly earned achievements create an inbox notification."""
        from unittest.mock import patch as _patch

        from app.models.notification import Notification

        achievement = MagicMock()
        achievement.id = "ach-001"
        achievement.code = "first_upload"
        achievement.name = "First Upload"
        achievement.xp_reward = 0
        achievement.criteria_json = {"type": "count", "event": "upload", "threshold": 1}

        session = AsyncMock()
        session.add = MagicMock()
        unearned_result = MagicMock()
        unearned_result.scalars.return_value.all.return_value = [achievement]
        session.execute = AsyncMock(return_value=unearned_result)

        with _patch(
            "app.services.achievement_service._evaluate_criteria",
            new_callable=AsyncMock,
            return_value=True,
        ):
            earned = await check_achievements(session, "user-001", "upload")

        assert len(earned) == 1
        added = [c.args[0] for c in session.add.call_args_list]
        notifications = [n for n in added if isinstance(n, Notification)]
        assert len(notifications) == 1
        assert notifications[0].kind == "achievement"
        assert "First Upload" in notifications[0].title
