"""Pins the docs-only CI fast path in .gitlab-ci.yml (M35-D30-09).

Main and tags must never skip a gate, the three always-on jobs must carry no
docs-only condition, and every tracked file must be classified as code or docs
so a new top-level path cannot silently join the fast path.
"""

from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
CI_FILE = REPO_ROOT / ".gitlab-ci.yml"

ALWAYS_ON = ("python-lint", "secret-scan", "dependency-audit")
GATED = (
    "backend-tests",
    "summary-eval",
    "test-floor",
    "integration-tests",
    "sast",
    "frontend-checks",
    "e2e-tests",
)
# Paths under docs/ that tests parse; they must count as code.
TEST_READ_DOCS = (
    "docs/CONTRACTS.md",
    "docs/strategy.md",
    "docs/decisions.md",
    "docs/adr/0001-adopt-agentic-kit.md",
    "docs/security/threat-model.md",
)
DOCS_ONLY_PREFIX = "docs/"
DOCS_ONLY_FILES = {"README.md"}

pytestmark = pytest.mark.skipif(not CI_FILE.is_file(), reason=".gitlab-ci.yml not mounted")


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(CI_FILE.read_text())


def _changes_rule(rules: list[dict]) -> dict:
    found = [r for r in rules if "changes" in r]
    assert len(found) == 1, "expected exactly one changes rule"
    return found[0]


def _is_code(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if pat.endswith("/**/*"):
            if path.startswith(pat[: -len("**/*")]):
                return True
        elif "/" not in pat and "/" not in path and fnmatch.fnmatchcase(path, pat) or path == pat:
            return True
    return False


class TestFastPathRules:
    def test_heavy_jobs_share_the_code_rules(self, ci: dict) -> None:
        first = ci[GATED[0]]["rules"]
        for name in GATED:
            assert ci[name]["rules"] == first, name

    def test_main_and_tags_run_unconditionally(self, ci: dict) -> None:
        rules = ci[GATED[0]]["rules"]
        main = next(r for r in rules if r.get("if") == '$CI_COMMIT_BRANCH == "main"')
        tag = next(r for r in rules if r.get("if") == "$CI_COMMIT_TAG")
        for rule in (main, tag):
            assert rule["when"] == "on_success"
            assert "changes" not in rule
        # Both precede the changes rule, and only the schedule opt-out precedes them.
        idx = rules.index(main)
        assert idx < rules.index(_changes_rule(rules))
        assert all(r.get("when") == "never" and "schedule" in r["if"] for r in rules[:idx])

    def test_changes_rule_compares_to_main(self, ci: dict) -> None:
        rule = _changes_rule(ci[GATED[0]]["rules"])
        assert rule["changes"]["compare_to"] == "refs/heads/main"
        assert rule.get("when", "on_success") == "on_success"

    def test_schedules_never_run_heavy_jobs(self, ci: dict) -> None:
        for name in GATED:
            first = ci[name]["rules"][0]
            assert first["when"] == "never" and "schedule" in first["if"], name

    @pytest.mark.parametrize("name", ALWAYS_ON)
    def test_always_on_jobs_have_no_changes_condition(self, ci: dict, name: str) -> None:
        for rule in ci[name]["rules"]:
            assert "changes" not in rule, name
        assert {"when": "on_success"} in ci[name]["rules"], name

    @pytest.mark.parametrize("name", ["build-api", "build-ui", "deploy-selfhosted"])
    def test_publish_jobs_have_no_changes_condition(self, ci: dict, name: str) -> None:
        assert all("changes" not in r for r in ci[name].get("rules", [])), name


class TestClassification:
    def _patterns(self, ci: dict) -> list[str]:
        return _changes_rule(ci[GATED[0]]["rules"])["changes"]["paths"]

    @pytest.mark.parametrize("path", TEST_READ_DOCS)
    def test_docs_read_by_tests_count_as_code(self, ci: dict, path: str) -> None:
        assert _is_code(path, self._patterns(ci)), path

    def test_ordinary_docs_are_docs_only(self, ci: dict) -> None:
        patterns = self._patterns(ci)
        assert not _is_code("docs/PROGRESS.md", patterns)
        assert not _is_code("README.md", patterns)

    def test_ci_file_and_sources_are_code(self, ci: dict) -> None:
        patterns = self._patterns(ci)
        for path in (
            ".gitlab-ci.yml",
            "Makefile",
            "docker-compose.prod.yml",
            "services/app/app/main.py",
        ):
            assert _is_code(path, patterns), path

    def test_every_tracked_file_is_classified(self, ci: dict) -> None:
        if shutil.which("git") is None:
            pytest.skip("git not available")
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"], capture_output=True, text=True
        )
        if out.returncode != 0 or not out.stdout.strip():
            pytest.skip("not a git checkout")
        patterns = self._patterns(ci)
        unclassified = [
            p
            for p in out.stdout.splitlines()
            if not _is_code(p, patterns)
            and not p.startswith(DOCS_ONLY_PREFIX)
            and p not in DOCS_ONLY_FILES
        ]
        assert not unclassified, (
            f"classify these in .rules-code (code) or DOCS_ONLY_* here (docs): {unclassified}"
        )
