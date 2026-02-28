"""FastAPI API routers."""

from app.api.courses import router as courses_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.review_items import router as review_items_router
from app.api.summaries import router as summaries_router
from app.api.uploads import router as uploads_router

__all__ = [
    "courses_router",
    "dashboard_router",
    "files_router",
    "review_items_router",
    "summaries_router",
    "uploads_router",
]
