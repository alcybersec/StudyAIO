#!/usr/bin/env python3
"""Import v0 lecture files and summaries into StudyAIO database.

Scans lecture_manager/raw_lectures/ and lecture_manager/lectures_summary/
directories, creates Course, LectureArtifact, and Summary records.

Idempotent: safe to run multiple times. Uses SHA-256 dedup for artifacts
and (course_id, week) uniqueness for summaries.

Usage:
    DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
    python scripts/import_v0.py
"""

import asyncio
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add services/app to path so we can import the app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import models after path setup
from app.core.database import Base
from app.core.utils import generate_id, compute_sha256
from app.models.course import Course
from app.models.artifact import LectureArtifact
from app.models.summary import Summary


# ── Config ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
RAW_LECTURES_DIR = PROJECT_ROOT / "lecture_manager" / "raw_lectures"
SUMMARIES_DIR = PROJECT_ROOT / "lecture_manager" / "lectures_summary"
DATA_UPLOADS = PROJECT_ROOT / "data" / "uploads"
DATA_SUMMARIES = PROJECT_ROOT / "data" / "summaries"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio",
)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
FILENAME_PATTERN = re.compile(
    r"^([A-Z]{2,6}\d{2,4})_Week(\d+)(?:_v\d+)?\.(\w+)$"
)


# ── Helpers ─────────────────────────────────────────────────────────

async def get_or_create_course(session: AsyncSession, code: str) -> Course:
    """Get existing course or create a new one."""
    result = await session.execute(select(Course).where(Course.code == code))
    course = result.scalar_one_or_none()
    if course:
        return course

    course = Course(id=generate_id(), code=code)
    session.add(course)
    await session.flush()
    return course


async def artifact_exists(session: AsyncSession, sha256: str) -> bool:
    """Check if an artifact with this hash already exists."""
    result = await session.execute(
        select(LectureArtifact.id).where(LectureArtifact.sha256 == sha256)
    )
    return result.scalar_one_or_none() is not None


async def summary_exists(session: AsyncSession, course_id: str, week: int) -> bool:
    """Check if a summary for this course+week already exists."""
    result = await session.execute(
        select(Summary.id).where(
            Summary.course_id == course_id,
            Summary.week == week,
        )
    )
    return result.scalar_one_or_none() is not None


# ── Main import logic ───────────────────────────────────────────────

