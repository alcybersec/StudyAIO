"""FastAPI API routers."""

from app.api.assets import router as assets_router
from app.api.courses import router as courses_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.qa import router as qa_router
from app.api.review_items import router as review_items_router
from app.api.settings import router as settings_router
from app.api.study import router as study_router
from app.api.summaries import router as summaries_router
from app.api.uploads import router as uploads_router

__all__ = [
    "assets_router",
    "courses_router",
    "dashboard_router",
    "files_router",
    "qa_router",
    "review_items_router",
    "settings_router",
    "study_router",
    "summaries_router",
    "uploads_router",
]
