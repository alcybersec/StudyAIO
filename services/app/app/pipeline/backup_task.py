"""Celery task for automated database backups."""

import subprocess
from urllib.parse import quote, unquote, urlparse

import structlog

from app.config import settings
from app.worker import celery_app

logger = structlog.get_logger()


def _db_env() -> tuple[dict[str, str], str]:
    """Derive libpq env vars from ``settings.database_url_sync``.

    Returns:
        ``(env, secret)``: the PG* variables and the raw password, so callers
        can scrub it from anything they log or raise. The URL itself is never
        logged.
    """
    parsed = urlparse(settings.database_url_sync)
    password = unquote(parsed.password or "")
    env = {
        "PGHOST": parsed.hostname or "",
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": unquote(parsed.username or ""),
        "PGPASSWORD": password,
        "PGDATABASE": unquote(parsed.path.lstrip("/")),
    }
    return env, password


def _scrub(text: str, password: str) -> str:
    """Remove the password (raw and URL-encoded) from ``text``."""
    if not password:
        return text
    for secret in (password, quote(password, safe=""), quote(password)):
        text = text.replace(secret, "***")
    return text


@celery_app.task(name="app.pipeline.backup_task.run_backup", bind=True, max_retries=1)
def run_backup(self) -> dict[str, str]:
    """Run the backup script as a Celery task.

    Executes scripts/backup.sh inside the worker container.
    The backup sidecar or host cron can also trigger this directly.
    """
    if not settings.backup_enabled:
        logger.info("backup_skipped", reason="backup_enabled=false")
        return {"status": "skipped", "reason": "backups disabled"}

    db_env, password = _db_env()
    try:
        logger.info("backup_starting", db_host=db_env["PGHOST"], db_name=db_env["PGDATABASE"])
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
                **db_env,
            },
        )

        if result.returncode != 0:
            stderr = _scrub(result.stderr, password)
            logger.error("backup_failed", stderr=stderr[:500])
            raise self.retry(
                exc=RuntimeError(f"Backup failed: {stderr[:200]}"),
                countdown=300,
            )

        logger.info("backup_completed", stdout=_scrub(result.stdout[-200:], password))
        return {"status": "ok", "output": result.stdout[-200:]}

    except subprocess.TimeoutExpired:
        logger.error("backup_timeout")
        return {"status": "error", "reason": "timeout after 600s"}
    except Exception as exc:
        # Never log str(exc) raw: it may embed the child env or command.
        safe = _scrub(str(exc), password)
        logger.error("backup_error", error=safe)
        if safe != str(exc):
            raise RuntimeError(safe) from None
        raise
