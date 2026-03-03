"""CourseOps Celery task — extract assessments and deadlines from course documents."""

from pathlib import Path

import structlog

from app.agents.factory import get_agent
from app.core.database import async_session_factory, run_async
from app.core.exceptions import CourseOpsError
from app.extractors import get_extractor
from app.models.course_document import CourseDocument
from app.services import courseops_service
from app.worker import celery_app

logger = structlog.get_logger()


async def _process_document(document_id: str) -> dict:
    """Async implementation: extract text, call AI, persist results.

    Args:
        document_id: UUID of the CourseDocument.

    Returns:
        Dict with document_id, assessment_count, deadline_count.

    Raises:
        CourseOpsError: If processing fails.
    """
    async with async_session_factory() as session:
        doc = await session.get(CourseDocument, document_id)
        if not doc:
            raise CourseOpsError(f"CourseDocument {document_id} not found")

        # Update status to processing
        doc.status = "processing"
        await session.commit()

        try:
            # Extract text from file
            file_path = Path(doc.file_path)
            if not file_path.exists():
                raise CourseOpsError(f"File not found: {doc.file_path}")

            extractor = get_extractor(doc.file_type)
            # Use a temp dir for images (we don't need them for course docs)
            output_dir = file_path.parent / "courseops_extract"
            output_dir.mkdir(exist_ok=True)

            extraction_result = extractor.extract(file_path, output_dir)
            extracted_text = "\n\n".join(
                page.text for page in extraction_result.pages if page.text.strip()
            )

            if not extracted_text.strip():
                raise CourseOpsError("No text could be extracted from the document")

            # Load course code for the AI prompt
            from app.models.course import Course

            course = await session.get(Course, doc.course_id)
            course_code = course.code if course else "UNKNOWN"

            # Call AI agent
            agent = get_agent()
            ai_result = await agent.extract_course_ops(
                document_text=extracted_text,
                course_code=course_code,
                document_type=doc.document_type,
            )

            # Persist results
            result = await courseops_service.process_course_document(
                session=session,
                document_id=document_id,
                extracted_text=extracted_text,
                ai_result=ai_result,
            )

            return result

        except CourseOpsError:
            doc.status = "failed"
            await session.commit()
            raise

        except Exception as e:
            doc.status = "failed"
            await session.commit()
            raise CourseOpsError(f"CourseOps processing failed: {e}") from e


@celery_app.task(
    name="app.pipeline.courseops_task.process_course_document",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def process_course_document(self, document_id: str) -> dict:
    """Celery task: extract assessments and deadlines from a course document.

    This is a standalone task (not part of the 6-stage pipeline chain).

    Args:
        document_id: UUID of the CourseDocument to process.

    Returns:
        Dict with document_id, assessment_count, deadline_count.
    """
    logger.info("courseops_task_started", document_id=document_id)
    try:
        result = run_async(_process_document(document_id))
        logger.info("courseops_task_completed", **result)
        return result
    except CourseOpsError:
        raise
    except Exception as exc:
        logger.error("courseops_task_error", error=str(exc), document_id=document_id)
        raise self.retry(exc=exc) from exc
