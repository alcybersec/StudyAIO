"""Prometheus worker metrics: increments, label policy, server gating (M32 G3)."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import Retry
from prometheus_client import REGISTRY

from app.agents.transient import TransientAgentError
from app.config import settings
from app.pipeline import backup_task, metrics, recovery, reembed_task, resilience
from app.pipeline.limits import TRANSIENT_MAX_RETRIES
from tests.unit.pipeline.test_recovery import _artifact, _factory, _session


def _val(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@contextmanager
def delta(name: str, **labels: str):
    before = _val(name, **labels)
    out = SimpleNamespace(value=0.0)
    yield out
    out.value = _val(name, **labels) - before


def _retry_task(retries: int) -> MagicMock:
    task = MagicMock()
    task.request.retries = retries
    task.retry.side_effect = lambda **kw: Retry()
    return task


class TestRetryAndFailure:
    def test_retry_counts_stage_and_error_class(self):
        with (
            patch.object(resilience, "run_async"),
            patch.object(resilience, "publish_pipeline_event_sync"),
            delta(
                "studyaio_stage_retries_total", stage="index", error_class="TransientAgentError"
            ) as d,
        ):
            with pytest.raises(Retry):
                resilience.handle_retryable(
                    _retry_task(0),
                    TransientAgentError("x"),
                    stage="index",
                    artifact_id="a",
                    event_user_id="u",
                )
        assert d.value == 1

    def test_exhausted_retries_do_not_count_a_retry(self):
        with (
            patch.object(resilience, "run_async"),
            patch.object(resilience, "publish_pipeline_event_sync"),
            delta(
                "studyaio_stage_retries_total", stage="index", error_class="TransientAgentError"
            ) as d,
        ):
            with pytest.raises(TransientAgentError):
                resilience.handle_retryable(
                    _retry_task(TRANSIENT_MAX_RETRIES),
                    TransientAgentError("x"),
                    stage="index",
                    artifact_id="a",
                    event_user_id="u",
                )
        assert d.value == 0

    @pytest.mark.parametrize(
        ("state", "outcome", "failures"), [("SUCCESS", "success", 0), ("FAILURE", "failure", 1)]
    )
    def test_stage_latency_and_failure_via_signals(self, state, outcome, failures):
        task = SimpleNamespace(name="app.pipeline.extract.extract_artifact")
        with (
            delta("studyaio_stage_duration_seconds_count", stage="extract", outcome=outcome) as n,
            delta("studyaio_stage_failures_total", stage="extract") as f,
        ):
            metrics._on_prerun(task_id="t1", task=task)
            metrics._on_postrun(task_id="t1", task=task, state=state)
        assert n.value == 1
        assert f.value == failures
        assert "t1" not in metrics._started

    def test_non_stage_task_is_not_timed(self):
        task = SimpleNamespace(name="app.pipeline.recovery.recover_stuck_artifacts")
        metrics._on_prerun(task_id="t2", task=task)
        assert "t2" not in metrics._started


class TestRecoveryMetrics:
    async def test_requeue_and_give_up_counted(self):
        arts = [_artifact("summarizing"), _artifact("indexing")]
        session = _session(arts, [0, recovery.MAX_RECOVERY_ATTEMPTS])
        with (
            delta("studyaio_stuck_artifacts_requeued_total", stage="summarize") as rq,
            delta("studyaio_stuck_artifacts_failed_total", stage="index") as fl,
            patch.object(recovery, "async_session_factory", _factory(session)),
            patch("app.pipeline.orchestrator.resume_pipeline"),
        ):
            await recovery._recover()
        assert (rq.value, fl.value) == (1, 1)

    @pytest.mark.parametrize("fail", [False, True])
    def test_run_outcome(self, fail):
        outcome = "error" if fail else "ok"
        result = {"requeued": [], "failed": []}
        with (
            delta("studyaio_recovery_runs_total", outcome=outcome) as d,
            patch.object(recovery, "_recover", new=MagicMock()),
            patch.object(
                recovery,
                "run_async",
                side_effect=RuntimeError("db") if fail else None,
                return_value=result,
            ),
        ):
            if fail:
                with pytest.raises(RuntimeError):
                    recovery.recover_stuck_artifacts.run()
            else:
                recovery.recover_stuck_artifacts.run()
        assert d.value == 1


class TestReembedMetrics:
    async def test_outcomes_counted(self):
        with (
            patch.object(reembed_task, "_artifact_page", side_effect=[["a", "b"], []]),
            patch.object(reembed_task, "async_session_factory", _factory(AsyncMock())),
            patch.object(
                reembed_task, "_reembed_artifact", side_effect=["reembedded", "skipped_fit"]
            ),
            delta("studyaio_reembed_artifacts_total", outcome="reembedded") as r,
            delta("studyaio_reembed_artifacts_total", outcome="skipped_fit") as s,
        ):
            await reembed_task.reembed_user_chunks_async("u")
        assert (r.value, s.value) == (1, 1)

    async def test_failed_counted_and_dry_run_silent(self):
        with (
            patch.object(reembed_task, "_artifact_page", side_effect=[["a"], [], ["a"], []]),
            patch.object(reembed_task, "async_session_factory", _factory(AsyncMock())),
            patch.object(
                reembed_task, "_reembed_artifact", side_effect=[RuntimeError("x"), "reembedded"]
            ),
            delta("studyaio_reembed_artifacts_total", outcome="failed") as f,
            delta("studyaio_reembed_artifacts_total", outcome="reembedded") as r,
        ):
            await reembed_task.reembed_user_chunks_async("u")
            await reembed_task.reembed_user_chunks_async("u", dry_run=True)
        assert (f.value, r.value) == (1, 0)


class TestBackupMetrics:
    def _run(self, returncode: int):
        proc = SimpleNamespace(returncode=returncode, stderr="boom", stdout="ok")
        with (
            patch.object(settings, "backup_enabled", True),
            patch("app.pipeline.backup_task.subprocess.run", return_value=proc),
        ):
            return backup_task.run_backup.run()

    def test_success_sets_outcome_duration_and_timestamp(self):
        with (
            delta("studyaio_backup_runs_total", outcome="success") as ok,
            delta("studyaio_backup_duration_seconds_count") as dur,
        ):
            self._run(0)
        assert (ok.value, dur.value) == (1, 1)
        assert _val("studyaio_backup_last_success_timestamp_seconds") > 1_700_000_000

    def test_failure_counts_once_and_keeps_old_timestamp(self):
        before = _val("studyaio_backup_last_success_timestamp_seconds")
        with (
            delta("studyaio_backup_runs_total", outcome="failure") as bad,
            delta("studyaio_backup_runs_total", outcome="error") as err,
            patch.object(backup_task.run_backup, "retry", side_effect=Retry()),
        ):
            with pytest.raises(Retry):
                self._run(1)
        assert (bad.value, err.value) == (1, 0)
        assert _val("studyaio_backup_last_success_timestamp_seconds") == before


class TestLabelPolicy:
    FORBIDDEN = {"user_id", "artifact_id", "email", "user", "token", "api_key", "key"}

    def test_no_metric_carries_an_identifier_label(self):
        found = [m for m in vars(metrics).values() if hasattr(m, "_labelnames")]
        assert len(found) == 14
        for m in found:
            assert m._name.startswith("studyaio_")
            assert not self.FORBIDDEN & set(m._labelnames), m._name


class TestServerGating:
    @pytest.mark.parametrize(
        ("port", "env", "starts"),
        [(9101, "/tmp", True), (0, "/tmp", False), (9101, None, False), (9101, "", False)],
    )
    def test_server_only_with_port_and_multiproc_dir(self, monkeypatch, port, env, starts):
        if env is None:
            monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
        else:
            monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", env)
        monkeypatch.setattr(metrics, "settings", SimpleNamespace(worker_metrics_port=port))
        with (
            patch.object(metrics, "_start_http_server") as start,
            patch.object(metrics.multiprocess, "MultiProcessCollector") as coll,
        ):
            assert metrics.start_worker_metrics_server() is starts
        assert start.called is starts
        assert coll.called is starts
        if starts:
            assert start.call_args.args[0] == port

    def test_child_shutdown_marks_process_dead_only_in_multiproc(self, monkeypatch):
        with patch.object(metrics.multiprocess, "mark_process_dead") as dead:
            monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
            metrics._on_child_shutdown(pid=42)
            dead.assert_not_called()
            monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp")
            metrics._on_child_shutdown(pid=42)
            dead.assert_called_once_with(42)

    def test_worker_ready_swallows_port_in_use(self):
        with patch.object(metrics, "start_worker_metrics_server", side_effect=OSError("in use")):
            metrics._on_worker_ready()
