"""Hermetic tests for scripts/backup.sh and scripts/offsite-backup.sh (W1-07).

Both are bash, so they run as subprocesses against a temp tree with stub
``restic`` / ``pg_dump`` binaries on PATH. Nothing here touches a network, a
database or a real repository.
"""

import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[4] / "scripts"
BACKUP = SCRIPTS / "backup.sh"
OFFSITE = SCRIPTS / "offsite-backup.sh"

# Logs every invocation (one line of args per call) and fails on request.
RESTIC_STUB = """#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
if [[ -n "${STUB_FAIL_ON:-}" && "$1" == "$STUB_FAIL_ON" ]]; then
    exit 3
fi
exit 0
"""

PG_DUMP_STUB = """#!/usr/bin/env bash
head -c 4000 /dev/urandom | base64
"""


def _stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def stubs(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _stub(bindir, "restic", RESTIC_STUB)
    _stub(bindir, "pg_dump", PG_DUMP_STUB)
    return bindir


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A fake /opt/studyaio with backups/ and data/."""
    root = tmp_path / "studyaio"
    (root / "backups").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "data" / "f.txt").write_text("x")
    return root


def _conf(tmp_path: Path) -> Path:
    conf = tmp_path / "offsite.conf"
    conf.write_text(
        "RESTIC_REPOSITORY=rest:https://backup.invalid/studyaio\n"
        f"RESTIC_PASSWORD_FILE={tmp_path / 'pass'}\n"
    )
    return conf


def _fresh_dump(tree: Path, age_hours: float = 1.0) -> Path:
    dump = tree / "backups" / "studyaio_20260101_020000_db.sql.gz"
    dump.write_bytes(b"x" * 200)
    mtime = time.time() - age_hours * 3600
    os.utime(dump, (mtime, mtime))
    return dump


def _run_offsite(tmp_path, tree, stubs, **extra):
    textfile = tmp_path / "textfile"
    textfile.mkdir(exist_ok=True)
    log = tmp_path / "restic.log"
    env = {
        "PATH": f"{stubs}:/usr/bin:/bin",
        "STUDYAIO_OFFSITE_CONF": str(_conf(tmp_path)),
        "STUDYAIO_DIR": str(tree),
        "TEXTFILE_DIR": str(textfile),
        "STUB_LOG": str(log),
        **extra,
    }
    result = subprocess.run(
        ["bash", str(OFFSITE)], capture_output=True, text=True, env=env, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls, textfile / "studyaio_offsite.prom"


class TestOffsiteBackup:
    def test_stale_source_exits_2_and_never_calls_restic(self, tmp_path, tree, stubs):
        _fresh_dump(tree, age_hours=30)
        result, calls, prom = _run_offsite(tmp_path, tree, stubs)
        assert result.returncode == 2, result.stderr
        assert calls == []
        assert not prom.exists()

    def test_no_dump_at_all_exits_2(self, tmp_path, tree, stubs):
        result, calls, _ = _run_offsite(tmp_path, tree, stubs)
        assert result.returncode == 2
        assert calls == []

    @pytest.mark.parametrize("failing", ["backup", "check"])
    def test_restic_failure_is_nonzero_and_writes_no_metric(self, tmp_path, tree, stubs, failing):
        _fresh_dump(tree)
        result, _, prom = _run_offsite(tmp_path, tree, stubs, STUB_FAIL_ON=failing)
        assert result.returncode != 0
        assert not prom.exists()

    def test_success_writes_metric_and_backs_up_both_trees(self, tmp_path, tree, stubs):
        _fresh_dump(tree)
        result, calls, prom = _run_offsite(tmp_path, tree, stubs)
        assert result.returncode == 0, result.stderr
        text = prom.read_text()
        assert "studyaio_offsite_backup_last_success_timestamp_seconds " in text
        assert "studyaio_offsite_backup_duration_seconds " in text
        backup_call = next(c for c in calls if c.startswith("backup"))
        assert f"{tree}/backups" in backup_call
        assert f"{tree}/data" in backup_call
        assert any(c.startswith("check") for c in calls)

    def test_never_forgets_or_prunes(self, tmp_path, tree, stubs):
        """The repository is append-only: pruning happens on the repo host."""
        _fresh_dump(tree)
        _, calls, _ = _run_offsite(tmp_path, tree, stubs)
        assert calls
        assert not any(c.split()[0] in {"forget", "prune"} or "--prune" in c for c in calls)
        text = OFFSITE.read_text()
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        assert "forget" not in code
        assert "prune" not in code

    def test_repository_and_password_are_not_passed_as_arguments(self, tmp_path, tree, stubs):
        _fresh_dump(tree)
        result, calls, _ = _run_offsite(tmp_path, tree, stubs)
        assert result.returncode == 0
        for call in calls:
            assert "backup.invalid" not in call
            assert "--password" not in call
            assert "-r " not in call
        assert "backup.invalid" not in result.stdout + result.stderr

    def test_missing_conf_exits_1(self, tmp_path, tree, stubs):
        env = {
            "PATH": f"{stubs}:/usr/bin:/bin",
            "STUDYAIO_OFFSITE_CONF": str(tmp_path / "nope.conf"),
            "STUDYAIO_DIR": str(tree),
        }
        result = subprocess.run(["bash", str(OFFSITE)], capture_output=True, text=True, env=env)
        assert result.returncode == 1


def _run_backup(tmp_path, stubs, **extra):
    env = {
        "PATH": f"{stubs}:/usr/bin:/bin",
        "PGHOST": "db.invalid",
        "BACKUP_DIR": str(tmp_path / "out"),
        "DATA_DIR": str(tmp_path / "data"),
        **extra,
    }
    (tmp_path / "data").mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(BACKUP)], capture_output=True, text=True, env=env, timeout=60
    )


class TestBackupScript:
    def test_dump_and_archive_are_owner_only(self, tmp_path, stubs):
        result = _run_backup(tmp_path, stubs)
        assert result.returncode == 0, result.stdout + result.stderr
        files = list((tmp_path / "out").glob("studyaio_*"))
        assert files
        for f in files:
            assert stat.S_IMODE(f.stat().st_mode) == 0o600, f

    @pytest.mark.skipif(shutil.which("aws") is not None, reason="aws CLI present on this host")
    def test_s3_configured_without_aws_cli_fails(self, tmp_path, stubs):
        result = _run_backup(tmp_path, stubs, S3_BACKUP_BUCKET="bucket.invalid")
        assert result.returncode == 1
        assert "off-site upload FAILED" in result.stderr

    def test_s3_failing_upload_fails_the_run(self, tmp_path, stubs):
        _stub(stubs, "aws", "#!/usr/bin/env bash\nexit 1\n")
        result = _run_backup(tmp_path, stubs, S3_BACKUP_BUCKET="bucket.invalid")
        assert result.returncode != 0

    def test_without_s3_the_run_succeeds(self, tmp_path, stubs):
        assert _run_backup(tmp_path, stubs).returncode == 0
