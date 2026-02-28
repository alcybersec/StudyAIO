"""Celery application factory."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "studyaio",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.pipeline.*": {"queue": "pipeline"},
    },
)

# Auto-discover pipeline tasks
celery_app.autodiscover_tasks(["app.pipeline"])
