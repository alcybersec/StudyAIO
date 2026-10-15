"""Seed rows the public API cannot create, for the Playwright suite.

Why a script and not the API: a Course exists only as a side effect of the
classify stage, which needs a Celery worker and an AI backend; the e2e-tests CI
job runs neither (the suite asserts uploads are *queued*, never processed). A
Concept likewise comes only from the AI concept-extraction task. Admin is a
role, and the only API that grants it needs an admin already (the default admin
a self-hosted stack serves has no password to log in with). So the specs that
need those rows seed them here, directly, through the app's own models.

Run from services/ui (Playwright's cwd) with DATABASE_URL_SYNC exported -- the
e2e-tests job already exports it.

    python3 e2e/seed_e2e.py course CODE [--concepts N]
    python3 e2e/seed_e2e.py admin EMAIL PASSWORD
    python3 e2e/seed_e2e.py user EMAIL PASSWORD
    python3 e2e/seed_e2e.py weakspots CODE
    python3 e2e/seed_e2e.py studyitems CODE

Both are idempotent. `course` seeds for the owner a self-hosted API resolves
requests to (the default admin, created here if no API request has made it yet).
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
sys.path.insert(0, str(APP_DIR))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  (registers every mapper)
from app.api.deps import (  # noqa: E402
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_ID,
    DEFAULT_ADMIN_USERNAME,
)
from app.config import settings
from app.core.auth import hash_password  # noqa: E402
from app.models.artifact import LectureArtifact  # noqa: E402
from app.models.concept import Concept  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.models.exam import Exam  # noqa: E402
from app.models.flashcard import Flashcard  # noqa: E402
from app.models.flashcard_review import FlashcardReview  # noqa: E402
from app.models.quiz import QuizQuestion  # noqa: E402
from app.models.quiz_attempt import QuizAttempt  # noqa: E402
from app.models.user import User  # noqa: E402


def _owner(session: Session) -> User:
    """The user a self-hosted API attributes unauthenticated requests to."""
    user = session.get(User, DEFAULT_ADMIN_ID)
    if user is None:
        user = session.execute(
            select(User).where(User.role == "admin").limit(1)
        ).scalar_one_or_none()
    if user is None:
        user = User(
            id=DEFAULT_ADMIN_ID,
            email=DEFAULT_ADMIN_EMAIL,
            username=DEFAULT_ADMIN_USERNAME,
            role="admin",
            tier="pro",
            is_active=True,
            email_verified=True,
            ai_processing_consent_at=datetime.now(UTC),
            ai_processing_consent_version=1,
        )
        session.add(user)
        session.flush()
    return user


def seed_course(session: Session, code: str, concepts: int) -> None:
    owner = _owner(session)
    course = session.execute(
        select(Course).where(Course.code == code, Course.user_id == owner.id)
    ).scalar_one_or_none()
    if course is None:
        course = Course(code=code, name=f"{code} (e2e)", user_id=owner.id)
        session.add(course)
        session.flush()
    have = {
        n
        for (n,) in session.execute(
            select(Concept.name).where(
                Concept.course_id == course.id, Concept.user_id == owner.id
            )
        )
    }
    for i in range(1, concepts + 1):
        name = f"E2E concept {i}"
        if name not in have:
            session.add(
                Concept(
                    user_id=owner.id,
                    course_id=course.id,
                    name=name,
                    description=f"Seeded concept {i} for keyboard-navigation e2e.",
                    category="general",
                    source_weeks=[1],
                    mention_count=1,
                )
            )


# Weeks the weak-spot spec reads: (week, questions, attempts as correct/incorrect).
# Week 1 is weak, 2 solid, 3 has questions but too few answers to judge (unknown).
WEAKSPOT_WEEKS = ((1, 5, [False] * 5), (2, 5, [True] * 5), (3, 3, [False, False]))


def seed_weakspots(session: Session, code: str) -> None:
    """A course with a weak, a solid and an unknown week, due cards and an exam.

    The weak-spot engine derives everything from quiz attempts, card reviews and
    exams; none of them can be created without answering through the UI, and
    the study-tonight plan is frozen on its first read of the day. Idempotent:
    a course that already has questions is left as it is.
    """
    owner = _owner(session)
    course = session.execute(
        select(Course).where(Course.code == code, Course.user_id == owner.id)
    ).scalar_one_or_none()
    if course is None:
        course = Course(code=code, name=f"{code} (e2e)", user_id=owner.id)
        session.add(course)
        session.flush()
    if session.execute(
        select(QuizQuestion.id).where(QuizQuestion.course_id == course.id).limit(1)
    ).first():
        return
    now = datetime.now(UTC)
    first_artifact = None
    for week, n_questions, outcomes in WEAKSPOT_WEEKS:
        artifact = LectureArtifact(
            user_id=owner.id,
            course_id=course.id,
            week=week,
            title=f"{code} week {week}",
            original_filename=f"{code}-w{week}.pdf",
            file_path=f"uploads/e2e-{code}-w{week}.pdf",
            file_type="pdf",
            sha256=f"{code}{week}".encode().hex().ljust(64, "0")[:64],
            file_size_bytes=1,
            status="processed",
        )
        session.add(artifact)
        session.flush()
        first_artifact = first_artifact or artifact
        questions = []
        for i in range(n_questions):
            q = QuizQuestion(
                course_id=course.id,
                week=week,
                question_type="short_answer",
                question=f"{code} w{week} question {i}?",
                correct_answer="an answer",
                explanation="because",
                source_artifact_id=artifact.id,
                source_page_ref=1,
            )
            session.add(q)
            questions.append(q)
        session.flush()
        for q, ok in zip(questions, outcomes):
            session.add(
                QuizAttempt(quiz_question_id=q.id, selected_answer="x", is_correct=ok)
            )
    for i in range(3):
        card = Flashcard(
            course_id=course.id,
            week=1,
            front=f"{code} card {i}?",
            back="an answer",
            tags=[],
            source_artifact_id=first_artifact.id,
            source_page_ref=1,
        )
        session.add(card)
        session.flush()
        session.add(
            FlashcardReview(
                user_id=owner.id,
                flashcard_id=card.id,
                ease_factor=1.3,
                interval_days=1,
                repetition_count=0,
                next_review_at=now - timedelta(days=2),
                last_reviewed_at=now - timedelta(days=3),
            )
        )
    session.add(
        Exam(
            user_id=owner.id,
            course_id=course.id,
            title=f"{code} midterm",
            exam_date=now + timedelta(days=5),
            weeks_scope=[1, 2, 3],
        )
    )


def seed_studyitems(session: Session, code: str) -> None:
    """A course with one lecture in week 1 holding two cards and a question.

    Week 2 deliberately has no lecture, so adding an item there is refused with
    409 `no_source_artifact`. Pipeline-origin rows, so "Yours" only appears once
    a spec edits or adds. Idempotent: a course that already has cards is kept.
    """
    owner = _owner(session)
    course = session.execute(
        select(Course).where(Course.code == code, Course.user_id == owner.id)
    ).scalar_one_or_none()
    if course is None:
        course = Course(code=code, name=f"{code} (e2e)", user_id=owner.id)
        session.add(course)
        session.flush()
    if session.execute(
        select(Flashcard.id).where(Flashcard.course_id == course.id).limit(1)
    ).first():
        return
    artifact = LectureArtifact(
        user_id=owner.id,
        course_id=course.id,
        week=1,
        title=f"{code} week 1",
        original_filename=f"{code}-w1.pdf",
        file_path=f"uploads/e2e-{code}-w1.pdf",
        file_type="pdf",
        sha256=f"items{code}".encode().hex().ljust(64, "0")[:64],
        file_size_bytes=1,
        status="processed",
    )
    session.add(artifact)
    session.flush()
    for i, (front, back) in enumerate(
        (("Seed front one", "Seed back one"), ("Seed front two", "Seed back two"))
    ):
        session.add(
            Flashcard(
                course_id=course.id,
                week=1,
                front=front,
                back=back,
                tags=[],
                source_artifact_id=artifact.id,
                source_page_ref=i + 1,
            )
        )
    session.add(
        QuizQuestion(
            course_id=course.id,
            week=1,
            question_type="multiple_choice",
            question="Seed which letter is second?",
            options_json=["A. Alpha", "B. Beta", "C. Gamma"],
            correct_answer="B",
            explanation="Beta is second.",
            source_artifact_id=artifact.id,
            source_page_ref=1,
        )
    )


def seed_admin(session: Session, email: str, password: str) -> None:
    """Create (or reset the password of) an admin who can actually log in."""
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, username=email.split("@")[0])
        session.add(user)
    user.hashed_password = hash_password(password)
    user.role = "admin"
    user.tier = "pro"
    user.is_active = True
    user.email_verified = True
    # AI-spending routes answer 403 until consent is recorded (GL#38).
    user.ai_processing_consent_at = datetime.now(UTC)
    user.ai_processing_consent_version = 1


def seed_user(session: Session, email: str, password: str) -> None:
    """Create (or reset) an ordinary, consented user who can log in.

    Specs use this instead of POST /api/auth/register: registration is limited
    to 3/minute per client, a budget the auth spec needs for itself.
    """
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, username=email.split("@")[0])
        session.add(user)
    user.hashed_password = hash_password(password)
    user.role = "user"
    user.is_active = True
    user.email_verified = True
    user.ai_processing_consent_at = datetime.now(UTC)
    user.ai_processing_consent_version = 1


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("course")
    c.add_argument("code")
    c.add_argument("--concepts", type=int, default=0)
    si = sub.add_parser("studyitems")
    si.add_argument("code")
    w = sub.add_parser("weakspots")
    w.add_argument("code")
    a = sub.add_parser("admin")
    a.add_argument("email")
    a.add_argument("password")
    u = sub.add_parser("user")
    u.add_argument("email")
    u.add_argument("password")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL_SYNC") or settings.database_url_sync
    engine = create_engine(url)
    with Session(engine) as session:
        if args.cmd == "course":
            seed_course(session, args.code, args.concepts)
        elif args.cmd == "studyitems":
            seed_studyitems(session, args.code)
        elif args.cmd == "weakspots":
            seed_weakspots(session, args.code)
        elif args.cmd == "user":
            seed_user(session, args.email, args.password)
        else:
            seed_admin(session, args.email, args.password)
        session.commit()


if __name__ == "__main__":
    main()
