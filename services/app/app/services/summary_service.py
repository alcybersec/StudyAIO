"""Business logic for Summary management."""

from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.agents.base import ExtractionData
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.extraction import Extraction
from app.models.summary import Summary

logger = structlog.get_logger()


async def get_week_extractions(
    session: AsyncSession, course_id: str, week: int
) -> list[Extraction]:
    """Get all extractions for a course+week.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.

    Returns:
        List of Extraction records for the week.
    """
    result = await session.execute(
        select(Extraction)
        .join(LectureArtifact, Extraction.artifact_id == LectureArtifact.id)
        .where(
            LectureArtifact.course_id == course_id,
            LectureArtifact.week == week,
        )
    )
    return list(result.scalars().all())


def merge_extractions(extractions: list[Extraction]) -> ExtractionData:
    """Merge multiple extractions into a single ExtractionData.

    Concatenates all pages from each extraction's manifest_json.

    Args:
        extractions: List of Extraction records.

    Returns:
        Merged ExtractionData with all pages and combined metadata.
    """
    all_pages: list[dict] = []
    artifact_ids: list[str] = []

    for extraction in extractions:
        manifest = extraction.manifest_json
        pages = manifest.get("pages", [])
        all_pages.extend(pages)
        artifact_ids.append(extraction.artifact_id)

    return ExtractionData(
        pages=all_pages,
        metadata={
            "artifact_ids": artifact_ids,
            "extraction_count": len(extractions),
        },
    )


async def get_existing_summary(
    session: AsyncSession, course_id: str, week: int
) -> Summary | None:
    """Get existing summary for a course+week if it exists.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.

    Returns:
        Existing Summary or None.
    """
    result = await session.execute(
        select(Summary).where(
            Summary.course_id == course_id,
            Summary.week == week,
        )
    )
    return result.scalar_one_or_none()


async def create_or_update_summary(
    session: AsyncSession,
    course_id: str,
    week: int,
    content_md: str,
    file_path: str,
    source_artifact_ids: list[str],
) -> Summary:
    """Create a new summary or update an existing one.

    If a summary already exists for the course+week, increments version
    and updates content. Otherwise creates a new one.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        content_md: Generated markdown content.
        file_path: Path where the markdown file is saved.
        source_artifact_ids: List of artifact IDs that contributed.

    Returns:
        The created or updated Summary.
    """
    existing = await get_existing_summary(session, course_id, week)

    if existing:
        # Merge source artifact IDs (avoid duplicates)
        current_sources = existing.source_artifacts or []
        merged_sources = list(set(current_sources + source_artifact_ids))

        existing.content_md = content_md
        existing.file_path = file_path
        existing.version = existing.version + 1
        existing.source_artifacts = merged_sources
        existing.updated_at = datetime.utcnow()

        await session.flush()
        logger.info(
            "summary_updated",
            course_id=course_id,
            week=week,
            version=existing.version,
        )
        return existing

    summary = Summary(
        id=generate_id(),
        course_id=course_id,
        week=week,
        content_md=content_md,
        file_path=file_path,
        version=1,
        source_artifacts=source_artifact_ids,
    )
    session.add(summary)
    await session.flush()

    logger.info(
        "summary_created",
        summary_id=summary.id,
        course_id=course_id,
        week=week,
    )
    return summary


def build_summary_file_path(summaries_dir: str, course_code: str, week: int) -> Path:
    """Build the file path for a summary markdown file.

    Args:
        summaries_dir: Base directory for summaries.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.

    Returns:
        Path like <summaries_dir>/<course_code>/<course_code>_Week<N>.md
    """
    course_dir = Path(summaries_dir) / course_code
    course_dir.mkdir(parents=True, exist_ok=True)
    return course_dir / f"{course_code}_Week{week}.md"
