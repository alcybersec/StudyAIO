"""Prometheus metrics for the Celery worker jobs (M32 gate condition G3).

Celery runs prefork, so prometheus_client must run in multiprocess mode: devops sets
``PROMETHEUS_MULTIPROC_DIR`` (a tmpfs dir) *before* the worker starts, and
prometheus_client then writes per-process files there. The worker main process serves
``/metrics`` on ``settings.worker_metrics_port`` through a `MultiProcessCollector`.
Without the env var or with port 0 nothing is served and no files are written; the
metric helpers stay safe to call.

Label policy (floor 2 / floor 1): labels are low-cardinality enums only -- ``stage``,
``outcome``, ``error_class``. Never a user id, artifact id, email or credential.
"""

import os
import time

import structlog
from celery.signals import (
    task_postrun,
    task_prerun,
    worker_process_shutdown,
    worker_ready,
)
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, multiprocess
from prometheus_client import start_http_server as _start_http_server

from app.config import settings

logger = structlog.get_logger()

#: Buckets span seconds (ingest) to the 1560s hard limit of summarize/assets.
_STAGE_BUCKETS = (1, 5, 15, 30, 60, 120, 300, 600, 900, 1500, 2400)
_BACKUP_BUCKETS = (1, 5, 15, 30, 60, 120, 300, 600)

STAGE_DURATION = Histogram(
    "studyaio_stage_duration_seconds",
    "Wall time of one pipeline stage task run.",
    ["stage", "outcome"],
    buckets=_STAGE_BUCKETS,
)
STAGE_RETRIES = Counter(
    "studyaio_stage_retries_total",
    "Stage retries scheduled after a retryable error.",
    ["stage", "error_class"],
)
STAGE_FAILURES = Counter(
    "studyaio_stage_failures_total", "Stage task runs that ended in failure.", ["stage"]
)
STUCK_REQUEUED = Counter(
    "studyaio_stuck_artifacts_requeued_total",
    "Stuck artifacts requeued by the recovery job.",
    ["stage"],
)
STUCK_FAILED = Counter(
    "studyaio_stuck_artifacts_failed_total",
    "Stuck artifacts the recovery job gave up on.",
    ["stage"],
)
RECOVERY_RUNS = Counter(
    "studyaio_recovery_runs_total", "Recovery job runs by outcome.", ["outcome"]
)
REEMBED_ARTIFACTS = Counter(
    "studyaio_reembed_artifacts_total",
    "Artifacts processed by the re-embed job.",
    ["outcome"],  # reembedded | skipped_fit | skipped_no_extraction | failed
)
#: Targeted (weak-spot) generation, ADR 0007. ``stage`` carries the kind (quiz | flashcards).
TARGETED_GENERATIONS = Counter(
    "studyaio_targeted_generations_total",
    "Targeted generations by kind (stage) and outcome.",
    ["stage", "outcome"],  # outcome: completed | failed | retry | skipped | recovered
)
TARGETED_FAILURES = Counter(
    "studyaio_targeted_generation_failures_total",
    "Targeted generations that failed or retried, by kind (stage) and exception class.",
    ["stage", "error_class"],  # error_class is type(exc).__name__, never a message
)
TARGETED_ITEMS = Counter(
    "studyaio_targeted_items_total",
    "Items a targeted generation produced or dropped, by kind (stage).",
    ["stage", "outcome"],  # outcome: created | dropped_uncited | dropped_duplicate
)
TARGETED_SECONDS = Histogram(
    "studyaio_targeted_generation_seconds",
    "Wall time of one targeted generation task run.",
    ["stage", "outcome"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600),
)
BACKUP_RUNS = Counter("studyaio_backup_runs_total", "Backup runs by outcome.", ["outcome"])
BACKUP_DURATION = Histogram(
    "studyaio_backup_duration_seconds", "Wall time of a backup run.", buckets=_BACKUP_BUCKETS
)
BACKUP_LAST_SUCCESS = Gauge(
    "studyaio_backup_last_success_timestamp_seconds",
    "Unix time of the last successful backup.",
    multiprocess_mode="mostrecent",
)

#: Celery task name -> stage label, for per-stage latency.
_STAGE_TASKS: dict[str, str] = {
    "app.pipeline.ingest.ingest_file": "ingest",
    "app.pipeline.classify.classify_artifact": "classify",
    "app.pipeline.extract.extract_artifact": "extract",
    "app.pipeline.summarize.summarize_artifact": "summarize",
    "app.pipeline.index.index_artifact": "index",
    "app.pipeline.assets.generate_assets": "assets",
}
_started: dict[str, float] = {}


@task_prerun.connect(weak=False)
def _on_prerun(task_id: str | None = None, task=None, **_: object) -> None:
    if task is not None and task.name in _STAGE_TASKS and task_id:
        _started[task_id] = time.monotonic()


@task_postrun.connect(weak=False)
def _on_postrun(
    task_id: str | None = None, task=None, state: str | None = None, **_: object
) -> None:
    started = _started.pop(task_id, None) if task_id else None
    if task is None or started is None:
        return
    stage = _STAGE_TASKS[task.name]
    outcome = {"SUCCESS": "success", "RETRY": "retry"}.get(state or "", "failure")
    STAGE_DURATION.labels(stage=stage, outcome=outcome).observe(time.monotonic() - started)
    if outcome == "failure":
        STAGE_FAILURES.labels(stage=stage).inc()


def multiproc_dir() -> str | None:
    """The multiprocess directory, if prometheus_client is in multiprocess mode."""
    return os.environ.get("PROMETHEUS_MULTIPROC_DIR") or None


def start_worker_metrics_server() -> bool:
    """Serve the multiprocess registry on ``worker_metrics_port``.

    Returns:
        True when a server was started; False when disabled (port 0 or no
        ``PROMETHEUS_MULTIPROC_DIR``).
    """
    port = int(getattr(settings, "worker_metrics_port", 0) or 0)
    directory = multiproc_dir()
    if port <= 0 or not directory:
        return False
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=directory)
    _start_http_server(port, registry=registry)
    logger.info("worker_metrics_server_started", port=port)
    return True


@worker_ready.connect(weak=False)
def _on_worker_ready(**_: object) -> None:
    try:
        start_worker_metrics_server()
    except OSError as exc:  # port taken: metrics are optional, the worker is not
        logger.error("worker_metrics_server_failed", error=str(exc))


@worker_process_shutdown.connect(weak=False)
def _on_child_shutdown(pid: int | None = None, **_: object) -> None:
    if multiproc_dir() and pid:
        multiprocess.mark_process_dead(pid)
