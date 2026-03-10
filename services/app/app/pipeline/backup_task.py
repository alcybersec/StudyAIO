"""Celery task for automated database backups."""

import subprocess

import structlog

from app.config import settings
from app.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.pipeline.backup_task.run_backup", bind=True, max_retries=1)
def run_backup(self) -> dict[str, str]:
    """Run the backup script as a Celery task.

    Executes scripts/backup.sh inside the worker container.
    The backup sidecar or host cron can also trigger this directly.
    """
    if not settings.backup_enabled:
        logger.info("backup_skipped", reason="backup_enabled=false")
        return {"status": "skipped", "reason": "backups disabled"}

    try:
        logger.info("backup_starting")
        result = subprocess.run(
            ["bash", "/app/scripts/backup.sh"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            env={
                "BACKUP_DIR": "/app/backups",
                "DATA_DIR": settings.data_dir,
                "BACKUP_RETENTION": str(settings.backup_retention),
                "PATH": "/usr/local/bin:/usr/bin:/bin",
            },
        )

        if result.returncode != 0:
            logger.error("backup_failed", stderr=result.stderr[:500])
            raise self.retry(
                exc=RuntimeError(f"Backup failed: {result.stderr[:200]}"),
                countdown=300,
            )

        logger.info("backup_completed", stdout=result.stdout[-200:])
        return {"status": "ok", "output": result.stdout[-200:]}

    except subprocess.TimeoutExpired:
        logger.error("backup_timeout")
        return {"status": "error", "reason": "timeout after 600s"}
    except Exception as exc:
        logger.error("backup_error", error=str(exc))
        raise
