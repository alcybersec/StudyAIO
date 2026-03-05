"""Pydantic schemas for gamification endpoints."""

from pydantic import BaseModel


class XPEventItem(BaseModel):
    """A single XP event."""

    id: str
    event_type: str
    xp_amount: int
    created_at: str


class XPSummaryResponse(BaseModel):
    """User XP summary with level progress."""

    total_xp: int
    level: int
    progress_pct: float
    current_threshold: int
    next_threshold: int | None
    recent_events: list[XPEventItem]


class AchievementItem(BaseModel):
    """A single achievement with earned status."""

    id: str
    code: str
    title: str
    description: str
    icon: str
    category: str
    xp_reward: int
    earned: bool
    earned_at: str | None


class AchievementsListResponse(BaseModel):
    """All achievements with user progress."""

    total: int
    earned: int
    achievements: list[AchievementItem]


class DailyChallengeResponse(BaseModel):
    """Today's daily challenge with user progress."""

    challenge_id: str
    challenge_date: str
    challenge_type: str
    target: int
    description: str
    xp_reward: int
    progress: int
    completed: bool
    completed_at: str | None


class LeaderboardEntry(BaseModel):
    """A single leaderboard entry."""

    user_id: str
    username: str
    total_xp: int
    level: int
    rank: int


class LeaderboardResponse(BaseModel):
    """Top users by XP."""

    entries: list[LeaderboardEntry]


class UnnotifiedAchievement(BaseModel):
    """Achievement earned but not yet shown to user."""

    user_achievement_id: str
    code: str
    title: str
    description: str
    icon: str
    xp_reward: int
    earned_at: str


class MarkNotifiedRequest(BaseModel):
    """Request to mark achievements as notified."""

    user_achievement_ids: list[str]
