"""Celery application factory."""

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging
from kombu import Queue

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


#: Queue names (TECH-09, GL#51). Each is served by its own worker pool so a slow
#: beat job cannot occupy the slots a user's upload is waiting for, and vice versa.
PIPELINE_QUEUE = "pipeline"
AI_ONDEMAND_QUEUE = "ai_ondemand"
MAINTENANCE_QUEUE = "maintenance"
#: The queue every task used before the split. Nothing routes here any more; it is
#: still declared so a worker started without ``-Q`` drains messages that were
#: enqueued before the rollout. Remove once that queue is empty.
LEGACY_QUEUE = "celery"

#: Every queue a task may be routed to, plus the legacy drain queue.
ALL_QUEUES = (PIPELINE_QUEUE, AI_ONDEMAND_QUEUE, MAINTENANCE_QUEUE, LEGACY_QUEUE)

#: ``-Q`` list for a single worker consuming everything (rollout / small installs).
SINGLE_WORKER_QUEUES = ",".join(ALL_QUEUES)

_QUEUE_TASKS: dict[str, tuple[str, ...]] = {
    # Interactive: a user is waiting on these.
    PIPELINE_QUEUE: (
        "app.pipeline.ingest.ingest_file",
        "app.pipeline.classify.classify_artifact",
        "app.pipeline.extract.extract_artifact",
        "app.pipeline.summarize.summarize_artifact",
        "app.pipeline.index.index_artifact",
        "app.pipeline.assets.generate_assets",
        "app.pipeline.courseops_task.process_course_document",
    ),
    # User-triggered, heavier, not on the upload path.
    AI_ONDEMAND_QUEUE: (
        "app.pipeline.targeted_task.generate_targeted_items",
        "app.pipeline.concepts_task.extract_concepts",
    ),
    # Beat-driven and operator jobs.
    MAINTENANCE_QUEUE: (
        "app.pipeline.recovery.recover_stuck_artifacts",
        "app.pipeline.targeted_task.recover_stuck_generations",
        "app.pipeline.notification_tasks.send_deadline_reminders",
        "app.pipeline.notification_tasks.send_daily_reminders",
        "app.pipeline.notification_tasks.send_weekly_digest",
        "app.pipeline.calendar_task.sync_all_calendars",
        "app.pipeline.backup_task.run_backup",
        "app.pipeline.reembed_task.reembed_all_chunks",
        "app.pipeline.reembed_task.reembed_user_chunks",
    ),
}

#: task name -> queue. Named by string (ADR 0002: worker must not import pipeline).
#: A unit test fails any registered task missing here; the default queue is only
#: a safety net.
TASK_ROUTES: dict[str, dict[str, str]] = {
    name: {"queue": queue} for queue, names in _QUEUE_TASKS.items() for name in names
}

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
        "app.pipeline.targeted_task",
        "app.pipeline.concepts_task",
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
    # Queue split (TECH-09). The default is the interactive queue: an unrouted new
    # task must not land on maintenance, nor on the unconsumed legacy queue.
    task_default_queue=PIPELINE_QUEUE,
    task_queues=tuple(Queue(name) for name in ALL_QUEUES),
    task_routes=TASK_ROUTES,
    # acks_late redelivers a task whose unacked message outlives the Redis
    # visibility timeout (default 1h) while it is still running. Keep it above the
    # longest hard limit so a slow task is not run twice (limits.py, TECH-04).
    broker_transport_options={"visibility_timeout": 7200},
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    # Per-stage soft/hard time limits (TECH-04) are applied by app.pipeline.limits
    # (ADR 0002: worker must not import pipeline).
    beat_schedule={
        "recover-stuck-artifacts": {
            "task": "app.pipeline.recovery.recover_stuck_artifacts",
            "schedule": crontab(minute="*/10"),
        },
        "recover-stuck-generations": {
            "task": "app.pipeline.targeted_task.recover_stuck_generations",
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
