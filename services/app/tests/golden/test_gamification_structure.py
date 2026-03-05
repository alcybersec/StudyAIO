"""Golden tests for gamification response structures.

Validates that gamification-related data conforms to expected schemas:
- XP summary: level, progress, thresholds, recent events
- XP event: type, amount, timestamp
- Achievement: earned vs unearned, criteria types
- Daily challenge: progress, completion
- Leaderboard: ranked entries
- Dashboard gamification summary
- Level thresholds and XP amounts validity
"""

import pytest

from app.services.xp_service import LEVEL_THRESHOLDS, XP_AMOUNTS
from app.services.challenge_service import CHALLENGE_TEMPLATES


# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_xp_summary():
    """A realistic XP summary response."""
    return {
        "total_xp": 250,
        "level": 2,
        "progress_pct": 75.0,
        "current_threshold": 100,
        "next_threshold": 300,
        "recent_events": [
            {
                "id": "evt-001",
                "event_type": "card_reviewed",
                "xp_amount": 5,
                "created_at": "2026-03-05T10:00:00",
            },
        ],
    }


@pytest.fixture
def sample_xp_event():
    """A realistic XP event."""
    return {
        "id": "evt-001",
        "event_type": "card_reviewed",
        "xp_amount": 5,
        "created_at": "2026-03-05T10:00:00",
    }


@pytest.fixture
def sample_achievement_earned():
    """An earned achievement."""
    return {
        "id": "ach-001",
        "code": "first_review",
        "title": "First Steps",
        "description": "Review your first flashcard",
        "icon": "star",
        "category": "study",
        "xp_reward": 10,
        "earned": True,
        "earned_at": "2026-03-05T10:00:00",
    }


@pytest.fixture
def sample_achievement_unearned():
    """An unearned achievement."""
    return {
        "id": "ach-002",
        "code": "fifty_reviews",
        "title": "Card Scholar",
        "description": "Review 50 flashcards",
        "icon": "book",
        "category": "study",
        "xp_reward": 50,
        "earned": False,
        "earned_at": None,
    }


