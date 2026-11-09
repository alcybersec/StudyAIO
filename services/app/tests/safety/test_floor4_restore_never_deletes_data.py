"""Floor 4 -- ``scripts/restore.sh`` never deletes ``data/`` or the database it replaces.

M35-W1-08 (audit OP-02, IN-10). ``restore.sh`` is the one operator script that
replaces live user data wholesale: the database (``DROP SCHEMA public CASCADE``
plus a load) and the ``data/`` tree (uploads, extractions, summaries). The floor
holds only if, at every point a run can stop, the state it replaced is still on
disk:

* the current database is dumped to ``prerestore_<now>.sql.gz`` first, and a
  failed, empty or truncated dump aborts before anything changes;
* the schema drop and the load are one ``psql -v ON_ERROR_STOP=1
  --single-transaction``, so a bad dump rolls the drop back too;
* the archive is extracted into a staging directory beside ``data/``, never
  into it, and the current tree is renamed aside to ``data.prerestore-<now>``;
* nothing on the data path is removed. The two removals the script has are the
  half-written safety dump and the emptied staging directory.

Two layers. The static pins read the script's code (comment lines dropped) and
fail on a new delete primitive or a reordering. The behavioural pins run the
real script against a temp project with a ``docker`` stand-in that *executes*
the two root-container steps (the ``tar`` extract and the ``sh -c`` swap) on the
host with the container paths mapped back, so the rename/rmdir logic is the one
that ships, not a mock of it. They find every original file by content anywhere
under the project root, so moving a file is fine and losing one is not.

The drill (``scripts/restore-drill.sh``) is held by
``tests/unit/test_backup_scripts.py::TestRestoreDrill``; it touches no live path.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
RESTORE = REPO / "scripts" / "restore.sh"
TS = "20260101_020000"
NOW = "20261106_120000"

# Every line of restore.sh that removes anything. Anything else that deletes is a
# floor-4 violation, wherever it points.
SANCTIONED_REMOVALS = {
    'rm -f "${PRE}.partial"',  # the half-written safety dump, before any change
    'rmdir "$2"\' sh "$NAME" "$STAGE" "$NOW"',  # emptied staging dir ($2 = STAGE)
}

# Delete primitives, by shell word. ``--rm`` (docker's auto-remove of a one-off
# container) is excluded by the lookbehind.
DELETE_PRIMITIVE = re.compile(
    r"(?<![\w-])(rm|rmdir|unlink|shred|truncate|srm|wipe)(?![\w-])"
    r"|-delete\b|--delete\b|--remove-files|--recursive-unlink|--unlink-first"
    r"|--overwrite(?:-dir)?\b|\bvolume\s+(?:rm|prune)\b|\bsystem\s+prune\b"
    r"|\bprune\b|\brsync\b|\bshutil\b|/dev/null\s*$|\bdown\b"
)


def _code_lines() -> list[str]:
    return [
        ln.strip()
        for ln in RESTORE.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _logical_lines() -> list[str]:
    """Code lines with backslash continuations joined."""
    out: list[str] = []
    buf = ""
    for ln in _code_lines():
        buf = f"{buf} {ln}" if buf else ln
        if buf.endswith("\\"):
            buf = buf[:-1].rstrip()
            continue
        out.append(buf)
        buf = ""
    return out


def _first(pattern: str) -> int:
    lines = _code_lines()
    hits = [i for i, ln in enumerate(lines) if re.search(pattern, ln)]
    assert hits, f"restore.sh has no line matching {pattern!r}"
    return hits[0]


# --------------------------------------------------------------------------- #
# Static pins
# --------------------------------------------------------------------------- #


def test_floor4_restore_has_no_delete_beyond_the_sanctioned_two():
    """No rm/find -delete/rsync --delete/tar --overwrite/volume rm/down on any path."""
    found = {ln for ln in _code_lines() if DELETE_PRIMITIVE.search(ln)}
    # ``2>/dev/null`` redirections are not deletes.
    found = {ln for ln in found if not re.fullmatch(r".*2>/dev/null.*", ln)}
    assert found <= SANCTIONED_REMOVALS, sorted(found - SANCTIONED_REMOVALS)
    # Both sanctioned removals still exist, so a reshuffle cannot hide one.
    assert set(_code_lines()) >= SANCTIONED_REMOVALS


def test_floor4_restore_extracts_only_into_staging_and_renames_live_tree_aside():
    code = "\n".join(_logical_lines())
    assert 'STAGE="${NAME}.restore-${NOW}"' in code
    extracts = [ln for ln in _logical_lines() if re.search(r"\s-x\w*f\b", ln)]
    assert extracts, "restore.sh no longer extracts the data archive"
    for ln in extracts:
        targets = re.findall(r'-C\s+("[^"]*"|\S+)', ln)
        assert targets == ['"/parent/${STAGE}"'], ln
    # The live tree is only ever the source of a rename to .prerestore-<now>.
    assert 'mv "$1" "$1.prerestore-$3"' in code
    assert code.index('mv "$1" "$1.prerestore-$3"') < code.index('mv "$2/$1" "$1"')


def test_floor4_restore_safety_dump_precedes_every_change_and_aborts_on_failure():
    lines = _code_lines()
    assert "set -euo pipefail" in lines[:3]
    dump = _first(r"pg_dump .*\$\{PRE\}\.partial")
    # The guard: pipeline failure (pipefail), a near-empty file, or a bad gzip all abort.
    guard = " ".join(lines[dump : dump + 2])
    assert guard.startswith("if !"), guard
    assert "-lt 100" in guard and '! gzip -t "${PRE}.partial"' in guard
    block = lines[dump : _first(r'^mv (-\w+ )*"\$\{PRE\}\.partial" "\$PRE"$')]
    assert "exit 1" in block, block
    for later in (
        r"config --services .*stop",  # services stopped
        r"DROP SCHEMA",  # database replaced
        r"-x\w*f",  # archive extracted
        r'mv "\$1"',  # live data/ renamed
        r"alembic upgrade head",
    ):
        assert dump < _first(later), later


def test_floor4_restore_drop_and_load_are_one_transaction():
    logical = _logical_lines()
    assert sum("psql" in ln for ln in logical) == 1
    (load,) = [ln for ln in logical if "DROP SCHEMA public CASCADE" in ln]
    assert "psql -v ON_ERROR_STOP=1 --single-transaction" in load
    assert load.index("DROP SCHEMA") < load.index('gunzip -c "$DB_DUMP"')
    assert load.index('gunzip -c "$DB_DUMP"') < load.index("psql")
    code = "\n".join(logical)
    for weakener in ("set +e", "set +o pipefail", "|| :", "ON_ERROR_STOP=0"):
        assert weakener not in code, weakener
    assert "|| true" not in code.replace("grep -m1 pgvector || true", "")


# --------------------------------------------------------------------------- #
# Behavioural pins
# --------------------------------------------------------------------------- #

DOCKER = r'''#!__PY__
"""docker stand-in: logs calls; runs the root-container tar/sh steps on the host."""
import os, subprocess, sys

argv = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(" ".join(argv) + "\n")
fail = os.environ.get("STUB_FAIL", "")

if argv[0] == "compose":
    rest = argv[1:]
    while rest and rest[0] == "-f":
        rest = rest[2:]
    joined = " ".join(rest)
    if rest[:2] == ["config", "--images"]:
        print("pgvector/pgvector:pg16")
    elif rest[:2] == ["config", "--services"]:
        print("db\napi\nworker")
    elif "pg_dump" in joined:
        if fail == "dump_empty":
            sys.exit(0)
        if fail == "dump_race":  # another run's dump lands while this one dumps
            with open(os.environ["STUB_RACE"], "wb") as racer:
                racer.write(b"RACER")
        sys.stdout.write("-- PostgreSQL database dump\n-- " + os.urandom(512).hex() + "\n")
        sys.stdout.flush()
        sys.exit(2 if fail == "dump_exit" else 0)
    elif "psql" in joined:
        with open(os.environ["STUB_SQL"], "ab") as sql:
            sql.write(sys.stdin.buffer.read())
        sys.exit(3 if fail == "load" else 0)
    sys.exit(0)

if argv[0] == "run":
    rest, mounts, entry = argv[1:], {}, None
    while rest[0].startswith("-"):
        opt = rest.pop(0)
        if opt == "--rm":
            continue
        val = rest.pop(0)
        if opt == "-v":
            host, ctr = val.split(":")[:2]
            mounts[ctr] = host
        elif opt == "--entrypoint":
            entry = val
    rest = rest[1:]  # image

    def m(s):
        for ctr, host in mounts.items():
            s = s.replace(ctr, host)
        return s

    sys.exit(subprocess.run([entry, *[m(a) for a in rest]]).returncode)
sys.exit(0)
'''

DATE = f"""#!/bin/sh
[ "$1" = "+%Y%m%d_%H%M%S" ] && {{ echo {NOW}; exit 0; }}
exec /bin/date "$@"
"""


def _exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project root: a live data/ tree, and a backup whose data/ differs."""
    root = tmp_path / "proj"
    (root / "backups").mkdir(parents=True)
    src = tmp_path / "archived"
    for base, tag in ((root, "live"), (src, "archived")):
        (base / "data" / "uploads" / "u1").mkdir(parents=True)
        (base / "data" / "summaries").mkdir()
        (base / "data" / "uploads" / "u1" / "lecture.pdf").write_text(f"{tag}-upload")
        (base / "data" / "summaries" / "w1.md").write_text(f"{tag}-summary")
    dump = b"CREATE TABLE users (id int);\n-- PostgreSQL database dump complete\n"
    (root / "backups" / f"studyaio_{TS}_db.sql.gz").write_bytes(gzip.compress(dump))
    tar = root / "backups" / f"studyaio_{TS}_data.tar.gz"
    subprocess.run(["tar", "czf", str(tar), "-C", str(src), "data"], check=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _exe(bindir / "docker", DOCKER.replace("__PY__", sys.executable))
    _exe(bindir / "date", DATE)
    return root


def _restore(root: Path, **env: str) -> subprocess.CompletedProcess:
    full = {
        "PATH": f"{root.parent / 'bin'}:/usr/bin:/bin",
        "BACKUP_DIR": str(root / "backups"),
        "DATA_DIR": str(root / "data"),
        "STUDYAIO_COMPOSE_FILES": "docker-compose.yml docker-compose.prod.yml",
        "STUB_LOG": str(root.parent / "docker.log"),
        "STUB_SQL": str(root.parent / "load.sql"),
        **env,
    }
    return subprocess.run(
        ["bash", str(RESTORE), TS, "--yes"],
        cwd=root,
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _contents(root: Path) -> dict[bytes, list[str]]:
    """Every file under ``root`` by content digest (location-agnostic)."""
    out: dict[bytes, list[str]] = {}
    for dirpath, _, files in os.walk(root):
        for name in files:
            p = Path(dirpath, name)
            out.setdefault(hashlib.sha256(p.read_bytes()).digest(), []).append(
                str(p.relative_to(root))
            )
    return out


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _calls(root: Path) -> str:
    log = root.parent / "docker.log"  # absent when the run never reached docker
    return log.read_text() if log.exists() else ""


def test_floor4_restore_keeps_every_live_file_and_swaps_in_the_backup(project):
    before = _contents(project / "data")
    result = _restore(project)
    assert result.returncode == 0, result.stdout + result.stderr
    after = _contents(project)
    lost = [paths for digest, paths in before.items() if digest not in after]
    assert not lost, lost
    assert (project / f"data.prerestore-{NOW}/uploads/u1/lecture.pdf").read_text() == (
        "live-upload"
    )
    assert (project / "data/uploads/u1/lecture.pdf").read_text() == "archived-upload"
    assert not (project / f"data.restore-{NOW}").exists()
    pre = project / "backups" / f"prerestore_{NOW}.sql.gz"
    assert gzip.decompress(pre.read_bytes()).startswith(b"-- PostgreSQL database dump")
    sql = (project.parent / "load.sql").read_bytes()
    assert sql.startswith(b"DROP SCHEMA public CASCADE; CREATE SCHEMA public;\n")


@pytest.mark.parametrize("fail", ["dump_empty", "dump_exit"])
def test_floor4_restore_failed_safety_dump_changes_nothing(project, fail):
    before = _snapshot(project)
    result = _restore(project, STUB_FAIL=fail)
    assert result.returncode == 1
    assert "Safety dump failed" in result.stderr
    calls = _calls(project)
    assert "psql" not in calls and " stop " not in calls
    assert _snapshot(project) == before  # no staging, no prerestore file, data/ as was


def test_floor4_restore_failed_load_leaves_live_data_in_place(project):
    before = _snapshot(project / "data")
    result = _restore(project, STUB_FAIL="load")
    assert result.returncode != 0
    assert _snapshot(project / "data") == before
    assert "prerestore-" not in _calls(project)
    assert (project / "backups" / f"prerestore_{NOW}.sql.gz").is_file()


def test_floor4_restore_with_an_existing_prerestore_tree_loses_neither(project):
    """``data.prerestore-<now>`` already there (clock reset, a same-second rerun)."""
    old = project / f"data.prerestore-{NOW}"
    (old / "uploads").mkdir(parents=True)
    (old / "uploads" / "older.pdf").write_text("older-generation-upload")
    before_tree = _snapshot(project)
    before = _contents(project / "data") | _contents(old)
    result = _restore(project)
    after = _contents(project)
    lost = [paths for digest, paths in before.items() if digest not in after]
    assert not lost, lost
    # Since e83851f the run refuses up front: nothing dumped, stopped or loaded.
    assert result.returncode == 1
    assert "exists:" in result.stderr
    assert _snapshot(project) == before_tree
    assert "psql" not in _calls(project) and " stop " not in _calls(project)


def test_floor4_restore_rerun_with_same_timestamp_keeps_first_safety_dump(project):
    """Two runs that compute the same <now> must not overwrite the first safety dump.

    The first run's ``prerestore_<now>.sql.gz`` is the only copy of the database as
    it was before any restore. A second run with the same ``<now>`` (clock stepped
    back by NTP or a VM snapshot revert, or two operators starting together) would
    dump the already-restored database and rename it over the first (V1, fixed in
    e83851f).
    """
    first = _restore(project)
    assert first.returncode == 0, first.stderr
    pre = project / "backups" / f"prerestore_{NOW}.sql.gz"
    pre.write_bytes(gzip.compress(b"-- PostgreSQL database dump\nORIGINAL STATE\n"))
    original = pre.read_bytes()
    # The operator has already moved the old tree away, so only the dump check stands.
    (project / f"data.prerestore-{NOW}").rename(project.parent / "verified-old-tree")
    (project.parent / "load.sql").unlink()
    second = _restore(project)
    assert second.returncode == 1
    assert pre.read_bytes() == original, "the first run's safety dump was overwritten"
    assert not (project.parent / "load.sql").exists()  # nothing was loaded


def test_floor4_restore_safety_dump_landing_mid_run_is_not_overwritten(project):
    """The up-front check passes, then another run's dump appears before the rename."""
    pre = project / "backups" / f"prerestore_{NOW}.sql.gz"
    result = _restore(project, STUB_FAIL="dump_race", STUB_RACE=str(pre))
    assert result.returncode == 1
    assert pre.read_bytes() == b"RACER"
    assert "psql" not in _calls(project) and " stop " not in _calls(project)
    assert not (project / f"data.restore-{NOW}").exists()
