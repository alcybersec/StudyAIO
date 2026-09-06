"""File serving API endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.storage import LocalStorageBackend, get_storage, normalize_storage_key
from app.models.user import User
from app.services import artifact_service, course_service

router = APIRouter()

# Prefixes the generic path-addressed route at the bottom of this module will
# serve.
#
# ``uploads`` and ``courseops`` are deliberately absent. Both already have
# id-addressed, owner-scoped routes above (``/files/uploads/artifacts/{id}``,
# ``/files/courseops/documents/{id}``) and those are what the UI uses
# (``ArtifactList.tsx``, ``FileViewer.tsx``). Serving them by raw path as well
# only widened #66: an uploaded file's storage key is
# ``uploads/<uuid>_<original name>`` and carries no owner, so there is nothing
# in the path to scope it by.
_VALID_PREFIXES = {"extractions", "summaries"}

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

    doc = await courseops_service.get_course_document(session, document_id, user_id=user.id)
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
    "/files/uploads/artifacts/{artifact_id}/preview",
    response_model=None,
    summary="Inline preview of an artifact as PDF",
    description="Serves a PDF for inline preview — the original for PDFs, or a cached LibreOffice conversion for PPTX/DOCX.",
)
async def preview_artifact(
    artifact_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Serve a PDF suitable for inline preview (converts Office files on demand)."""
    from app.services import preview_service

    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user.id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if artifact.file_type == "pdf":
        key = normalize_storage_key(artifact.file_path)
        return await _serve_storage_key(key, media_type="application/pdf")

    if artifact.file_type not in preview_service.CONVERTIBLE_TYPES:
        raise HTTPException(status_code=415, detail="No inline preview for this file type")

    key = await preview_service.ensure_preview_pdf(session, artifact_id, user_id=user.id)
    if not key:
        raise HTTPException(status_code=422, detail="Preview could not be generated")
    return await _serve_storage_key(key, media_type="application/pdf")


async def _authorize_path(
    file_type: str,
    path: str,
    user: User,
    session: AsyncSession,
) -> None:
    """Raise 404 unless *user* owns the object the path addresses.

    The generic route's path carries no owner of its own, so authentication
    alone would leave any signed-in user able to read anyone else's files --
    the #47/#53/#55 IDOR class. Ownership is instead resolved from the shape
    of each prefix, whose first segment is always an owned object's id:

    * ``extractions/<artifact_id>/...`` -- everything the extraction pipeline
      writes lives under the artifact's own id (``pipeline/extract.py``), so
      the owner-scoped artifact getter settles the whole subtree.
    * ``summaries/<COURSE_CODE>/...`` -- summary keys are
      ``summaries/<CODE>/<CODE>_Week<N>.md`` (``summary_service`` builds
      them), so the owner-scoped course getter settles the whole subtree.
      This is the half of #66 that was enumerable: course codes are standard
      university codes and weeks run 1-15.

    A path too short to carry an owner segment is unresolvable, so it is
    refused rather than served.

    Raises:
        HTTPException: 404 if the caller does not own the addressed object.
    """
    parts = Path(path).parts
    # ``<owner segment>/<filename>`` is the shortest addressable form.
    if len(parts) < 2:
        raise HTTPException(status_code=404, detail="File not found")

    owner_segment = parts[0]
    if file_type == "extractions":
        owned = await artifact_service.get_artifact(session, owner_segment, user_id=user.id)
    elif file_type == "summaries":
        owned = await course_service.get_course_by_code(session, owner_segment, user_id=user.id)
    else:
        # A prefix added to _VALID_PREFIXES without an ownership rule here
        # fails closed, rather than inheriting whichever branch is last.
        owned = None

    if not owned:
        # 404, not 403: a 403 here would confirm the file exists to someone
        # who may not have it, and every id-addressed route above 404s too.
        raise HTTPException(status_code=404, detail="File not found")


@router.get(
    "/files/{file_type}/{path:path}",
    response_model=None,
    summary="Serve a file",
    description=(
        "Serves a file the caller owns from the data directory. file_type must be one of: "
        "extractions, summaries. Path traversal is blocked. Files the caller does not own "
        "return 404."
    ),
)
async def serve_file(
    file_type: str,
    path: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Serve a file from the data directory, scoped to its owner.

    Args:
        file_type: One of extractions, summaries.
        path: Relative path within the type directory.
        user: Authenticated caller.
        session: Database session.
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

    await _authorize_path(file_type, path, user, session)

    key = f"{file_type}/{path}"
    return await _serve_storage_key(key)