async def import_v0():
    """Run the full v0 import."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Ensure output directories exist
    DATA_UPLOADS.mkdir(parents=True, exist_ok=True)
    DATA_SUMMARIES.mkdir(parents=True, exist_ok=True)

    stats = {
        "courses_created": 0,
        "courses_existing": 0,
        "artifacts_imported": 0,
        "artifacts_skipped_dup": 0,
        "artifacts_skipped_missing": 0,
        "artifacts_skipped_bad_name": 0,
        "summaries_imported": 0,
        "summaries_skipped": 0,
    }

    async with session_factory() as session:
        # ── Phase 1: Import lecture artifacts ───────────────────
        print("\n=== Phase 1: Import lecture artifacts ===")

        if not RAW_LECTURES_DIR.exists():
            print(f"  WARNING: {RAW_LECTURES_DIR} does not exist, skipping artifacts")
        else:
            for course_dir in sorted(RAW_LECTURES_DIR.iterdir()):
                if not course_dir.is_dir():
                    continue

                course_code = course_dir.name
                course = await get_or_create_course(session, course_code)

                # Check if this was a new creation
                if session.new and course in session.new:
                    stats["courses_created"] += 1
                    print(f"  Created course: {course_code}")
                else:
                    stats["courses_existing"] += 1

                for file_path in sorted(course_dir.iterdir()):
                    if not file_path.is_file():
                        continue
                    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                        continue

                    # Parse filename
                    match = FILENAME_PATTERN.match(file_path.name)
                    if not match:
                        print(f"  SKIP (bad name): {file_path.name}")
                        stats["artifacts_skipped_bad_name"] += 1
                        continue

                    _, week_str, ext = match.groups()
                    week = int(week_str)

                    # Check if file exists (binaries may be gitignored)
                    if not file_path.exists() or file_path.stat().st_size == 0:
                        print(f"  SKIP (missing/empty): {file_path.name}")
                        stats["artifacts_skipped_missing"] += 1
                        continue

                    # Compute hash and check for duplicate
                    sha256 = compute_sha256(file_path)
                    if await artifact_exists(session, sha256):
                        print(f"  SKIP (duplicate): {file_path.name}")
                        stats["artifacts_skipped_dup"] += 1
                        continue

                    # Copy to data/uploads/
                    artifact_id = generate_id()
                    dest_filename = f"{artifact_id}_{file_path.name}"
                    dest_path = DATA_UPLOADS / dest_filename
                    shutil.copy2(str(file_path), str(dest_path))

                    # Create artifact record
                    artifact = LectureArtifact(
                        id=artifact_id,
                        course_id=course.id,
                        week=week,
                        title=f"{course_code} Week {week}",
                        original_filename=file_path.name,
                        file_path=str(dest_path),
                        file_type=ext.lower(),
                        sha256=sha256,
                        file_size_bytes=dest_path.stat().st_size,
                        status="classified",  # Already classified by filename
                        pipeline_started_at=datetime.utcnow(),
                    )
                    session.add(artifact)
                    stats["artifacts_imported"] += 1
                    print(f"  Imported: {file_path.name} -> {course_code} Week {week}")

            await session.commit()

        # ── Phase 2: Import summaries ──────────────────────────
        print("\n=== Phase 2: Import summaries ===")

        if not SUMMARIES_DIR.exists():
            print(f"  WARNING: {SUMMARIES_DIR} does not exist, skipping summaries")
        else:
            for course_dir in sorted(SUMMARIES_DIR.iterdir()):
                if not course_dir.is_dir():
                    continue

                course_code = course_dir.name
                course = await get_or_create_course(session, course_code)

                for md_file in sorted(course_dir.iterdir()):
                    if not md_file.is_file() or md_file.suffix != ".md":
                        continue

                    # Parse week from filename: CSIT302_Week5.md
                    week_match = re.search(r"Week(\d+)", md_file.name)
                    if not week_match:
                        print(f"  SKIP (bad name): {md_file.name}")
                        continue

                    week = int(week_match.group(1))

                    # Check for existing summary
                    if await summary_exists(session, course.id, week):
                        print(f"  SKIP (exists): {md_file.name}")
                        stats["summaries_skipped"] += 1
                        continue

                    # Read content
                    content_md = md_file.read_text(encoding="utf-8")

                    # Copy to data/summaries/<course>/
                    dest_dir = DATA_SUMMARIES / course_code
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / md_file.name
                    shutil.copy2(str(md_file), str(dest_path))

                    # Create summary record
                    summary = Summary(
                        id=generate_id(),
                        course_id=course.id,
                        week=week,
                        content_md=content_md,
                        file_path=str(dest_path),
                        version=1,
                        source_artifacts=[],  # No specific artifact linkage for v0
                    )
                    session.add(summary)
                    stats["summaries_imported"] += 1
                    print(f"  Imported: {md_file.name}")

            await session.commit()

    # ── Report ──────────────────────────────────────────────────
    print("\n=== Import Report ===")
    print(f"  Courses created:            {stats['courses_created']}")
    print(f"  Courses already existed:    {stats['courses_existing']}")
    print(f"  Artifacts imported:         {stats['artifacts_imported']}")
    print(f"  Artifacts skipped (dup):    {stats['artifacts_skipped_dup']}")
    print(f"  Artifacts skipped (missing):{stats['artifacts_skipped_missing']}")
    print(f"  Artifacts skipped (name):   {stats['artifacts_skipped_bad_name']}")
    print(f"  Summaries imported:         {stats['summaries_imported']}")
    print(f"  Summaries skipped:          {stats['summaries_skipped']}")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_v0())
