"""Retry, time-limit and recovery policy shared by the pipeline stages (TECH-04, GL#22).

Three rules:

* **Transient errors retry; permanent ones fail fast.** A transient error is a
  `TransientAgentError` (timeout / 429 / 5xx / connection reset, classified in the
  adapters), a `StageBusyError` (another worker holds the week's summarize lock)
  or a Celery soft time limit. Retries use exponential backoff with jitter and are
  bounded by `TRANSIENT_MAX_RETRIES`; when they run out the artifact is marked
  failed with a `pipeline_runs` row.
* **Every stage has a soft and hard time limit** (`STAGE_TIME_LIMITS`, applied via
  `task_annotations` in `app.worker`). The hard limit always exceeds the longest
  AI call the stage can make.
* **Stuck artifacts recover.** `STUCK_THRESHOLD_SECONDS` exceeds every hard limit
  plus the longest backoff, so the beat job in `app.pipeline.recovery` never
  races a live task.
"""

import random
from collections import Counter
from typing import NoReturn

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from app.agents.transient import TransientAgentError
from app.core.database import run_async
from app.core.exceptions import SummarizationError
from app.pipeline.failures import record_stage_event
from app.pipeline.limits import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_CAP_SECONDS,
    STAGE_TIME_LIMITS,  # noqa: F401 - re-exported
    STUCK_THRESHOLD_SECONDS,  # noqa: F401 - re-exported
    TRANSIENT_MAX_RETRIES,
)
from app.services.event_service import publish_pipeline_event_sync

logger = structlog.get_logger()

#: In-process counters (also emitted as structured `pipeline_metric` log lines).
METRICS: Counter[str] = Counter()


def count_metric(name: str, **labels: str) -> None:
    """Increment a pipeline counter and log it."""
    key = name + "".join(f"|{k}={v}" for k, v in sorted(labels.items()))
    METRICS[key] += 1
    logger.info("pipeline_metric", metric=name, value=1, **labels)


class StageBusyError(SummarizationError):
    """Another worker holds the lock this stage needs; retry later (GL#23)."""


def is_retryable(exc: BaseException) -> bool:
    """True for errors a stage retries instead of failing the artifact."""
    return isinstance(exc, (TransientAgentError, StageBusyError, SoftTimeLimitExceeded))


def backoff_countdown(retries: int) -> int:
    """Seconds to wait before retry number ``retries + 1``: exponential, jittered.

    Equal jitter: half the exponential delay is fixed, half is random, so
    simultaneous failures do not retry in lockstep.
    """
    delay = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2**retries))
    return int(delay / 2 + random.uniform(0, delay / 2))  # noqa: S311 - jitter, not crypto


def handle_retryable(
    task,
    exc: BaseException,
    *,
    stage: str,
    artifact_id: str,
    event_user_id: str | None,
) -> NoReturn:
    """Retry ``task`` with backoff, or fail the artifact once retries run out.

    Always raises: `task.retry(...)`'s `Retry`, or ``exc`` when exhausted.
    """
    retries = task.request.retries
    timed_out = isinstance(exc, SoftTimeLimitExceeded)
    message = f"{stage} exceeded its time limit" if timed_out else f"{type(exc).__name__}: {exc}"
    if timed_out:
        count_metric("pipeline_stage_timeouts_total", stage=stage)
        # The stage's own run row died with its transaction; leave a visible one.
        run_async(
            record_stage_event(
                artifact_id, stage, "failed", f"time limit exceeded; {retries} prior retries"
            )
        )
    if retries >= TRANSIENT_MAX_RETRIES:
        count_metric("pipeline_stage_retries_exhausted_total", stage=stage)
        logger.error(
            "pipeline_retries_exhausted", stage=stage, artifact_id=artifact_id, retries=retries
        )
        run_async(
            record_stage_event(
                artifact_id,
                stage,
                "failed",
                f"retries exhausted after {retries}: {message}",
                artifact_status="failed",
            )
        )
        publish_pipeline_event_sync(artifact_id, stage, "failed", user_id=event_user_id)
        raise exc
    countdown = backoff_countdown(retries)
    count_metric("pipeline_stage_retries_total", stage=stage)
    logger.warning(
        "pipeline_stage_retrying",
        stage=stage,
        artifact_id=artifact_id,
        attempt=retries + 1,
        countdown=countdown,
        error=message,
    )
    publish_pipeline_event_sync(artifact_id, stage, "retrying", user_id=event_user_id)
    raise task.retry(exc=exc, countdown=countdown, max_retries=TRANSIENT_MAX_RETRIES)
