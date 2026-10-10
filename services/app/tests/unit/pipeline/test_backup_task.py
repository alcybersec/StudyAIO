"""run_backup must hand scripts/backup.sh libpq env vars without leaking them."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import structlog

from app.config import settings
from app.pipeline import backup_task

PASSWORD = "p@ss:w/rd%#?"
URL = "postgresql://us%40er:p%40ss%3Aw%2Frd%25%23%3F@dbhost:6543/mydb"
ENCODED = "p%40ss%3Aw%2Frd%25%23%3F"


@pytest.fixture
def run_ok():
    proc = SimpleNamespace(returncode=0, stderr="", stdout="ok")
    with (
        patch.object(settings, "backup_enabled", True),
        patch.object(settings, "database_url_sync", URL),
        patch("app.pipeline.backup_task.subprocess.run", return_value=proc) as run,
    ):
        yield run


class TestBackupEnv:
    def test_libpq_env_derived_from_database_url(self, run_ok):
        backup_task.run_backup.run()
        env = run_ok.call_args.kwargs["env"]
        assert env["PGHOST"] == "dbhost"
        assert env["PGPORT"] == "6543"
        assert env["PGUSER"] == "us@er"
        assert env["PGPASSWORD"] == PASSWORD
        assert env["PGDATABASE"] == "mydb"
        assert env["BACKUP_DIR"] == "/app/backups"
        assert "PATH" in env

    def test_default_port_is_5432(self):
        proc = SimpleNamespace(returncode=0, stderr="", stdout="")
        with (
            patch.object(settings, "backup_enabled", True),
            patch.object(settings, "database_url_sync", "postgresql://u:p@db/studyaio"),
            patch("app.pipeline.backup_task.subprocess.run", return_value=proc) as run,
        ):
            backup_task.run_backup.run()
        assert run.call_args.kwargs["env"]["PGPORT"] == "5432"


class TestBackupNoLeak:
    def test_logs_never_contain_password_or_url(self, run_ok):
        with structlog.testing.capture_logs() as logs:
            backup_task.run_backup.run()
        blob = repr(logs)
        assert PASSWORD not in blob and ENCODED not in blob and URL not in blob
        assert any(e.get("db_host") == "dbhost" for e in logs)

    def test_failure_paths_scrub_password(self):
        stderr = f"pg_dump: connection failed PGPASSWORD={PASSWORD} {ENCODED}"
        proc = SimpleNamespace(returncode=1, stderr=stderr, stdout="")
        task = backup_task.run_backup
        retry = MagicMock(side_effect=RuntimeError("retry"))
        with (
            patch.object(settings, "backup_enabled", True),
            patch.object(settings, "database_url_sync", URL),
            patch("app.pipeline.backup_task.subprocess.run", return_value=proc),
            structlog.testing.capture_logs() as logs,
            patch.object(task, "retry", retry, create=True),
            pytest.raises(RuntimeError),
        ):
            task.run()
        blob = repr(logs) + repr(retry.call_args)
        assert retry.called
        assert PASSWORD not in blob and ENCODED not in blob

    def test_unexpected_exception_scrubbed(self):
        boom = RuntimeError(f"cmd failed env PGPASSWORD={PASSWORD} {ENCODED}")
        with (
            patch.object(settings, "backup_enabled", True),
            patch.object(settings, "database_url_sync", URL),
            patch("app.pipeline.backup_task.subprocess.run", side_effect=boom),
            structlog.testing.capture_logs() as logs,
            pytest.raises(RuntimeError) as exc,
        ):
            backup_task.run_backup.run()
        assert PASSWORD not in repr(logs) + str(exc.value)
        assert ENCODED not in repr(logs) + str(exc.value)
