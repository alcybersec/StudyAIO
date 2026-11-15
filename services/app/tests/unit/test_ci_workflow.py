"""Pins the one-pipeline-per-push workflow in .gitlab-ci.yml (M35-CI-dedup).

`workflow:rules` suppresses the branch pipeline when the branch has an open merge
request, so the merge request pipeline is the only one. That is safe only if every
job that runs on a branch pipeline also runs on a merge request pipeline, where
CI_COMMIT_BRANCH is unset. This module evaluates the real rules for each pipeline
context and fails when a job is reachable through `push` only (unless it is
main/tag/schedule-only by design), when main, tags or schedules change, or when the
dedup rule disappears.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
CI_FILE = REPO_ROOT / ".gitlab-ci.yml"

pytestmark = pytest.mark.skipif(not CI_FILE.is_file(), reason=".gitlab-ci.yml not mounted")

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
PUBLISH = ("build-api", "build-ui", "deploy-selfhosted")
MAIN_ONLY = ("credential-scope-probe",)
NIGHTLY = ("dependency-audit", "image-rescan", "renovate")
WEEKLY = ("gitleaks-history",)
NEVER_ON_BRANCHES = PUBLISH + MAIN_ONLY + NIGHTLY[1:] + WEEKLY

# Pipeline contexts: the predefined variables GitLab sets for each kind.
FEATURE_PUSH = {"CI_PIPELINE_SOURCE": "push", "CI_COMMIT_BRANCH": "task/x"}
FEATURE_PUSH_WITH_MR = {**FEATURE_PUSH, "CI_OPEN_MERGE_REQUESTS": "grp/proj!7"}
MR_EVENT = {
    "CI_PIPELINE_SOURCE": "merge_request_event",
    "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "task/x",
    "CI_MERGE_REQUEST_IID": "7",
}
MAIN_PUSH = {"CI_PIPELINE_SOURCE": "push", "CI_COMMIT_BRANCH": "main"}
TAG_PUSH = {"CI_PIPELINE_SOURCE": "push", "CI_COMMIT_TAG": "v1.2.3"}
NIGHTLY_SCHEDULE = {"CI_PIPELINE_SOURCE": "schedule", "SCHEDULE_KIND": "nightly"}
WEEKLY_SCHEDULE = {"CI_PIPELINE_SOURCE": "schedule", "SCHEDULE_KIND": "weekly"}
WEB = {"CI_PIPELINE_SOURCE": "web", "CI_COMMIT_BRANCH": "task/x"}


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(CI_FILE.read_text())


def _atom(expr: str, env: dict[str, str]) -> bool:
    expr = expr.strip()
    m = re.fullmatch(r'\$(\w+)\s*(==|!=)\s*"([^"]*)"', expr)
    if m:
        eq = env.get(m.group(1), "") == m.group(3)
        return eq if m.group(2) == "==" else not eq
    m = re.fullmatch(r"\$(\w+)\s*=~\s*/(.*)/", expr)
    if m:
        return re.search(m.group(2), env.get(m.group(1), "")) is not None
    m = re.fullmatch(r"\$(\w+)", expr)
    if m:
        return bool(env.get(m.group(1)))
    raise AssertionError(f"unsupported rule expression: {expr!r}")


def _cond(expr: str, env: dict[str, str]) -> bool:
    return any(all(_atom(a, env) for a in part.split("&&")) for part in expr.split("||"))


def _runs(rules: list[dict] | None, env: dict[str, str], changed: bool = True) -> bool:
    """First matching rule wins; `changes:` is answered by `changed`."""
    if rules is None:
        return True
    for rule in rules:
        if "if" in rule and not _cond(rule["if"], env):
            continue
        if "changes" in rule and not changed:
            continue
        return rule.get("when", "on_success") != "never"
    return False


def _job_rules(ci: dict, name: str) -> list[dict] | None:
    job = ci[name]
    if "rules" in job:
        return job["rules"]
    parent = job.get("extends")
    if isinstance(parent, str) and "rules" in ci.get(parent, {}):
        return ci[parent]["rules"]
    return None


def _jobs(ci: dict) -> list[str]:
    return [
        name
        for name, body in ci.items()
        if isinstance(body, dict)
        and not name.startswith(".")
        and ("script" in body or "extends" in body)
    ]


def _running(ci: dict, env: dict[str, str], changed: bool = True) -> set[str]:
    if not _runs(ci["workflow"]["rules"], env):
        return set()
    return {n for n in _jobs(ci) if _runs(_job_rules(ci, n), env, changed)}


class TestWorkflowRules:
    def test_workflow_rules_exist(self, ci: dict) -> None:
        assert ci["workflow"]["rules"], "workflow:rules removed: every push gets two pipelines"

    def test_merge_request_events_run(self, ci: dict) -> None:
        assert _runs(ci["workflow"]["rules"], MR_EVENT)

    def test_push_to_branch_with_open_mr_is_suppressed(self, ci: dict) -> None:
        assert not _runs(ci["workflow"]["rules"], FEATURE_PUSH_WITH_MR)

    def test_push_to_branch_without_mr_still_runs(self, ci: dict) -> None:
        assert _runs(ci["workflow"]["rules"], FEATURE_PUSH)

    @pytest.mark.parametrize(
        "env", [MAIN_PUSH, TAG_PUSH, NIGHTLY_SCHEDULE, WEEKLY_SCHEDULE, WEB], ids=str
    )
    def test_main_tags_schedules_and_manual_sources_run(self, ci: dict, env: dict) -> None:
        assert _runs(ci["workflow"]["rules"], env)

    def test_schedules_and_manual_sources_run_even_with_an_open_mr(self, ci: dict) -> None:
        for env in (NIGHTLY_SCHEDULE, WEEKLY_SCHEDULE, WEB):
            assert _runs(ci["workflow"]["rules"], {**env, "CI_OPEN_MERGE_REQUESTS": "g/p!7"})

    def test_only_the_push_source_is_ever_suppressed(self, ci: dict) -> None:
        rules = ci["workflow"]["rules"]
        suppressing = [r for r in rules if r.get("when") == "never"]
        assert suppressing, "no suppression rule"
        for rule in suppressing:
            assert '$CI_PIPELINE_SOURCE == "push"' in rule["if"]
            assert "$CI_OPEN_MERGE_REQUESTS" in rule["if"]
        assert rules[-1] == {"when": "always"}


class TestJobReachability:
    @pytest.mark.parametrize("name", ALWAYS_ON)
    @pytest.mark.parametrize("changed", [True, False])
    def test_always_on_jobs_run_in_branch_and_mr_pipelines(
        self, ci: dict, name: str, changed: bool
    ) -> None:
        assert name in _running(ci, FEATURE_PUSH, changed)
        assert name in _running(ci, MR_EVENT, changed)

    @pytest.mark.parametrize("name", GATED)
    def test_gated_jobs_follow_changes_in_mr_pipelines(self, ci: dict, name: str) -> None:
        assert name in _running(ci, MR_EVENT, changed=True)
        assert name not in _running(ci, MR_EVENT, changed=False)

    @pytest.mark.parametrize("changed", [True, False])
    def test_no_job_is_reachable_only_via_push(self, ci: dict, changed: bool) -> None:
        assert _running(ci, FEATURE_PUSH, changed) == _running(ci, MR_EVENT, changed)

    def test_docs_only_mr_runs_exactly_the_three_always_on_jobs(self, ci: dict) -> None:
        assert _running(ci, MR_EVENT, changed=False) == set(ALWAYS_ON)

    @pytest.mark.parametrize("name", NEVER_ON_BRANCHES)
    def test_main_tag_schedule_only_jobs_stay_out_of_mr_pipelines(
        self, ci: dict, name: str
    ) -> None:
        assert name not in _running(ci, MR_EVENT)
        assert name not in _running(ci, FEATURE_PUSH)

    def test_every_job_is_classified(self, ci: dict) -> None:
        known = set(ALWAYS_ON + GATED + PUBLISH + MAIN_ONLY + NIGHTLY + WEEKLY)
        assert set(_jobs(ci)) == known, "classify new jobs here: reachable from MR pipelines?"


class TestMainTagsSchedulesUnchanged:
    def test_main_runs_every_gate_and_publish_job(self, ci: dict) -> None:
        for changed in (True, False):
            running = _running(ci, MAIN_PUSH, changed)
            assert set(ALWAYS_ON + GATED + PUBLISH) <= running
            assert not set(NIGHTLY[1:] + WEEKLY) & running

    def test_v_tag_builds_and_deploys(self, ci: dict) -> None:
        running = _running(ci, TAG_PUSH, changed=False)
        assert set(ALWAYS_ON + GATED + PUBLISH) <= running

    def test_nightly_schedule_runs_only_its_jobs(self, ci: dict) -> None:
        assert _running(ci, NIGHTLY_SCHEDULE) == set(NIGHTLY)

    def test_weekly_schedule_runs_only_its_jobs(self, ci: dict) -> None:
        assert _running(ci, WEEKLY_SCHEDULE) == set(WEEKLY)

    def test_merge_request_pipeline_never_publishes(self, ci: dict) -> None:
        assert not set(PUBLISH) & _running(ci, MR_EVENT)
