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

Both are idempotent. `course` seeds for the owner a self-hosted API resolves
requests to (the default admin, created here if no API request has made it yet).
"""

import argparse
import os
import sys
from datetime import UTC, datetime
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
from app.models.concept import Concept  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.models.user import User  # noqa: E402


def _owner(session: Session) -> User:
    """The user a self-hosted API attributes unauthenticated requests to."""
    user = session.get(User, DEFAULT_ADMIN_ID)
    if user is None:
        user = session.execute(select(User).where(User.role == "admin").limit(1)).scalar_one_or_none()
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
            select(Concept.name).where(Concept.course_id == course.id, Concept.user_id == owner.id)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("course")
    c.add_argument("code")
    c.add_argument("--concepts", type=int, default=0)
    a = sub.add_parser("admin")
    a.add_argument("email")
    a.add_argument("password")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL_SYNC") or settings.database_url_sync
    engine = create_engine(url)
    with Session(engine) as session:
        if args.cmd == "course":
            seed_course(session, args.code, args.concepts)
        else:
            seed_admin(session, args.email, args.password)
        session.commit()


if __name__ == "__main__":
    main()
