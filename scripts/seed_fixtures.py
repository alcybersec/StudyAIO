#!/usr/bin/env python3
"""Seed the database with demo data for development and testing.

Creates courses, artifacts, summaries, flashcards, quiz questions,
and review items. Idempotent: safe to run multiple times.

Usage:
    DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
    python scripts/seed_fixtures.py
"""

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add services/app to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.utils import generate_id
from app.models.course import Course
from app.models.artifact import LectureArtifact
from app.models.summary import Summary
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.review_item import ReviewItem


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio",
)


# ── Seed data definitions ────────────────────────────────────────────

COURSES = [
    {"code": "CSIT302", "name": "Cybersecurity", "term": "2025-S1"},
    {"code": "CSIT314", "name": "Software Engineering", "term": "2025-S1"},
]

WEEKS = {
    "CSIT302": [
        (1, "Introduction to Cybersecurity"),
        (2, "Cryptography Fundamentals"),
        (3, "Network Security"),
        (4, "Web Application Security"),
    ],
    "CSIT314": [
        (1, "Software Development Life Cycle"),
        (2, "Requirements Engineering"),
        (3, "Design Patterns"),
    ],
}


def _make_summary_md(course_code: str, week: int, title: str) -> str:
    """Generate a valid 8-section summary markdown."""
    return f"""# {course_code} — Week {week}: {title}

## Key Concepts
- Core principles of {title.lower()}
- Practical applications and real-world examples
- Common pitfalls and best practices

## Definitions

| Term | Definition |
|------|-----------|
| {title.split()[0]} | A fundamental concept in {course_code} |
| Practice | The application of theoretical knowledge |
| Framework | A structured approach to solving problems |

## Code Examples

```python
# Example: {title}
def demonstrate():
    print("Week {week} concepts in action")
    return True
```

## Diagrams & Figures

![Overview diagram](page1_img1.png)
*Figure 1: {title} overview*

## Potential Exam Topics
- Define and explain {title.lower()}
- Compare approaches discussed in this week
- Apply concepts to a real-world scenario

## Summary

This week covers {title.lower()}, building on the foundations established in
previous weeks. Students should focus on understanding the core principles
and their practical applications.

The material connects to broader themes in {course_code} and prepares
students for upcoming assessments.

---
**Sources:** {course_code}_Week{week}.pdf | **Version:** 1 | **Generated:** 2025-03-01
"""


FLASHCARD_TEMPLATES = [
    ("What is the main topic of this week?", "The main topic is {title}, covering fundamental concepts and applications.", ["core", "overview"]),
    ("List three key principles.", "1. Understanding fundamentals\n2. Practical application\n3. Critical analysis", ["principles"]),
    ("Why is this topic important?", "{title} is essential because it forms the foundation for advanced topics in the course.", ["importance"]),
    ("What are common misconceptions?", "Students often confuse theoretical concepts with practical implementation details.", ["misconceptions"]),
    ("How does this relate to previous weeks?", "This topic builds on prior foundations and extends them with new concepts.", ["connections"]),
]

QUIZ_TEMPLATES = [
    {
        "question_type": "multiple_choice",
        "question": "Which of the following best describes {title}?",
        "options": [
            "A theoretical framework for analysis",
            "A practical methodology for implementation",
            "A combination of theory and practice",
            "None of the above",
        ],
        "correct_answer": "A combination of theory and practice",
        "explanation": "{title} encompasses both theoretical foundations and practical applications.",
    },
    {
        "question_type": "multiple_choice",
        "question": "What is the primary goal of studying {title}?",
        "options": [
            "Memorization of facts",
            "Understanding core principles and their applications",
            "Learning specific tools only",
            "Historical analysis",
        ],
        "correct_answer": "Understanding core principles and their applications",
        "explanation": "The focus is on understanding principles that can be applied broadly.",
    },
    {
        "question_type": "short_answer",
        "question": "Explain the significance of {title} in the context of {course_code}.",
        "options": None,
        "correct_answer": "{title} is significant because it provides foundational knowledge necessary for understanding advanced topics in {course_code}.",
        "explanation": "A good answer should connect the specific topic to the broader course objectives.",
    },
]


# ── Helpers ──────────────────────────────────────────────────────────


async def course_exists(session: AsyncSession, code: str) -> Course | None:
    """Return existing course or None."""
    result = await session.execute(select(Course).where(Course.code == code))
    return result.scalar_one_or_none()


async def summary_exists(session: AsyncSession, course_id: str, week: int) -> bool:
    """Check if a summary already exists for this course+week."""
    result = await session.execute(
        select(Summary.id).where(Summary.course_id == course_id, Summary.week == week)
    )
    return result.scalar_one_or_none() is not None


# ── Main seed logic ──────────────────────────────────────────────────


