"""Per-stage Celery time limits and the stuck threshold (TECH-04, GL#22).

Import-light on purpose. Importing this module applies the limits to the Celery
app as `task_annotations` (the soft limit raises inside the task so it can retry;
the hard limit kills a wedged process). `app.worker` lists it in `include=` by
name, so the dependency points pipeline -> worker as ADR 0002 requires.
"""

from app.worker import celery_app

TRANSIENT_MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 30
BACKOFF_CAP_SECONDS = 600

#: task name -> (soft, hard) seconds.
STAGE_TIME_LIMITS: dict[str, tuple[int, int]] = {
    "app.pipeline.ingest.ingest_file": (300, 330),
    "app.pipeline.classify.classify_artifact": (420, 480),
    "app.pipeline.extract.extract_artifact": (900, 960),
    "app.pipeline.summarize.summarize_artifact": (1500, 1560),
    "app.pipeline.index.index_artifact": (900, 960),
    "app.pipeline.assets.generate_assets": (1500, 1560),
}

#: An in-progress artifact untouched this long is stuck. Above the largest hard
#: limit (1560s) plus the longest backoff (600s) with margin.
STUCK_THRESHOLD_SECONDS = 45 * 60

celery_app.conf.task_annotations = {
    name: {"soft_time_limit": soft, "time_limit": hard}
    for name, (soft, hard) in STAGE_TIME_LIMITS.items()
}
