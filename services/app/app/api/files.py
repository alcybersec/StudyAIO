"""File serving API endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.config import settings
from app.core.database import get_session
from app.models.user import User
from app.services import artifact_service

router = APIRouter()

# Map file_type to base directory
_TYPE_DIRS = {
    "uploads": settings.uploads_dir,
    "extractions": settings.extractions_dir,
    "summaries": settings.summaries_dir,
}

# Map file extension to MIME type for inline viewing
_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@router.get(
    "/files/uploads/artifacts/{artifact_id}",
    summary="Download an uploaded artifact",
    description="Downloads the original uploaded file for a given artifact ID with the correct filename.",
)
async def download_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download the original uploaded file for an artifact."""
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = Path(artifact.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        str(file_path),
        filename=artifact.original_filename,
        media_type="application/octet-stream",
    )


@router.get(
    "/files/uploads/artifacts/{artifact_id}/view",
    summary="View an uploaded artifact inline",
    description="Serves the original uploaded file with the correct MIME type for inline viewing (e.g. PDF in browser).",
)
async def view_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Serve the original uploaded file for inline viewing."""
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = Path(artifact.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_type = _MIME_TYPES.get(
        artifact.file_type, "application/octet-stream"
    )

    return FileResponse(str(file_path), media_type=media_type)


@router.get(
    "/files/{file_type}/{path:path}",
    summary="Serve a file",
    description="Serves a file from the data directory. file_type must be one of: uploads, extractions, summaries. Path traversal is blocked.",
)
async def serve_file(file_type: str, path: str) -> FileResponse:
    """Serve a file from the data directory.

    Args:
        file_type: One of uploads, extractions, summaries.
        path: Relative path within the type directory.
    """
    base_dir = _TYPE_DIRS.get(file_type)
    if not base_dir:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file_type}. Valid: {sorted(_TYPE_DIRS.keys())}",
        )

    file_path = Path(base_dir) / path

    # Prevent path traversal
    try:
        file_path.resolve().relative_to(Path(base_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied") from None

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(file_path))
