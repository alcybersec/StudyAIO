"""Celery application factory."""

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from app.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry

# Error monitoring for the worker process (no-op unless SENTRY_DSN is set).
init_sentry("worker")


@setup_logging.connect
def configure_worker_logging(**_kwargs: object) -> None:
    """Install the redacting log config for the worker and beat processes.

    Connecting to ``setup_logging`` stops Celery from hijacking the root logger,
    so structlog's ``redact_emails`` and the stdlib ``EmailRedactingFilter``
    apply to task logs too. Prefork children are forked after this runs in the
    parent and inherit the configured root logger and handlers.
    """
    configure_logging(settings.log_level)


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
        "app.pipeline.reembed_task",
        "app.pipeline.assets",
        "app.pipeline.courseops_task",
        "app.pipeline.notification_tasks",
        "app.pipeline.calendar_task",
        "app.pipeline.backup_task",
        "app.pipeline.recovery",
        "app.pipeline.limits",
        "app.pipeline.metrics",
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
    # Per-stage soft/hard time limits (TECH-04) are applied by app.pipeline.limits
    # (ADR 0002: worker must not import pipeline).
    beat_schedule={
        "recover-stuck-artifacts": {
            "task": "app.pipeline.recovery.recover_stuck_artifacts",
            "schedule": crontab(minute="*/10"),
        },
        "daily-deadline-reminders": {
            "task": "app.pipeline.notification_tasks.send_deadline_reminders",
            "schedule": crontab(minute=0),
        },
        "daily-card-reminders": {
            "task": "app.pipeline.notification_tasks.send_daily_reminders",
            "schedule": crontab(minute=0),
        },
        "weekly-study-digest": {
            "task": "app.pipeline.notification_tasks.send_weekly_digest",
            "schedule": crontab(minute=0),
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
