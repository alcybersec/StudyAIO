"""Tests for the image-retention logic in infra/deploy/deploy.sh.

The script is bash and deploys to a real host, so the retention functions are
exercised by sourcing it (it stops after its definitions when sourced) and by
putting a fake `docker` on PATH. Nothing here touches a docker daemon.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[4] / "infra" / "deploy" / "deploy.sh"
OWNER = "acme"
API = f"ghcr.io/{OWNER}/studyaio-api"
UI = f"ghcr.io/{OWNER}/studyaio-ui"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _listing(*rows: tuple[str, str, str]) -> str:
    return "".join(f"{repo}\t{tag}\t{created}\n" for repo, tag, created in rows)


def _select(listing: str, keep: int, current: str) -> list[str]:
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{SCRIPT}"; select_stale_app_refs "$1" "$2" "$3"',
            "_",
            str(keep),
            current,
            OWNER,
        ],
        input=listing,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def _t(day: int) -> str:
    return f"2026-10-{day:02d} 10:00:00 +0000 UTC"


FIVE_RELEASES = _listing(
    (API, "eeeeeee", _t(12)),
    (UI, "eeeeeee", _t(12)),
    (API, "ddddddd", _t(11)),
    (UI, "ddddddd", _t(11)),
    (API, "ccccccc", _t(10)),
    (UI, "ccccccc", _t(10)),
    (API, "bbbbbbb", _t(9)),
    (API, "aaaaaaa", _t(8)),
    ("pgvector/pgvector", "pg16", _t(1)),
    ("redis", "7-alpine", _t(1)),
    ("ghcr.io/other/studyaio-api", "zzzzzzz", _t(1)),
)


class TestSelection:
    def test_keeps_current_and_previous_only(self):
        stale = _select(FIVE_RELEASES, 2, "eeeeeee")
        assert sorted(stale) == sorted(
            [
                f"{API}:ccccccc",
                f"{UI}:ccccccc",
                f"{API}:bbbbbbb",
                f"{API}:aaaaaaa",
            ]
        )

    def test_never_lists_non_app_images(self):
        stale = _select(FIVE_RELEASES, 1, "eeeeeee")
        assert not any(r.startswith(("pgvector", "redis", "ghcr.io/other")) for r in stale)

    def test_keep_is_configurable(self):
        stale = _select(FIVE_RELEASES, 3, "eeeeeee")
        assert sorted(stale) == sorted([f"{API}:bbbbbbb", f"{API}:aaaaaaa"])

    def test_keep_one_removes_every_other_release(self):
        stale = _select(FIVE_RELEASES, 1, "eeeeeee")
        assert not any(r.endswith(":eeeeeee") for r in stale)
        assert len(stale) == 6

    def test_current_is_kept_even_when_not_the_newest(self):
        """A redeploy of an older SHA: it is the running release, so it stays."""
        stale = _select(FIVE_RELEASES, 2, "ccccccc")
        assert f"{API}:ccccccc" not in stale
        assert f"{API}:eeeeeee" not in stale  # newest other tag = the rollback target
        assert f"{API}:ddddddd" in stale

    def test_fewer_releases_than_keep_removes_nothing(self):
        only = _listing((API, "eeeeeee", _t(12)), (UI, "eeeeeee", _t(12)))
        assert _select(only, 2, "eeeeeee") == []

    def test_empty_listing_is_fine(self):
        assert _select("", 2, "eeeeeee") == []

    def test_untagged_images_are_not_listed(self):
        rows = _listing((API, "<none>", _t(1)), (API, "eeeeeee", _t(12)))
        assert _select(rows, 1, "eeeeeee") == []


def _fake_docker(tmp_path: Path, listing: str, in_use: str) -> tuple[dict[str, str], Path]:
    """A `docker` shim on PATH that serves canned output and logs rmi/prune."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "listing").write_text(listing)
    (tmp_path / "in_use").write_text(in_use)
    log = tmp_path / "calls.log"
    shim = bin_dir / "docker"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f'case "$1" in\n'
        f'  images) cat "{tmp_path}/listing" ;;\n'
        f'  ps) cat "{tmp_path}/in_use" ;;\n'
        f'  rmi|image) echo "$@" >> "{log}" ;;\n'
        "esac\n"
    )
    shim.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}, log


class TestPrune:
    def _run(self, tmp_path, keep=2, current="eeeeeee", in_use=""):
        env, log = _fake_docker(tmp_path, FIVE_RELEASES, in_use)
        subprocess.run(
            [
                "bash",
                "-c",
                f'source "{SCRIPT}"; prune_old_app_images "$1" "$2" "$3"',
                "_",
                str(keep),
                current,
                OWNER,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return log.read_text().splitlines()

    def test_untags_stale_then_prunes_dangling_only(self, tmp_path):
        calls = self._run(tmp_path)
        assert f"rmi {API}:ccccccc" in calls
        assert f"rmi {API}:aaaaaaa" in calls
        assert calls[-1] == "image prune -f"  # dangling only: no -a, no age filter
        assert not any("pgvector" in c or "redis" in c for c in calls)

    def test_skips_images_used_by_a_container(self, tmp_path):
        calls = self._run(tmp_path, in_use=f"{API}:ccccccc\n")
        assert f"rmi {API}:ccccccc" not in calls
        assert f"rmi {API}:bbbbbbb" in calls


def test_invalid_keep_releases_is_refused():
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, "SSH_ORIGINAL_COMMAND": "abcdef1", "KEEP_RELEASES": "0"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 64
    assert "KEEP_RELEASES" in result.stderr


def test_sourcing_does_not_deploy():
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; echo sourced'], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "sourced"
