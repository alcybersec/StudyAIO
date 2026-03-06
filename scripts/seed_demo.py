#!/usr/bin/env python3
"""Seed the database with a demo user and rich sample data.

Creates a demo user (role=demo) with courses, artifacts, summaries,
flashcards, quiz questions, study sessions, exams, gamification data,
chat sessions, analytics snapshots, and review items.

Idempotent: safe to run multiple times.

Usage:
    DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
    python scripts/seed_demo.py
"""

import asyncio
import hashlib
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add services/app to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.utils import generate_id
from app.models.achievement import Achievement
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.exam import Exam
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.review_item import ReviewItem
from app.models.study_session import StudySession
from app.models.summary import Summary
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_xp import UserXP
from app.models.xp_event import XPEvent


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio",
)

# ── Constants ───────────────────────────────────────────────────────

DEMO_USER_ID = "00000000-0000-0000-0000-000000000002"
DEMO_EMAIL = "demo@studyaio.app"
DEMO_USERNAME = "demo"

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
    ("Define the key terminology.", "Key terms include fundamental concepts, methodologies, and frameworks discussed in this lecture.", ["terminology"]),
]

QUIZ_TEMPLATES = [
    {
        "question_type": "multiple_choice",
        "question": "Which of the following best describes {title}?",
        "options": ["A theoretical framework for analysis", "A practical methodology for implementation", "A combination of theory and practice", "None of the above"],
        "correct_answer": "A combination of theory and practice",
        "explanation": "{title} encompasses both theoretical foundations and practical applications.",
    },
    {
        "question_type": "multiple_choice",
        "question": "What is the primary goal of studying {title}?",
        "options": ["Memorization of facts", "Understanding core principles and their applications", "Learning specific tools only", "Historical analysis"],
        "correct_answer": "Understanding core principles and their applications",
        "explanation": "The focus is on understanding principles that can be applied broadly.",
    },
    {
        "question_type": "short_answer",
        "question": "Explain the significance of {title} in the context of {course_code}.",
        "options": None,
        "correct_answer": "{title} is significant because it provides foundational knowledge for advanced topics in {course_code}.",
        "explanation": "A good answer should connect the specific topic to the broader course objectives.",
    },
]


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_or_none(session: AsyncSession, model, **filters):
    """Get a single entity or None."""
    stmt = select(model)
    for key, val in filters.items():
        stmt = stmt.where(getattr(model, key) == val)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ── Main seed logic ──────────────────────────────────────────────────


