"""CourseOps API endpoints — course documents, assessments, deadlines, and exports."""

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.courseops_schemas import (
    AssessmentResponse,
    CourseDocumentDetailResponse,
    CourseDocumentResponse,
    DeadlineResponse,
    DeadlineUpdateRequest,
)
from app.api.deps import get_current_user_or_default
from app.config import settings
from app.core.database import get_session
from app.core.exceptions import CourseOpsError
from app.core.rate_limit import limiter
from app.core.utils import read_upload_with_limit, sanitize_filename
from app.models.user import User
from app.services import courseops_service
from app.services.calendar_service import generate_ics, generate_task_plan_md

logger = structlog.get_logger()

router = APIRouter(prefix="/courseops")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}


@router.post(
    "/documents",
    response_model=CourseDocumentResponse,
    status_code=201,
    summary="Upload a course document",
    description="Upload a course outline, rubric, or handbook. Triggers AI extraction of assessments and deadlines.",
)
@limiter.limit(lambda: settings.rate_limit_uploads)
async def upload_course_document(
    request: Request,
    file: UploadFile,
    course_code: str = Query(..., description="Course code to associate with"),
    document_type: str = Query(
        ..., description="Document type: outline, rubric, handbook, other"
    ),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseDocumentResponse:
    """Upload a course document and trigger processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    if document_type not in ("outline", "rubric", "handbook", "other"):
        raise HTTPException(
            status_code=400,
            detail="document_type must be one of: outline, rubric, handbook, other",
        )

    # Save file to disk
    upload_dir = Path(settings.data_dir) / "courseops"
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(file.filename)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await read_upload_with_limit(file, max_bytes)
    file_size = len(content)

    # Write temp then compute hash
    import hashlib

    sha256 = hashlib.sha256(content).hexdigest()
    stored_name = f"{sha256[:16]}_{safe_name}"
    file_path = upload_dir / stored_name
    file_path.write_bytes(content)

    try:
        doc = await courseops_service.upload_course_document(
            session=session,
            course_code=course_code,
            document_type=document_type,
            original_filename=file.filename,
            file_path=str(file_path),
            file_type=ext.lstrip("."),
            sha256=sha256,
            file_size_bytes=file_size,
            user_id=user.id,
        )
    except CourseOpsError as e:
        # Clean up file on error
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(e)) from e

    # Dispatch Celery task for AI extraction
    from app.pipeline.courseops_task import process_course_document

    process_course_document.delay(doc.id)

    return CourseDocumentResponse.model_validate(doc)


@router.get(
    "/documents",
    response_model=list[CourseDocumentResponse],
    summary="List course documents",
)
async def list_documents(
    course_code: str = Query(..., description="Course code"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[CourseDocumentResponse]:
    """List all course documents for a course."""
    docs = await courseops_service.list_course_documents(session, course_code, user_id=user.id)
    return [CourseDocumentResponse.model_validate(d) for d in docs]


@router.get(
    "/documents/{document_id}",
    response_model=CourseDocumentDetailResponse,
    summary="Get course document detail",
)
async def get_document(
    document_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseDocumentDetailResponse:
    """Get a course document with its extracted assessments and deadlines."""
    doc = await courseops_service.get_course_document(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return CourseDocumentDetailResponse.model_validate(doc)


@router.get(
    "/assessments",
    response_model=list[AssessmentResponse],
    summary="List assessments",
)
async def list_assessments(
    course_code: str = Query(..., description="Course code"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[AssessmentResponse]:
    """List all assessments for a course."""
    assessments = await courseops_service.list_assessments(session, course_code)
    return [AssessmentResponse.model_validate(a) for a in assessments]


@router.get(
    "/deadlines",
    response_model=list[DeadlineResponse],
    summary="List deadlines",
)
async def list_deadlines(
    course_code: str = Query(..., description="Course code"),
    upcoming: bool = Query(False, description="Only show future deadlines"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[DeadlineResponse]:
    """List deadlines for a course."""
    deadlines = await courseops_service.list_deadlines(
        session, course_code, upcoming_only=upcoming
    )
    return [DeadlineResponse.model_validate(d) for d in deadlines]


@router.put(
    "/deadlines/{deadline_id}",
    response_model=DeadlineResponse,
    summary="Update a deadline",
)
async def update_deadline(
    deadline_id: str,
    body: DeadlineUpdateRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> DeadlineResponse:
    """Update or confirm a deadline."""
    deadline = await courseops_service.update_deadline(
        session,
        deadline_id,
        title=body.title,
        due_date=body.due_date,
        deadline_type=body.deadline_type,
        description=body.description,
        is_confirmed=body.is_confirmed,
    )
    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")
    return DeadlineResponse.model_validate(deadline)


@router.delete(
    "/deadlines/{deadline_id}",
    status_code=204,
    summary="Delete a deadline",
)
async def delete_deadline(
    deadline_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an AI-extracted deadline."""
    deleted = await courseops_service.delete_deadline(session, deadline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Deadline not found")


@router.post(
    "/deadlines/{deadline_id}/create-exam",
    response_model=dict,
    status_code=201,
    summary="Create exam from deadline",
)
async def create_exam_from_deadline(
    deadline_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create an Exam entity from a deadline."""
    try:
        exam = await courseops_service.create_exam_from_deadline(session, deadline_id, user_id=user.id)
    except CourseOpsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not exam:
        raise HTTPException(status_code=404, detail="Deadline not found")

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "exam_date": exam.exam_date.isoformat(),
        "status": exam.status,
    }


@router.get(
    "/export/calendar/{course_code}",
    summary="Download .ics calendar",
)
async def export_calendar(
    course_code: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Download an .ics calendar file with all deadlines for a course."""
    result = await generate_ics(session, course_code)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found or no deadlines")

    buf, filename = result
    return StreamingResponse(
        buf,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/export/task-plan/{course_code}",
    summary="Download markdown task plan",
)
async def export_task_plan(
    course_code: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Download a markdown task plan with deadlines and study recommendations."""
    result = await generate_task_plan_md(session, course_code)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")

    buf, filename = result
    return StreamingResponse(
        buf,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
