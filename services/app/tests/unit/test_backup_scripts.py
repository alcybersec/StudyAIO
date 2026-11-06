"""Hermetic tests for scripts/backup.sh, offsite-backup.sh, restore.sh, restore-drill.sh.

Both are bash, so they run as subprocesses against a temp tree with stub
``restic`` / ``pg_dump`` binaries on PATH. Nothing here touches a network, a
database or a real repository.
"""

import gzip
import os
import re
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


# --------------------------------------------------------------------------- #
# restore.sh / restore-drill.sh (M35-W1-08)
# --------------------------------------------------------------------------- #

RESTORE = SCRIPTS / "restore.sh"
DRILL = SCRIPTS / "restore-drill.sh"
TS = "20260101_020000"

# A docker stand-in: logs every call, fakes the few outputs the scripts read, and
# fails the step named in STUB_FAIL ("pg_dump", "restore", "load").
DOCKER_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
all="$*"
case "$1" in
  ps) [[ -n "${STUB_STACK:-}" ]] && echo abc123; exit 0 ;;
  inspect) echo "${STUB_STACK:-}"; exit 0 ;;
  network|rm|stop) exit 0 ;;
  run)
    if [[ "$all" == *"--entrypoint tar"* ]]; then
      [[ "${STUB_EMPTY_ARCHIVE:-}" == "1" ]] && exit 0
      target="${all##*-C }"; target="${target%% *}"
      mkdir -p "${STUB_PARENT}${target#/parent}/data"
    fi
    exit 0 ;;
  exec)
    if [[ "$all" == *"count(*)"* ]]; then
      printf 'users=%s\ncourses=1\nlecture_artifacts=0\nsummaries=0\nchunks=0\n' "${STUB_USERS:-3}"
      exit 0
    fi
    if [[ "$all" == *"psql"* ]]; then
      cat >/dev/null
      if [[ "$all" == *"--single-transaction"* && "${STUB_FAIL:-}" == "load" ]]; then exit 3; fi
    fi
    exit 0 ;;
  compose)
    shift
    while [[ "${1:-}" == "-f" ]]; do shift 2; done
    case "$1" in
      config)
        if [[ "$2" == "--images" ]]; then echo "pgvector/pgvector:pg16"; echo "api:pinned"
        else printf 'db\nredis\napi\nworker\nui\n'; fi
        exit 0 ;;
      exec)
        if [[ "$all" == *"pg_dump"* ]]; then
          [[ "${STUB_FAIL:-}" == "pg_dump" ]] && exit 0
          head -c 4000 /dev/urandom | base64; exit 0
        fi
        cat >/dev/null
        [[ "${STUB_FAIL:-}" == "restore" ]] && exit 3
        exit 0 ;;
    esac
    exit 0 ;;
