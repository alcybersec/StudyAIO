"""CourseOps service — upload, extract, and manage course documents, assessments, and deadlines."""

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.agents.base import CourseOpsResult
from app.core.exceptions import CourseOpsError
from app.core.utils import generate_id
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.deadline import Deadline
from app.models.exam import Exam

logger = structlog.get_logger()


async def upload_course_document(
    session: AsyncSession,
    course_code: str,
    document_type: str,
    original_filename: str,
    file_path: str,
    file_type: str,
    sha256: str,
    file_size_bytes: int,
    user_id: str | None = None,
) -> CourseDocument:
    """Upload a course document with SHA-256 dedup.

    Args:
        session: Database session.
        course_code: Course code to associate with.
        document_type: Type of document (outline, rubric, handbook, other).
        original_filename: Original filename.
        file_path: Stored file path.
        file_type: File extension (pdf, docx).
        sha256: SHA-256 hash of the file.
        file_size_bytes: File size in bytes.

    Returns:
        The created CourseDocument.

    Raises:
        CourseOpsError: If course not found or document is a duplicate.
    """
    # Look up course
    query = select(Course).where(Course.code == course_code)
    if user_id:
        query = query.where(Course.user_id == user_id)
    result = await session.execute(query)
    course = result.scalar_one_or_none()
    if not course:
        raise CourseOpsError(f"Course {course_code} not found")

    # Check for duplicate
    existing = await session.execute(
        select(CourseDocument).where(
            CourseDocument.course_id == course.id,
            CourseDocument.sha256 == sha256,
        )
    )
    if existing.scalar_one_or_none():
        raise CourseOpsError(
            f"Document with SHA-256 {sha256[:16]}... already uploaded for {course_code}"
        )

    doc = CourseDocument(
        id=generate_id(),
        user_id=user_id or course.user_id,
        course_id=course.id,
        document_type=document_type,
        title=original_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_type,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    logger.info(
        "course_document_uploaded",
        document_id=doc.id,
        course_code=course_code,
        document_type=document_type,
        filename=original_filename,
    )
    return doc


async def process_course_document(
    session: AsyncSession,
    document_id: str,
    extracted_text: str,
    ai_result: CourseOpsResult,
) -> dict:
    """Persist AI-extracted assessments and deadlines for a course document.

    Args:
        session: Database session.
        document_id: UUID of the course document.
        extracted_text: Raw text extracted from the document.
        ai_result: CourseOpsResult from the AI agent.

    Returns:
        Dict with counts of created assessments and deadlines.

    Raises:
        CourseOpsError: If document not found.
    """
    doc = await session.get(CourseDocument, document_id)
    if not doc:
        raise CourseOpsError(f"CourseDocument {document_id} not found")

    doc.extracted_text = extracted_text
    doc.status = "processed"

    # Update course info if available
    course = await session.get(Course, doc.course_id)
    if course and ai_result.course_info:
        if not course.name and ai_result.course_info.get("course_name"):
            course.name = ai_result.course_info["course_name"]
        if not course.term and ai_result.course_info.get("term"):
            course.term = ai_result.course_info["term"]

    # Create assessments
    assessment_count = 0
    assessment_map: dict[str, str] = {}  # title -> assessment_id for linking deadlines
    for a_data in ai_result.assessments:
        assessment = Assessment(
            id=generate_id(),
            course_id=doc.course_id,
            source_document_id=document_id,
            title=a_data.title,
            assessment_type=a_data.assessment_type,
            weight_pct=a_data.weight_pct,
            description=a_data.description,
            weeks_relevant=a_data.weeks_relevant if a_data.weeks_relevant else None,
        )
        session.add(assessment)
        assessment_map[a_data.title.lower()] = assessment.id
        assessment_count += 1

    # Create deadlines
    deadline_count = 0
    for d_data in ai_result.deadlines:
        if not d_data.due_date:
            continue
        try:
            due_date = date.fromisoformat(d_data.due_date)
        except ValueError:
            logger.warning("invalid_deadline_date", date_str=d_data.due_date, title=d_data.title)
            continue

        # Try to link to an assessment by matching title
        assessment_id = None
        for a_title, a_id in assessment_map.items():
            if a_title in d_data.title.lower() or d_data.title.lower() in a_title:
                assessment_id = a_id
                break

        deadline = Deadline(
            id=generate_id(),
            course_id=doc.course_id,
            assessment_id=assessment_id,
            source_document_id=document_id,
            title=d_data.title,
            due_date=due_date,
            deadline_type=d_data.deadline_type,
            description=d_data.description,
            is_confirmed=False,
        )
        session.add(deadline)
        deadline_count += 1

    await session.commit()

    logger.info(
        "course_document_processed",
        document_id=document_id,
        assessments=assessment_count,
        deadlines=deadline_count,
        confidence=ai_result.confidence,
    )

    return {
        "document_id": document_id,
        "assessment_count": assessment_count,
        "deadline_count": deadline_count,
        "confidence": ai_result.confidence,
    }


async def list_course_documents(
    session: AsyncSession,
    course_code: str,
    user_id: str | None = None,
) -> list[CourseDocument]:
    """List all course documents for a course.

    Args:
        session: Database session.
        course_code: Course code.

    Returns:
        List of CourseDocument objects.
    """
    query = select(Course).where(Course.code == course_code)
    if user_id:
        query = query.where(Course.user_id == user_id)
    result = await session.execute(query)
    course = result.scalar_one_or_none()
    if not course:
        return []

    docs_result = await session.execute(
        select(CourseDocument)
        .where(CourseDocument.course_id == course.id)
        .order_by(CourseDocument.created_at.desc())
    )
    return list(docs_result.scalars().all())


async def get_course_document(
    session: AsyncSession,
    document_id: str,
) -> CourseDocument | None:
    """Get a single course document by ID.

    Args:
        session: Database session.
        document_id: UUID of the document.

    Returns:
        CourseDocument or None.
    """
    result = await session.execute(
        select(CourseDocument)
        .options(
            joinedload(CourseDocument.assessments),
            joinedload(CourseDocument.deadlines),
        )
        .where(CourseDocument.id == document_id)
    )
    return result.unique().scalar_one_or_none()


async def list_assessments(
    session: AsyncSession,
    course_code: str,
) -> list[Assessment]:
    """List all assessments for a course.

    Args:
        session: Database session.
        course_code: Course code.

    Returns:
        List of Assessment objects.
    """
    result = await session.execute(select(Course).where(Course.code == course_code))
    course = result.scalar_one_or_none()
    if not course:
        return []

    assessments_result = await session.execute(
        select(Assessment)
        .where(Assessment.course_id == course.id)
        .order_by(Assessment.assessment_type, Assessment.title)
    )
    return list(assessments_result.scalars().all())


async def list_deadlines(
    session: AsyncSession,
    course_code: str,
    upcoming_only: bool = False,
) -> list[Deadline]:
    """List deadlines for a course.

    Args:
        session: Database session.
        course_code: Course code.
        upcoming_only: If True, only return future deadlines.

    Returns:
        List of Deadline objects.
    """
    result = await session.execute(select(Course).where(Course.code == course_code))
    course = result.scalar_one_or_none()
    if not course:
        return []

    query = select(Deadline).where(Deadline.course_id == course.id)
    if upcoming_only:
        query = query.where(Deadline.due_date >= date.today())
    query = query.order_by(Deadline.due_date)

    deadlines_result = await session.execute(query)
    return list(deadlines_result.scalars().all())


async def update_deadline(
    session: AsyncSession,
    deadline_id: str,
    title: str | None = None,
    due_date: date | None = None,
    deadline_type: str | None = None,
    description: str | None = None,
    is_confirmed: bool | None = None,
) -> Deadline | None:
    """Update a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.
        title: New title (optional).
        due_date: New due date (optional).
        deadline_type: New type (optional).
        description: New description (optional).
        is_confirmed: New confirmed status (optional).

    Returns:
        Updated Deadline or None if not found.
    """
    deadline = await session.get(Deadline, deadline_id)
    if not deadline:
        return None

    if title is not None:
        deadline.title = title
    if due_date is not None:
        deadline.due_date = due_date
    if deadline_type is not None:
        deadline.deadline_type = deadline_type
    if description is not None:
        deadline.description = description
    if is_confirmed is not None:
        deadline.is_confirmed = is_confirmed

    deadline.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(deadline)
    return deadline


async def delete_deadline(
    session: AsyncSession,
    deadline_id: str,
) -> bool:
    """Delete a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.

    Returns:
        True if deleted, False if not found.
    """
    deadline = await session.get(Deadline, deadline_id)
    if not deadline:
        return False

    await session.delete(deadline)
    await session.commit()
    return True


async def create_exam_from_deadline(
    session: AsyncSession,
    deadline_id: str,
    user_id: str | None = None,
) -> Exam | None:
    """Create an Exam from a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.

    Returns:
        Created Exam or None if deadline not found.

    Raises:
        CourseOpsError: If deadline type is not exam-compatible.
    """
    deadline = await session.get(Deadline, deadline_id)
    if not deadline:
        return None

    # Determine weeks_scope from linked assessment
    weeks_scope: list[int] = []
    if deadline.assessment_id:
        assessment = await session.get(Assessment, deadline.assessment_id)
        if assessment and assessment.weeks_relevant:
            weeks_scope = assessment.weeks_relevant

    due_datetime = datetime.combine(deadline.due_date, datetime.min.time())

    # Resolve user_id from deadline's course if not provided
    if not user_id:
        course = await session.get(Course, deadline.course_id)
        user_id = course.user_id if course else ""

    exam = Exam(
        id=generate_id(),
        user_id=user_id,
        course_id=deadline.course_id,
        title=deadline.title,
        exam_date=due_datetime,
        weeks_scope=weeks_scope or [1],
        status="active",
    )
    session.add(exam)

    # Mark deadline as confirmed
    deadline.is_confirmed = True
    deadline.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(exam)

    logger.info(
        "exam_created_from_deadline",
        exam_id=exam.id,
        deadline_id=deadline_id,
        title=exam.title,
    )
    return exam


async def get_upcoming_deadlines_all_courses(
    session: AsyncSession,
    limit: int = 5,
    user_id: str | None = None,
) -> list[dict]:
    """Get upcoming deadlines across all courses for the dashboard.

    Args:
        session: Database session.
        limit: Max deadlines to return.

    Returns:
        List of deadline dicts with course_code.
    """
    query = (
        select(Deadline, Course.code)
        .join(Course, Deadline.course_id == Course.id)
        .where(Deadline.due_date >= date.today())
    )
    if user_id:
        query = query.where(Course.user_id == user_id)
    query = query.order_by(Deadline.due_date).limit(limit)
    result = await session.execute(query)

    deadlines = []
    for deadline, course_code in result.all():
        deadlines.append(
            {
                "id": deadline.id,
                "title": deadline.title,
                "due_date": deadline.due_date.isoformat(),
                "deadline_type": deadline.deadline_type,
                "course_code": course_code,
                "is_confirmed": deadline.is_confirmed,
            }
        )
    return deadlines
