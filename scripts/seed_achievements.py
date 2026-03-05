#!/usr/bin/env python3
"""Seed the database with achievement definitions.

Idempotent: upserts achievements by unique `code`. Safe to run multiple times.

Usage:
    DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
    python scripts/seed_achievements.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add services/app to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils import generate_id
from app.models.achievement import Achievement

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio",
)

ACHIEVEMENTS = [
    {
        "code": "first_upload",
        "title": "First Upload",
        "description": "Upload your first lecture file",
        "icon": "upload",
        "category": "milestone",
        "xp_reward": 25,
        "criteria_json": {"type": "count", "event_type": "upload", "threshold": 1},
    },
    {
        "code": "five_uploads",
        "title": "Dedicated Student",
        "description": "Upload 5 lecture files",
        "icon": "folder",
        "category": "milestone",
        "xp_reward": 50,
        "criteria_json": {"type": "count", "event_type": "upload", "threshold": 5},
    },
    {
        "code": "first_review",
        "title": "First Steps",
        "description": "Review your first flashcard",
        "icon": "play",
        "category": "study",
        "xp_reward": 10,
        "criteria_json": {"type": "count", "event_type": "card_reviewed", "threshold": 1},
    },
    {
        "code": "fifty_reviews",
        "title": "Card Scholar",
        "description": "Review 50 flashcards",
        "icon": "book",
        "category": "study",
        "xp_reward": 50,
        "criteria_json": {"type": "count", "event_type": "card_reviewed", "threshold": 50},
    },
    {
        "code": "two_hundred_reviews",
        "title": "Card Master",
        "description": "Review 200 flashcards",
        "icon": "trophy",
        "category": "study",
        "xp_reward": 100,
        "criteria_json": {"type": "count", "event_type": "card_reviewed", "threshold": 200},
    },
    {
        "code": "thousand_reviews",
        "title": "Card Grandmaster",
        "description": "Review 1,000 flashcards",
        "icon": "crown",
        "category": "study",
        "xp_reward": 250,
        "criteria_json": {"type": "count", "event_type": "card_reviewed", "threshold": 1000},
    },
    {
        "code": "first_quiz",
        "title": "Quiz Starter",
        "description": "Answer your first quiz question correctly",
        "icon": "check",
        "category": "study",
        "xp_reward": 10,
        "criteria_json": {"type": "count", "event_type": "quiz_correct", "threshold": 1},
    },
    {
        "code": "fifty_quiz",
        "title": "Quiz Champion",
        "description": "Answer 50 quiz questions correctly",
        "icon": "medal",
        "category": "study",
        "xp_reward": 75,
        "criteria_json": {"type": "count", "event_type": "quiz_correct", "threshold": 50},
    },
    {
        "code": "streak_3",
        "title": "Getting Consistent",
        "description": "Maintain a 3-day study streak",
        "icon": "flame",
        "category": "streak",
        "xp_reward": 30,
        "criteria_json": {"type": "streak", "threshold": 3},
    },
    {
        "code": "streak_7",
        "title": "Week Warrior",
        "description": "Maintain a 7-day study streak",
        "icon": "flame",
        "category": "streak",
        "xp_reward": 75,
        "criteria_json": {"type": "streak", "threshold": 7},
    },
    {
        "code": "streak_14",
        "title": "Fortnight Fighter",
        "description": "Maintain a 14-day study streak",
        "icon": "flame",
        "category": "streak",
        "xp_reward": 150,
        "criteria_json": {"type": "streak", "threshold": 14},
    },
    {
        "code": "streak_30",
        "title": "Monthly Master",
        "description": "Maintain a 30-day study streak",
        "icon": "flame",
        "category": "streak",
        "xp_reward": 300,
        "criteria_json": {"type": "streak", "threshold": 30},
    },
    {
        "code": "level_3",
        "title": "Rising Scholar",
        "description": "Reach level 3",
        "icon": "star",
        "category": "milestone",
        "xp_reward": 0,
        "criteria_json": {"type": "level", "threshold": 3},
    },
    {
        "code": "level_5",
        "title": "Dedicated Learner",
        "description": "Reach level 5",
        "icon": "star",
        "category": "milestone",
        "xp_reward": 0,
        "criteria_json": {"type": "level", "threshold": 5},
    },
    {
        "code": "level_10",
        "title": "Knowledge Sage",
        "description": "Reach level 10",
        "icon": "star",
        "category": "milestone",
        "xp_reward": 0,
        "criteria_json": {"type": "level", "threshold": 10},
    },
    {
        "code": "xp_500",
        "title": "XP Collector",
        "description": "Earn 500 total XP",
        "icon": "zap",
        "category": "milestone",
        "xp_reward": 0,
        "criteria_json": {"type": "total_xp", "threshold": 500},
    },
    {
        "code": "xp_2000",
        "title": "XP Hoarder",
        "description": "Earn 2,000 total XP",
        "icon": "zap",
        "category": "milestone",
        "xp_reward": 0,
        "criteria_json": {"type": "total_xp", "threshold": 2000},
    },
    {
        "code": "first_challenge",
        "title": "Challenge Accepted",
        "description": "Complete your first daily challenge",
        "icon": "target",
        "category": "study",
        "xp_reward": 20,
        "criteria_json": {"type": "count", "event_type": "challenge_completed", "threshold": 1},
    },
    {
        "code": "five_challenges",
        "title": "Challenge Champion",
        "description": "Complete 5 daily challenges",
        "icon": "target",
        "category": "study",
        "xp_reward": 50,
        "criteria_json": {"type": "count", "event_type": "challenge_completed", "threshold": 5},
    },
    {
        "code": "concept_master",
        "title": "Concept Master",
        "description": "Achieve 80% mastery across your flashcards",
        "icon": "brain",
        "category": "mastery",
        "xp_reward": 100,
        "criteria_json": {"type": "mastery_pct", "threshold": 80},
    },
]


async def seed_achievements() -> None:
    """Upsert achievement definitions into the database."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        created = 0
        updated = 0

        for ach_data in ACHIEVEMENTS:
            result = await session.execute(
                select(Achievement).where(Achievement.code == ach_data["code"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update fields in case definition changed
                existing.title = ach_data["title"]
                existing.description = ach_data["description"]
                existing.icon = ach_data["icon"]
                existing.category = ach_data["category"]
                existing.xp_reward = ach_data["xp_reward"]
                existing.criteria_json = ach_data["criteria_json"]
                updated += 1
            else:
                session.add(Achievement(
                    id=generate_id(),
                    **ach_data,
                ))
                created += 1

        await session.commit()
        print(f"Achievements seeded: {created} created, {updated} updated, {len(ACHIEVEMENTS)} total")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_achievements())
