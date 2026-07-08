"""File serving API endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.storage import LocalStorageBackend, get_storage, normalize_storage_key
from app.models.user import User
from app.services import artifact_service

router = APIRouter()

_VALID_PREFIXES = {"uploads", "extractions", "summaries", "courseops"}

# Map file extension to MIME type for inline viewing
_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


async def _serve_storage_key(
    key: str,
    filename: str | None = None,
    media_type: str = "application/octet-stream",
) -> FileResponse | Response:
    """Serve a file from the storage backend.

    For local storage, returns a FileResponse (zero-copy sendfile).
    For S3, returns the bytes directly (or could redirect to presigned URL).
    """
    storage = get_storage()
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="File not found")

    if isinstance(storage, LocalStorageBackend):
        local_path = storage.resolve_path(key)
        return FileResponse(
            str(local_path),
            filename=filename,
            media_type=media_type,
        )

    # S3 backend — read and return bytes
    data = await storage.get(key)
    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=data, media_type=media_type, headers=headers)


@router.get(
    "/files/courseops/documents/{document_id}",
    response_model=None,
    summary="Download a course/assessment document",
    description="Downloads a course or assessment document by ID with its original filename.",
)
async def download_course_document(
    document_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Download a CourseDocument's file by ID."""
    from app.services import courseops_service

    doc = await courseops_service.get_course_document(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    key = normalize_storage_key(doc.file_path)
    media_type = _MIME_TYPES.get(doc.file_type, "application/octet-stream")
    return await _serve_storage_key(key, filename=doc.original_filename, media_type=media_type)


@router.get(
    "/files/uploads/artifacts/{artifact_id}",
    response_model=None,
    summary="Download an uploaded artifact",
    description="Downloads the original uploaded file for a given artifact ID with the correct filename.",
)
async def download_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Download the original uploaded file for an artifact."""
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    key = normalize_storage_key(artifact.file_path)
    return await _serve_storage_key(
        key, filename=artifact.original_filename, media_type="application/octet-stream"
    )


@router.get(
    "/files/uploads/artifacts/{artifact_id}/view",
    response_model=None,
    summary="View an uploaded artifact inline",
    description="Serves the original uploaded file with the correct MIME type for inline viewing (e.g. PDF in browser).",
)
async def view_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Serve the original uploaded file for inline viewing."""
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    key = normalize_storage_key(artifact.file_path)
    media_type = _MIME_TYPES.get(artifact.file_type, "application/octet-stream")
    return await _serve_storage_key(key, media_type=media_type)


@router.get(
    "/files/{file_type}/{path:path}",
    response_model=None,
    summary="Serve a file",
    description="Serves a file from the data directory. file_type must be one of: uploads, extractions, summaries, courseops. Path traversal is blocked.",
)
async def serve_file(file_type: str, path: str) -> Response:
    """Serve a file from the data directory.

    Args:
        file_type: One of uploads, extractions, summaries, courseops.
        path: Relative path within the type directory.
    """
    if file_type not in _VALID_PREFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file_type}. Valid: {sorted(_VALID_PREFIXES)}",
        )

    # Prevent path traversal
    normalized = Path(path)
    if ".." in normalized.parts:
        raise HTTPException(status_code=403, detail="Access denied")

    key = f"{file_type}/{path}"
    return await _serve_storage_key(key)