async def seed():
    """Populate the database with demo data."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    stats = {
        "courses": 0,
        "artifacts": 0,
        "summaries": 0,
        "flashcards": 0,
        "quiz_questions": 0,
        "review_items": 0,
        "skipped": 0,
    }

    async with session_factory() as session:
        for course_def in COURSES:
            # ── Course ──
            existing = await course_exists(session, course_def["code"])
            if existing:
                course = existing
                print(f"  Course {course_def['code']} already exists, reusing")
            else:
                course = Course(
                    id=generate_id(),
                    code=course_def["code"],
                    name=course_def["name"],
                    term=course_def["term"],
                )
                session.add(course)
                await session.flush()
                stats["courses"] += 1
                print(f"  Created course: {course_def['code']} — {course_def['name']}")

            weeks = WEEKS[course_def["code"]]

            for week_num, title in weeks:
                # ── Artifact ──
                fake_sha = hashlib.sha256(
                    f"seed:{course_def['code']}:week{week_num}".encode()
                ).hexdigest()
                result = await session.execute(
                    select(LectureArtifact.id).where(LectureArtifact.sha256 == fake_sha)
                )
                existing_artifact_id = result.scalar_one_or_none()

                if existing_artifact_id:
                    artifact_id = existing_artifact_id
                    stats["skipped"] += 1
                else:
                    artifact_id = generate_id()
                    filename = f"{course_def['code']}_Week{week_num}.pdf"
                    artifact = LectureArtifact(
                        id=artifact_id,
                        course_id=course.id,
                        week=week_num,
                        title=title,
                        original_filename=filename,
                        file_path=f"/app/data/uploads/{artifact_id}_{filename}",
                        file_type="pdf",
                        sha256=fake_sha,
                        file_size_bytes=50000 + week_num * 10000,
                        status="processed",
                        pipeline_started_at=datetime.utcnow() - timedelta(hours=1),
                        pipeline_completed_at=datetime.utcnow(),
                    )
                    session.add(artifact)
                    await session.flush()
                    stats["artifacts"] += 1

                # ── Summary ──
                if not await summary_exists(session, course.id, week_num):
                    content_md = _make_summary_md(course_def["code"], week_num, title)
                    summary = Summary(
                        id=generate_id(),
                        course_id=course.id,
                        week=week_num,
                        content_md=content_md,
                        file_path=f"/app/data/summaries/{course_def['code']}/{course_def['code']}_Week{week_num}.md",
                        version=1,
                        source_artifacts=[artifact_id],
                    )
                    session.add(summary)
                    stats["summaries"] += 1

                # ── Flashcards ──
                result = await session.execute(
                    select(Flashcard.id).where(
                        Flashcard.source_artifact_id == artifact_id
                    ).limit(1)
                )
                if result.scalar_one_or_none() is None:
                    for front_tpl, back_tpl, tags in FLASHCARD_TEMPLATES:
                        fc = Flashcard(
                            id=generate_id(),
                            course_id=course.id,
                            week=week_num,
                            front=front_tpl,
                            back=back_tpl.format(title=title),
                            tags=tags,
                            source_artifact_id=artifact_id,
                            source_page_ref=1,
                            generation_version=1,
                        )
                        session.add(fc)
                        stats["flashcards"] += 1

                # ── Quiz questions ──
                result = await session.execute(
                    select(QuizQuestion.id).where(
                        QuizQuestion.source_artifact_id == artifact_id
                    ).limit(1)
                )
                if result.scalar_one_or_none() is None:
                    for q_tpl in QUIZ_TEMPLATES:
                        qq = QuizQuestion(
                            id=generate_id(),
                            course_id=course.id,
                            week=week_num,
                            question_type=q_tpl["question_type"],
                            question=q_tpl["question"].format(
                                title=title, course_code=course_def["code"]
                            ),
                            options_json=q_tpl["options"],
                            correct_answer=q_tpl["correct_answer"].format(
                                title=title, course_code=course_def["code"]
                            ),
                            explanation=q_tpl["explanation"].format(
                                title=title, course_code=course_def["code"]
                            ),
                            source_artifact_id=artifact_id,
                            source_page_ref=1,
                            generation_version=1,
                        )
                        session.add(qq)
                        stats["quiz_questions"] += 1

        # ── Review Items (one per course) ──
        result = await session.execute(
            select(ReviewItem.id).where(ReviewItem.status == "pending").limit(1)
        )
        if result.scalar_one_or_none() is None:
            # Get first artifact for a review item
            result = await session.execute(
                select(LectureArtifact.id).limit(1)
            )
            first_artifact_id = result.scalar_one_or_none()
            if first_artifact_id:
                ri = ReviewItem(
                    id=generate_id(),
                    review_type="classification",
                    entity_type="lecture_artifact",
                    entity_id=first_artifact_id,
                    payload_json={
                        "original_filename": "UnknownLecture.pdf",
                        "text_preview": "This lecture covers advanced topics...",
                    },
                    suggested_values={
                        "course_code": "CSIT302",
                        "week": 5,
                        "title": "Advanced Topics",
                        "confidence": 0.45,
                    },
                    status="pending",
                )
                session.add(ri)
                stats["review_items"] += 1

                ri2 = ReviewItem(
                    id=generate_id(),
                    review_type="classification",
                    entity_type="lecture_artifact",
                    entity_id=first_artifact_id,
                    payload_json={
                        "original_filename": "Lecture_Misc.pptx",
                        "text_preview": "Software architecture patterns...",
                    },
                    suggested_values={
                        "course_code": "CSIT314",
                        "week": 4,
                        "title": "Architecture Patterns",
                        "confidence": 0.38,
                    },
                    status="pending",
                )
                session.add(ri2)
                stats["review_items"] += 1

        await session.commit()

    # ── Report ──
    print("\n=== Seed Report ===")
    print(f"  Courses created:     {stats['courses']}")
    print(f"  Artifacts created:   {stats['artifacts']}")
    print(f"  Summaries created:   {stats['summaries']}")
    print(f"  Flashcards created:  {stats['flashcards']}")
    print(f"  Quiz questions:      {stats['quiz_questions']}")
    print(f"  Review items:        {stats['review_items']}")
    print(f"  Skipped (existing):  {stats['skipped']}")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