esac
exit 0
"""


def _code(path: Path) -> str:
    return "\n".join(ln for ln in path.read_text().splitlines() if not ln.lstrip().startswith("#"))


@pytest.fixture
def dstubs(tmp_path: Path) -> Path:
    bindir = tmp_path / "dbin"
    bindir.mkdir()
    _stub(bindir, "docker", DOCKER_STUB)
    return bindir


@pytest.fixture
def backups(tmp_path: Path) -> Path:
    """A project root with one real gzip dump, a real data archive and a data/ tree."""
    root = tmp_path / "proj"
    (root / "backups").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "data" / "keep.txt").write_text("precious")
    sql = (
        b"CREATE TABLE users (id int);\nALTER TABLE users OWNER TO studyaio;\n"
        b"--\n-- PostgreSQL database dump complete\n--\n"
    )
    (root / "backups" / f"studyaio_{TS}_db.sql.gz").write_bytes(gzip.compress(sql))
    subprocess.run(
        [
            "tar",
            "czf",
            str(root / "backups" / f"studyaio_{TS}_data.tar.gz"),
            "-C",
            str(root),
            "data",
        ],
        check=True,
    )
    return root


def _run_restore(root: Path, dstubs: Path, tmp_path: Path, *args: str, stdin=None, **extra):
    log = tmp_path / "docker.log"
    env = {
        "PATH": f"{dstubs}:/usr/bin:/bin",
        "BACKUP_DIR": str(root / "backups"),
        "DATA_DIR": str(root / "data"),
        "STUB_LOG": str(log),
        "STUB_PARENT": str(root),
        **extra,
    }
    result = subprocess.run(
        ["bash", str(RESTORE), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
        input=stdin,
        timeout=60,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


COMPOSE_ENV = {"STUDYAIO_COMPOSE_FILES": "docker-compose.yml docker-compose.prod.yml"}


class TestRestoreScript:
    def test_no_arguments_lists_backups_and_exits_1(self, backups, dstubs, tmp_path):
        result, calls = _run_restore(backups, dstubs, tmp_path)
        assert result.returncode == 1
        assert TS in result.stdout
        assert calls == []

    @pytest.mark.parametrize(
        "bad", ["latest", "2026-01-01", "20260101", "../x_020000", "20260101_02000"]
    )
    def test_bad_timestamp_exits_1_before_touching_docker(self, backups, dstubs, tmp_path, bad):
        result, calls = _run_restore(backups, dstubs, tmp_path, bad, "--yes", **COMPOSE_ENV)
        assert result.returncode == 1
        assert "timestamp must look like" in result.stderr
        assert calls == []

    def test_no_running_stack_and_no_override_exits_1_with_guidance(
        self, backups, dstubs, tmp_path
    ):
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes")
        assert result.returncode == 1
        assert "STUDYAIO_COMPOSE_FILES" in result.stderr
        assert not any(c.startswith("compose") for c in calls)

    def test_missing_dump_exits_1(self, backups, dstubs, tmp_path):
        result, _ = _run_restore(
            backups, dstubs, tmp_path, "20250101_000000", "--yes", **COMPOSE_ENV
        )
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_corrupt_dump_exits_1_before_any_compose_call(self, backups, dstubs, tmp_path):
        (backups / "backups" / f"studyaio_{TS}_db.sql.gz").write_bytes(b"not gzip at all" * 20)
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes", **COMPOSE_ENV)
        assert result.returncode == 1
        assert calls == []

    def test_dump_without_completion_trailer_exits_1_before_any_compose_call(
        self, backups, dstubs, tmp_path
    ):
        (backups / "backups" / f"studyaio_{TS}_db.sql.gz").write_bytes(
            gzip.compress(b"CREATE TABLE users (id int);\n")
        )
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes", **COMPOSE_ENV)
        assert result.returncode == 1
        assert "trailer" in result.stderr
        assert calls == []

    @pytest.mark.parametrize("bad", ["/", ".", "..", "-rf", "missing"])
    def test_bad_data_dir_exits_1_before_docker(self, backups, dstubs, tmp_path, bad):
        result, calls = _run_restore(
            backups, dstubs, tmp_path, TS, "--yes", DATA_DIR=bad, **COMPOSE_ENV
        )
        assert result.returncode == 1
        assert calls == []
        assert (backups / "data" / "keep.txt").read_text() == "precious"

    def test_data_dir_that_is_a_file_exits_1_before_docker(self, backups, dstubs, tmp_path):
        afile = backups / "afile"
        afile.write_text("x")
        result, calls = _run_restore(
            backups, dstubs, tmp_path, TS, "--yes", DATA_DIR=str(afile), **COMPOSE_ENV
        )
        assert result.returncode == 1
        assert "not a directory" in result.stderr
        assert calls == []

    def _fixed_now(self, dstubs: Path) -> str:
        _stub(
            dstubs,
            "date",
            '#!/usr/bin/env bash\n[[ "$1" == "+%Y%m%d_%H%M%S" ]] && '
            '{ echo 20261106_120000; exit 0; }\nexec /bin/date "$@"\n',
        )
        return "20261106_120000"

    def test_existing_safety_dump_is_never_overwritten(self, backups, dstubs, tmp_path):
        now = self._fixed_now(dstubs)
        pre = backups / "backups" / f"prerestore_{now}.sql.gz"
        pre.write_bytes(b"first run's only copy")
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes", **COMPOSE_ENV)
        assert result.returncode == 1
        assert "exists:" in result.stderr
        assert pre.read_bytes() == b"first run's only copy"
        assert calls == []  # refused before anything was stopped or dumped

    def test_existing_prerestore_data_tree_is_refused_before_database_is_touched(
        self, backups, dstubs, tmp_path
    ):
        now = self._fixed_now(dstubs)
        old = backups / f"data.prerestore-{now}"
        old.mkdir()
        (old / "older.txt").write_text("earlier tree")
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes", **COMPOSE_ENV)
        assert result.returncode == 1
        assert "exists:" in result.stderr
        assert (old / "older.txt").read_text() == "earlier tree"
        assert calls == []

    def test_safety_dump_goes_to_local_backups_not_backup_dir(self, backups, dstubs, tmp_path):
        fetched = tmp_path / "fetched"
        fetched.mkdir()
        for f in (backups / "backups").iterdir():
            (fetched / f.name).write_bytes(f.read_bytes())
        result, _ = _run_restore(
            backups,
            dstubs,
            tmp_path,
            TS,
            "--yes",
            BACKUP_DIR=str(fetched),
            **COMPOSE_ENV,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert list((backups / "backups").glob("prerestore_*.sql.gz"))
        assert not list(fetched.glob("prerestore_*"))

    def test_confirmation_mismatch_cancels_without_changes(self, backups, dstubs, tmp_path):
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, stdin="wrong\n", **COMPOSE_ENV)
        assert result.returncode == 0
        assert calls == []
        assert not list((backups / "backups").glob("prerestore_*"))

    def test_happy_path_order_and_flags(self, backups, dstubs, tmp_path):
        result, calls = _run_restore(backups, dstubs, tmp_path, TS, "--yes", **COMPOSE_ENV)
        assert result.returncode == 0, result.stdout + result.stderr
        joined = "\n".join(calls)
        # the stack's own compose files are used, not the bare default
        assert "compose -f docker-compose.yml -f docker-compose.prod.yml" in joined
        # safety dump written, owner-only, before the restore transaction
        pre = list((backups / "backups").glob("prerestore_*.sql.gz"))
        assert len(pre) == 1
        assert stat.S_IMODE(pre[0].stat().st_mode) == 0o600
        idx_dump = next(i for i, c in enumerate(calls) if "pg_dump" in c)
        idx_restore = next(i for i, c in enumerate(calls) if "--single-transaction" in c)
        assert idx_dump < idx_restore
        assert "ON_ERROR_STOP=1" in calls[idx_restore]
        # services stopped by name (db excluded), migrated in a one-off container
        assert any(c.endswith("stop redis api worker ui") for c in calls)
        assert any("run --rm --no-deps -T api alembic upgrade head" in c for c in calls)
        # data/ is renamed aside inside the container, never removed
        swap = "\n".join(calls)
        assert 'mv "$1" "$1.prerestore-$3"' in swap
        assert (backups / "data" / "keep.txt").read_text() == "precious"

    def test_safety_dump_failure_aborts_before_any_change(self, backups, dstubs, tmp_path):
        result, calls = _run_restore(
            backups, dstubs, tmp_path, TS, "--yes", STUB_FAIL="pg_dump", **COMPOSE_ENV
        )
        assert result.returncode == 1
        assert "Safety dump failed" in result.stderr
        assert not any("--single-transaction" in c for c in calls)
        assert not any(" stop " in c for c in calls)
        assert not list((backups / "backups").glob("prerestore_*"))

    def test_sql_error_exits_nonzero_and_data_untouched(self, backups, dstubs, tmp_path):
        result, calls = _run_restore(
            backups, dstubs, tmp_path, TS, "--yes", STUB_FAIL="restore", **COMPOSE_ENV
        )
        assert result.returncode != 0
        assert not any("prerestore-" in c for c in calls)
        assert not any("alembic" in c for c in calls)
        assert (backups / "data" / "keep.txt").read_text() == "precious"

    def test_archive_without_data_dir_aborts_before_database_is_touched(
        self, backups, dstubs, tmp_path
    ):
        result, calls = _run_restore(
            backups,
            dstubs,
            tmp_path,
            TS,
            "--yes",
            STUB_EMPTY_ARCHIVE="1",
            **COMPOSE_ENV,
        )
        assert result.returncode == 1
        assert not any(" stop " in c for c in calls)
        assert not any("--single-transaction" in c for c in calls)
        assert (backups / "data" / "keep.txt").read_text() == "precious"

    def test_schema_drop_shares_the_restore_transaction(self):
        """A failing dump must roll the DROP back too: one psql, one transaction."""
        code = _code(RESTORE)
        assert code.count("psql -v") == 1
        assert "DROP SCHEMA public CASCADE" in code
        assert "--single-transaction" in code
        assert "ON_ERROR_STOP=1" in code
        assert "|| true" not in code.replace("grep -m1 pgvector || true", "")

    def test_never_deletes_the_data_tree(self):
        """Static guard for the user-data floor.

        The only removals allowed are the half-written safety dump and the empty
        staging directory. Qa/safety may want a copy of this under tests/safety/.
        """
        code = _code(RESTORE)
        rm_lines = [
            ln.strip() for ln in code.splitlines() if re.search(r"(^|[\s;&|(])rm(dir)?\s", ln)
        ]
        assert all(
            ln.startswith('rm -f "${PRE}.partial"') or ln.startswith('rmdir "$2"')
            for ln in rm_lines
        ), rm_lines
        for banned in (
            "rm -r",
            "rm -rf",
            "rm -fr",
            "xargs rm",
            "-delete",
            "shutil",
            "--delete",
        ):
            assert banned not in code
        assert 'mv "$1" "$1.prerestore-$3"' in code


def _run_drill(tmp_path, dstubs, *args, **extra):
    log = tmp_path / "drill-docker.log"
    env = {
        "PATH": f"{dstubs}:/usr/bin:/bin",
        "STUB_LOG": str(log),
        "TEXTFILE_DIR": str(tmp_path / "no-such-dir"),
        "PG_IMAGE": "pgvector/pgvector:pg16",
        "API_IMAGE": "api:pinned",
        **extra,
    }
    result = subprocess.run(
        ["bash", str(DRILL), *args], capture_output=True, text=True, env=env, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


class TestRestoreDrill:
    def test_without_argument_exits_nonzero(self, tmp_path, dstubs):
        result, calls = _run_drill(tmp_path, dstubs)
        assert result.returncode != 0
        assert "usage" in result.stderr
        assert calls == []

    def test_missing_path_exits_1(self, tmp_path, dstubs):
        result, calls = _run_drill(tmp_path, dstubs, str(tmp_path / "nope"))
        assert result.returncode == 1
        assert calls == []

    def test_directory_without_dumps_exits_1(self, tmp_path, dstubs):
        (tmp_path / "empty").mkdir()
        result, calls = _run_drill(tmp_path, dstubs, str(tmp_path / "empty"))
        assert result.returncode == 1
        assert calls == []

    def test_bad_timestamp_exits_1(self, backups, tmp_path, dstubs):
        result, calls = _run_drill(tmp_path, dstubs, str(backups / "backups"), "latest")
        assert result.returncode == 1
        assert calls == []

    def test_corrupt_dump_exits_1_without_docker(self, backups, tmp_path, dstubs):
        (backups / "backups" / f"studyaio_{TS}_db.sql.gz").write_bytes(b"junk" * 50)
        result, calls = _run_drill(tmp_path, dstubs, str(backups / "backups"))
        assert result.returncode == 1
        assert calls == []

    def test_unknown_api_image_exits_1(self, backups, tmp_path, dstubs):
        result, calls = _run_drill(tmp_path, dstubs, str(backups / "backups"), API_IMAGE="")
        assert result.returncode == 1
        assert "api image" in result.stderr
        assert not any(c.startswith("network create") for c in calls)

    @pytest.mark.parametrize("as_file", [False, True])
    def test_success_prints_summary_line_and_cleans_up(self, backups, tmp_path, dstubs, as_file):
        dump = backups / "backups" / f"studyaio_{TS}_db.sql.gz"
        arg = str(dump if as_file else backups / "backups")
        result, calls = _run_drill(tmp_path, dstubs, arg)
        assert result.returncode == 0, result.stdout + result.stderr
        line = next(ln for ln in result.stdout.splitlines() if ln.startswith("restore_drill ok"))
        assert re.search(rf"backup={TS} users=3 data_files=\d+ load_s=\d+ total_s=\d+$", line)
        joined = "\n".join(calls)
        assert "network create --internal" in joined
        assert "--single-transaction" in joined and "ON_ERROR_STOP=1" in joined
        assert "alembic upgrade head" in joined
        assert any(c.startswith("rm -f studyaio-drill-") for c in calls)
        assert any(c.startswith("network rm studyaio-drill-") for c in calls)

    def test_load_failure_fails_the_drill_and_still_cleans_up(self, backups, tmp_path, dstubs):
        result, calls = _run_drill(tmp_path, dstubs, str(backups / "backups"), STUB_FAIL="load")
        assert result.returncode != 0
        assert "restore_drill ok" not in result.stdout
        assert any(c.startswith("rm -f studyaio-drill-") for c in calls)

    def test_empty_restore_fails_unless_allowed(self, backups, tmp_path, dstubs):
        result, _ = _run_drill(tmp_path, dstubs, str(backups / "backups"), STUB_USERS="0")
        assert result.returncode == 1
        assert "no users" in result.stderr
        allowed, _ = _run_drill(
            tmp_path,
            dstubs,
            str(backups / "backups"),
            STUB_USERS="0",
            DRILL_ALLOW_EMPTY="1",
        )
        assert allowed.returncode == 0

    def test_writes_textfile_metric_when_directory_exists(self, backups, tmp_path, dstubs):
        textfile = tmp_path / "tf"
        textfile.mkdir()
        result, _ = _run_drill(
            tmp_path, dstubs, str(backups / "backups"), TEXTFILE_DIR=str(textfile)
        )
        assert result.returncode == 0, result.stderr
        text = (textfile / "studyaio_drill.prom").read_text()
        assert "studyaio_restore_drill_last_success_timestamp_seconds " in text
        assert "studyaio_restore_drill_duration_seconds " in text

    def test_never_touches_live_stack_or_data(self):
        code = _code(DRILL)
        assert "docker compose" not in code.replace(
            "docker compose -f docker-compose.yml config --images", ""
        )
        assert "data/" not in code
        assert "rm -r" not in code
        assert "--internal" in code
