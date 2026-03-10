"""Celery application factory."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "studyaio",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.pipeline.ingest",
        "app.pipeline.classify",
        "app.pipeline.extract",
        "app.pipeline.summarize",
        "app.pipeline.index",
        "app.pipeline.assets",
        "app.pipeline.courseops_task",
        "app.pipeline.notification_tasks",
        "app.pipeline.calendar_task",
        "app.pipeline.backup_task",
    ],
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
    worker_max_tasks_per_child=100,
    beat_schedule={
        "daily-card-reminders": {
            "task": "app.pipeline.notification_tasks.send_daily_reminders",
            "schedule": crontab(hour=8, minute=0),
        },
        "weekly-study-digest": {
            "task": "app.pipeline.notification_tasks.send_weekly_digest",
            "schedule": crontab(hour=9, minute=0, day_of_week="sunday"),
        },
        "calendar-sync": {
            "task": "app.pipeline.calendar_task.sync_all_calendars",
            "schedule": crontab(minute="*/15"),
        },
        "daily-backup": {
            "task": "app.pipeline.backup_task.run_backup",
            "schedule": crontab(hour=settings.backup_schedule_hour, minute=0),
        },
    },
)