async def seed():
    """Populate the database with demo user and sample data."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    stats = {
        "user": 0, "courses": 0, "artifacts": 0, "summaries": 0,
        "flashcards": 0, "quiz_questions": 0, "flashcard_reviews": 0,
        "study_sessions": 0, "exams": 0, "xp": 0, "achievements": 0,
        "xp_events": 0, "chat_sessions": 0, "chat_messages": 0,
        "analytics_snapshots": 0, "course_documents": 0, "review_items": 0,
        "skipped": 0,
    }

    now = datetime.utcnow()
    today = date.today()

    async with session_factory() as session:
        # ── Demo User ──
        existing_user = await _get_or_none(session, User, id=DEMO_USER_ID)
        if existing_user:
            print(f"  Demo user already exists: {DEMO_EMAIL}")
        else:
            user = User(
                id=DEMO_USER_ID,
                email=DEMO_EMAIL,
                username=DEMO_USERNAME,
                hashed_password=None,  # Demo user has no password
                role="demo",
                tier="free",
                is_active=True,
                email_verified=False,
            )
            session.add(user)
            await session.flush()
            stats["user"] = 1
            print(f"  Created demo user: {DEMO_EMAIL} (role=demo)")

        # ── Courses ──
        course_map: dict[str, str] = {}  # code → id
        for course_def in COURSES:
            existing = await _get_or_none(session, Course, code=course_def["code"], user_id=DEMO_USER_ID)
            if existing:
                course_map[course_def["code"]] = existing.id
                stats["skipped"] += 1
            else:
                course_id = generate_id()
                course = Course(
                    id=course_id,
                    code=course_def["code"],
                    name=course_def["name"],
                    term=course_def["term"],
                    user_id=DEMO_USER_ID,
                )
                session.add(course)
                await session.flush()
                course_map[course_def["code"]] = course_id
                stats["courses"] += 1
                print(f"  Created course: {course_def['code']}")

        # ── Artifacts, Summaries, Flashcards, Quiz Questions ──
        artifact_ids: list[str] = []
        flashcard_ids: list[str] = []

        for course_def in COURSES:
            course_id = course_map[course_def["code"]]
            weeks = WEEKS[course_def["code"]]

            for week_num, title in weeks:
                fake_sha = hashlib.sha256(
                    f"demo:{course_def['code']}:week{week_num}".encode()
                ).hexdigest()

                # Artifact
                existing_art = await _get_or_none(session, LectureArtifact, sha256=fake_sha)
                if existing_art:
                    art_id = existing_art.id
                    stats["skipped"] += 1
                else:
                    art_id = generate_id()
                    filename = f"{course_def['code']}_Week{week_num}.pdf"
                    artifact = LectureArtifact(
                        id=art_id,
                        course_id=course_id,
                        week=week_num,
                        title=title,
                        original_filename=filename,
                        file_path=f"/app/data/uploads/{art_id}_{filename}",
                        file_type="pdf",
                        sha256=fake_sha,
                        file_size_bytes=50000 + week_num * 10000,
                        status="processed",
                        user_id=DEMO_USER_ID,
                        pipeline_started_at=now - timedelta(hours=1),
                        pipeline_completed_at=now,
                    )
                    session.add(artifact)
                    await session.flush()
                    stats["artifacts"] += 1
                artifact_ids.append(art_id)

                # Summary
                existing_sum = await _get_or_none(session, Summary, course_id=course_id, week=week_num)
                if not existing_sum:
                    content_md = _make_summary_md(course_def["code"], week_num, title)
                    summary = Summary(
                        id=generate_id(),
                        course_id=course_id,
                        week=week_num,
                        content_md=content_md,
                        file_path=f"/app/data/summaries/{course_def['code']}/{course_def['code']}_Week{week_num}.md",
                        version=1,
                        source_artifacts=[art_id],
                    )
                    session.add(summary)
                    stats["summaries"] += 1

                # Flashcards
                existing_fc = await _get_or_none(session, Flashcard, source_artifact_id=art_id)
                if not existing_fc:
                    for front_tpl, back_tpl, tags in FLASHCARD_TEMPLATES:
                        fc_id = generate_id()
                        fc = Flashcard(
                            id=fc_id,
                            course_id=course_id,
                            week=week_num,
                            front=front_tpl,
                            back=back_tpl.format(title=title),
                            tags=tags,
                            source_artifact_id=art_id,
                            source_page_ref=1,
                            generation_version=1,
                        )
                        session.add(fc)
                        flashcard_ids.append(fc_id)
                        stats["flashcards"] += 1

                # Quiz questions
                existing_qq = await _get_or_none(session, QuizQuestion, source_artifact_id=art_id)
                if not existing_qq:
                    for q_tpl in QUIZ_TEMPLATES:
                        qq = QuizQuestion(
                            id=generate_id(),
                            course_id=course_id,
                            week=week_num,
                            question_type=q_tpl["question_type"],
                            question=q_tpl["question"].format(title=title, course_code=course_def["code"]),
                            options_json=q_tpl["options"],
                            correct_answer=q_tpl["correct_answer"].format(title=title, course_code=course_def["code"]),
                            explanation=q_tpl["explanation"].format(title=title, course_code=course_def["code"]),
                            source_artifact_id=art_id,
                            source_page_ref=1,
                            generation_version=1,
                        )
                        session.add(qq)
                        stats["quiz_questions"] += 1

        await session.flush()

        # ── Flashcard Reviews (SM-2 progression for first ~30 cards) ──
        existing_review = await _get_or_none(session, FlashcardReview, user_id=DEMO_USER_ID)
        if not existing_review and flashcard_ids:
            review_cards = flashcard_ids[:30]
            for i, fc_id in enumerate(review_cards):
                # Simulate SM-2 progression: varying ease, interval, reps
                reps = min(i % 5 + 1, 5)
                ease = 2.5 + (i % 3) * 0.1 - (i % 2) * 0.2
                interval = [1, 3, 7, 14, 30][min(reps - 1, 4)]
                review = FlashcardReview(
                    id=generate_id(),
                    user_id=DEMO_USER_ID,
                    flashcard_id=fc_id,
                    ease_factor=round(ease, 2),
                    interval_days=interval,
                    repetition_count=reps,
                    next_review_at=now + timedelta(days=interval),
                    last_reviewed_at=now - timedelta(days=1),
                )
                session.add(review)
                stats["flashcard_reviews"] += 1

        # ── Study Sessions (5 sessions over 7 days) ──
        existing_ss = await _get_or_none(session, StudySession, user_id=DEMO_USER_ID)
        csit302_id = course_map.get("CSIT302")
        csit314_id = course_map.get("CSIT314")
        if not existing_ss and csit302_id and csit314_id:
            session_data = [
                (csit302_id, today - timedelta(days=6), 15, 5, 4, 1200),
                (csit302_id, today - timedelta(days=4), 20, 8, 6, 1800),
                (csit314_id, today - timedelta(days=3), 12, 6, 5, 900),
                (csit302_id, today - timedelta(days=1), 25, 10, 8, 2100),
                (csit314_id, today, 10, 4, 3, 600),
            ]
            for cid, sdate, cards, quiz_q, quiz_c, dur in session_data:
                ss = StudySession(
                    id=generate_id(),
                    user_id=DEMO_USER_ID,
                    course_id=cid,
                    session_date=sdate,
                    cards_reviewed=cards,
                    quiz_questions_answered=quiz_q,
                    quiz_correct=quiz_c,
                    duration_seconds=dur,
                )
                session.add(ss)
                stats["study_sessions"] += 1

        # ── Exam (1 active, 14 days from now) ──
        existing_exam = await _get_or_none(session, Exam, user_id=DEMO_USER_ID)
        if not existing_exam and csit302_id:
            exam = Exam(
                id=generate_id(),
                user_id=DEMO_USER_ID,
                course_id=csit302_id,
                title="CSIT302 Midterm",
                exam_date=now + timedelta(days=14),
                weeks_scope=[1, 2, 3, 4],
                target_mastery_pct=80,
                status="active",
            )
            session.add(exam)
            stats["exams"] += 1

        # ── UserXP (level 3, ~350 XP) ──
        existing_xp = await _get_or_none(session, UserXP, user_id=DEMO_USER_ID)
        if not existing_xp:
            user_xp = UserXP(
                id=generate_id(),
                user_id=DEMO_USER_ID,
                total_xp=350,
                level=3,
            )
            session.add(user_xp)
            stats["xp"] = 1

            # XP Events
            xp_events = [
                ("upload", 50, now - timedelta(days=6)),
                ("study_session", 30, now - timedelta(days=5)),
                ("study_session", 40, now - timedelta(days=4)),
                ("quiz_perfect", 80, now - timedelta(days=3)),
                ("study_session", 50, now - timedelta(days=2)),
                ("upload", 50, now - timedelta(days=1)),
                ("study_session", 50, now),
            ]
            for evt_type, xp_amt, created in xp_events:
                xpe = XPEvent(
                    id=generate_id(),
                    user_id=DEMO_USER_ID,
                    event_type=evt_type,
                    xp_amount=xp_amt,
                    created_at=created,
                )
                session.add(xpe)
                stats["xp_events"] += 1

        # ── Achievements (unlock 5 existing achievements) ──
        existing_ua = await _get_or_none(session, UserAchievement, user_id=DEMO_USER_ID)
        if not existing_ua:
            # Get first 5 achievements from the DB (seeded by seed_achievements.py)
            result = await session.execute(select(Achievement.id).limit(5))
            achievement_ids = [row[0] for row in result.all()]
            for ach_id in achievement_ids:
                ua = UserAchievement(
                    id=generate_id(),
                    user_id=DEMO_USER_ID,
                    achievement_id=ach_id,
                    earned_at=now - timedelta(days=2),
                    notified=True,
                )
                session.add(ua)
                stats["achievements"] += 1

        # ── Chat Session (1 session, 4 messages) ──
        existing_chat = await _get_or_none(session, ChatSession, user_id=DEMO_USER_ID)
        if not existing_chat and csit302_id:
            chat_session_id = generate_id()
            chat = ChatSession(
                id=chat_session_id,
                user_id=DEMO_USER_ID,
                course_id=csit302_id,
                title="Network Security Questions",
                message_count=4,
            )
            session.add(chat)
            stats["chat_sessions"] = 1

            messages = [
                ("user", "What are the main types of firewalls?"),
                ("assistant", "There are three main types of firewalls:\n\n1. **Packet filtering** — examines individual packets and allows or blocks them based on source/destination IP and port.\n2. **Stateful inspection** — tracks active connections and makes decisions based on connection state.\n3. **Application layer (proxy)** — inspects traffic at the application level for deeper analysis."),
                ("user", "How does stateful inspection differ from packet filtering?"),
                ("assistant", "The key difference is that stateful inspection tracks the **state of network connections**, while packet filtering evaluates each packet independently.\n\nStateful firewalls maintain a state table of active connections, so they can identify whether a packet is part of an established connection. This provides better security since it can detect out-of-context packets that packet filtering would miss."),
            ]
            for i, (role, content) in enumerate(messages):
                msg = ChatMessage(
                    id=generate_id(),
                    session_id=chat_session_id,
                    role=role,
                    content=content,
                    token_count=len(content.split()) * 2,  # rough estimate
                    created_at=now - timedelta(minutes=30 - i * 5),
                )
                session.add(msg)
                stats["chat_messages"] += 1

        # ── Analytics Snapshots (7 days) ──
        existing_snap = await _get_or_none(session, AnalyticsSnapshot, user_id=DEMO_USER_ID)
        if not existing_snap:
            for day_offset in range(7):
                snap_date = today - timedelta(days=6 - day_offset)
                snap = AnalyticsSnapshot(
                    id=generate_id(),
                    user_id=DEMO_USER_ID,
                    snapshot_date=snap_date,
                    metrics_json={
                        "cards_reviewed": 10 + day_offset * 3,
                        "quiz_accuracy": round(0.6 + day_offset * 0.04, 2),
                        "study_minutes": 15 + day_offset * 5,
                        "xp_earned": 30 + day_offset * 10,
                    },
                )
                session.add(snap)
                stats["analytics_snapshots"] += 1

        # ── Course Document (1 syllabus) ──
        existing_doc = await _get_or_none(session, CourseDocument, user_id=DEMO_USER_ID)
        if not existing_doc and csit302_id:
            doc_sha = hashlib.sha256(b"demo:coursedoc:syllabus").hexdigest()
            doc = CourseDocument(
                id=generate_id(),
                user_id=DEMO_USER_ID,
                course_id=csit302_id,
                document_type="syllabus",
                title="CSIT302 Course Syllabus",
                original_filename="CSIT302_Syllabus.pdf",
                file_path="/app/data/uploads/demo_syllabus.pdf",
                file_type="pdf",
                sha256=doc_sha,
                file_size_bytes=125000,
                status="processed",
                extracted_text="CSIT302 Cybersecurity\nSemester 1 2025\nAssessments: Midterm 30%, Final 40%, Labs 30%",
            )
            session.add(doc)
            stats["course_documents"] += 1

        # ── Review Items (1 pending, 1 resolved) ──
        existing_ri = await _get_or_none(session, ReviewItem, entity_type="lecture_artifact")
        if not existing_ri and artifact_ids:
            ri_pending = ReviewItem(
                id=generate_id(),
                review_type="classification",
                entity_type="lecture_artifact",
                entity_id=artifact_ids[0],
                payload_json={
                    "original_filename": "UnknownLecture.pdf",
                    "text_preview": "This lecture covers advanced cryptography topics...",
                },
                suggested_values={
                    "course_code": "CSIT302",
                    "week": 5,
                    "title": "Advanced Cryptography",
                    "confidence": 0.42,
                },
                status="pending",
            )
            session.add(ri_pending)
            stats["review_items"] += 1

            ri_resolved = ReviewItem(
                id=generate_id(),
                review_type="classification",
                entity_type="lecture_artifact",
                entity_id=artifact_ids[1] if len(artifact_ids) > 1 else artifact_ids[0],
                payload_json={
                    "original_filename": "Lecture_Extra.pptx",
                    "text_preview": "Software architecture patterns...",
                },
                suggested_values={
                    "course_code": "CSIT314",
                    "week": 4,
                    "title": "Architecture Patterns",
                    "confidence": 0.38,
                },
                status="resolved",
                resolution_json={
                    "action": "accept",
                    "resolved_by": DEMO_USER_ID,
                },
            )
            session.add(ri_resolved)
            stats["review_items"] += 1

        await session.commit()

    # ── Report ──
    print("\n=== Demo Seed Report ===")
    for key, val in stats.items():
        if val > 0:
            print(f"  {key}: {val}")
    if stats["skipped"] > 0:
        print(f"  skipped (existing): {stats['skipped']}")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
