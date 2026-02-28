"""File serving API endpoint."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter()

# Map file_type to base directory
_TYPE_DIRS = {
    "uploads": settings.uploads_dir,
    "extractions": settings.extractions_dir,
    "summaries": settings.summaries_dir,
}


@router.get("/files/{file_type}/{path:path}")
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
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(file_path))
