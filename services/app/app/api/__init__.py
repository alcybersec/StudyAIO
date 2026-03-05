"""FastAPI API routers."""

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.chat import router as chat_router
from app.api.concepts import router as concepts_router
from app.api.courseops import router as courseops_router
from app.api.courses import router as courses_router
from app.api.dashboard import router as dashboard_router
from app.api.exams import router as exams_router
from app.api.exports import router as exports_router
from app.api.files import router as files_router
from app.api.gamification import router as gamification_router
from app.api.qa import router as qa_router
from app.api.review_items import router as review_items_router
from app.api.settings import router as settings_router
from app.api.study import router as study_router
from app.api.summaries import router as summaries_router
from app.api.uploads import router as uploads_router

__all__ = [
    "admin_router",
    "analytics_router",
    "assets_router",
    "auth_router",
    "billing_router",
    "chat_router",
    "concepts_router",
    "courseops_router",
    "courses_router",
    "dashboard_router",
    "exams_router",
    "exports_router",
    "gamification_router",
    "files_router",
    "qa_router",
    "review_items_router",
    "settings_router",
    "study_router",
    "summaries_router",
    "uploads_router",
]