@pytest.fixture
def sample_daily_challenge():
    """A realistic daily challenge response."""
    return {
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


@pytest.fixture
def sample_daily_challenge_completed():
    """A completed daily challenge."""
    return {
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


@pytest.fixture
def sample_leaderboard_entry():
    """A realistic leaderboard entry."""
    return {
        "user_id": "user-001",
        "username": "alice",
        "total_xp": 1000,
        "level": 5,
        "rank": 1,
    }


@pytest.fixture
def sample_dashboard_gamification():
    """A realistic dashboard gamification summary."""
    return {
        "total_xp": 250,
        "level": 2,
        "progress_pct": 75.0,
        "next_threshold": 300,
        "daily_challenge_description": "Review 10 flashcards",
        "daily_challenge_progress": 4,
        "daily_challenge_target": 10,
        "daily_challenge_completed": False,
        "unnotified_achievement_count": 1,
    }


# ── XP Summary structure ────────────────────────────────────────────


class TestXPSummaryStructure:
    """Validate XP summary response structure."""

    def test_has_required_fields(self, sample_xp_summary):
        """XP summary has all required fields."""
        required = {
            "total_xp", "level", "progress_pct", "current_threshold",
            "next_threshold", "recent_events",
        }
        missing = required - sample_xp_summary.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_total_xp_is_non_negative(self, sample_xp_summary):
        """Total XP is a non-negative integer."""
        assert isinstance(sample_xp_summary["total_xp"], int)
        assert sample_xp_summary["total_xp"] >= 0

    def test_level_is_positive(self, sample_xp_summary):
        """Level is a positive integer."""
        assert isinstance(sample_xp_summary["level"], int)
        assert sample_xp_summary["level"] >= 1

    def test_progress_pct_is_valid(self, sample_xp_summary):
        """Progress percentage is between 0 and 100."""
        pct = sample_xp_summary["progress_pct"]
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100


# ── XP Event structure ──────────────────────────────────────────────


class TestXPEventStructure:
    """Validate XP event structure."""

    def test_has_required_fields(self, sample_xp_event):
        """XP event has all required fields."""
        required = {"id", "event_type", "xp_amount", "created_at"}
        missing = required - sample_xp_event.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_xp_amount_is_positive(self, sample_xp_event):
        """XP amount is positive."""
        assert isinstance(sample_xp_event["xp_amount"], int)
        assert sample_xp_event["xp_amount"] > 0


# ── Achievement structure ────────────────────────────────────────────


class TestAchievementStructure:
    """Validate achievement response structure."""

    def test_earned_has_required_fields(self, sample_achievement_earned):
        """Earned achievement has all required fields."""
        required = {
            "id", "code", "title", "description", "icon",
            "category", "xp_reward", "earned", "earned_at",
        }
        missing = required - sample_achievement_earned.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_earned_has_earned_at(self, sample_achievement_earned):
        """Earned achievement has earned_at timestamp."""
        assert sample_achievement_earned["earned"] is True
        assert sample_achievement_earned["earned_at"] is not None

    def test_unearned_has_no_earned_at(self, sample_achievement_unearned):
        """Unearned achievement has earned_at as None."""
        assert sample_achievement_unearned["earned"] is False
        assert sample_achievement_unearned["earned_at"] is None


# ── Daily Challenge structure ────────────────────────────────────────


class TestDailyChallengeStructure:
    """Validate daily challenge response structure."""

    def test_incomplete_has_required_fields(self, sample_daily_challenge):
        """Incomplete challenge has all required fields."""
        required = {
            "challenge_id", "challenge_date", "challenge_type", "target",
            "description", "xp_reward", "progress", "completed", "completed_at",
        }
        missing = required - sample_daily_challenge.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_incomplete_is_not_completed(self, sample_daily_challenge):
        """Incomplete challenge has completed=False."""
        assert sample_daily_challenge["completed"] is False
        assert sample_daily_challenge["completed_at"] is None

    def test_completed_has_timestamp(self, sample_daily_challenge_completed):
        """Completed challenge has completed_at."""
        assert sample_daily_challenge_completed["completed"] is True
        assert sample_daily_challenge_completed["completed_at"] is not None

    def test_progress_does_not_exceed_target(self, sample_daily_challenge):
        """Progress should not exceed target on incomplete challenge."""
        assert sample_daily_challenge["progress"] <= sample_daily_challenge["target"]


# ── Leaderboard structure ────────────────────────────────────────────


class TestLeaderboardStructure:
    """Validate leaderboard entry structure."""

    def test_has_required_fields(self, sample_leaderboard_entry):
        """Leaderboard entry has all required fields."""
        required = {"user_id", "username", "total_xp", "level", "rank"}
        missing = required - sample_leaderboard_entry.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_rank_is_positive(self, sample_leaderboard_entry):
        """Rank is a positive integer."""
        assert isinstance(sample_leaderboard_entry["rank"], int)
        assert sample_leaderboard_entry["rank"] >= 1


# ── Dashboard gamification structure ─────────────────────────────────


class TestDashboardGamificationStructure:
    """Validate dashboard gamification summary structure."""

    def test_has_required_fields(self, sample_dashboard_gamification):
        """Dashboard gamification has all required fields."""
        required = {
            "total_xp", "level", "progress_pct", "next_threshold",
            "daily_challenge_description", "daily_challenge_progress",
            "daily_challenge_target", "daily_challenge_completed",
            "unnotified_achievement_count",
        }
        missing = required - sample_dashboard_gamification.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_unnotified_count_is_non_negative(self, sample_dashboard_gamification):
        """Unnotified count is non-negative."""
        assert sample_dashboard_gamification["unnotified_achievement_count"] >= 0


# ── Constants validity ──────────────────────────────────────────────


class TestLevelThresholdsValidity:
    """Validate level threshold constants."""

    def test_monotonically_increasing(self):
        """Level thresholds must be strictly increasing."""
        for i in range(1, len(LEVEL_THRESHOLDS)):
            assert LEVEL_THRESHOLDS[i] > LEVEL_THRESHOLDS[i - 1], (
                f"Threshold {i} ({LEVEL_THRESHOLDS[i]}) not greater than "
                f"threshold {i-1} ({LEVEL_THRESHOLDS[i-1]})"
            )

    def test_starts_at_zero(self):
        """First threshold is 0."""
        assert LEVEL_THRESHOLDS[0] == 0

    def test_has_at_least_two_levels(self):
        """At least 2 levels defined."""
        assert len(LEVEL_THRESHOLDS) >= 2


class TestXPAmountsValidity:
    """Validate XP amount constants."""

    def test_all_amounts_are_non_negative(self):
        """All XP amounts are non-negative integers."""
        for event_type, amount in XP_AMOUNTS.items():
            assert isinstance(amount, int), f"{event_type} amount is not int"
            assert amount >= 0, f"{event_type} amount is negative"

    def test_core_events_have_positive_amounts(self):
        """Core gameplay events award positive XP."""
        core = ["card_reviewed", "quiz_correct", "streak_day", "upload"]
        for event_type in core:
            assert event_type in XP_AMOUNTS, f"{event_type} not in XP_AMOUNTS"
            assert XP_AMOUNTS[event_type] > 0, f"{event_type} has zero XP"


class TestChallengeTemplatesValidity:
    """Validate challenge template constants."""

    def test_all_templates_have_required_keys(self):
        """All templates have type, desc, target, xp."""
        for i, t in enumerate(CHALLENGE_TEMPLATES):
            assert "type" in t, f"Template {i} missing 'type'"
            assert "desc" in t, f"Template {i} missing 'desc'"
            assert "target" in t, f"Template {i} missing 'target'"
            assert "xp" in t, f"Template {i} missing 'xp'"

    def test_all_targets_positive(self):
        """All challenge targets are positive integers."""
        for t in CHALLENGE_TEMPLATES:
            assert isinstance(t["target"], int)
            assert t["target"] > 0

    def test_all_xp_rewards_positive(self):
        """All challenge XP rewards are positive."""
        for t in CHALLENGE_TEMPLATES:
            assert isinstance(t["xp"], int)
            assert t["xp"] > 0

    def test_descriptions_contain_target_placeholder(self):
        """Descriptions with numeric targets use {target} placeholder."""
        for t in CHALLENGE_TEMPLATES:
            if t["target"] > 1:
                assert "{target}" in t["desc"], (
                    f"Template '{t['type']}' desc should contain {{target}}"
                )
