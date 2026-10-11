"""Retry/backoff/time-limit policy (TECH-04, GL#22)."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded

from app.agents.transient import TransientAgentError
from app.core.exceptions import AgentError, SummarizationError
from app.pipeline import resilience
from app.pipeline.limits import (
    BACKOFF_CAP_SECONDS,
    STAGE_TIME_LIMITS,
    STUCK_THRESHOLD_SECONDS,
    TRANSIENT_MAX_RETRIES,
)


class TestClassification:
    def test_transient_agent_error_is_retryable(self):
        assert resilience.is_retryable(TransientAgentError("429"))

    def test_stage_busy_and_soft_limit_are_retryable(self):
        assert resilience.is_retryable(resilience.StageBusyError("busy"))
        assert resilience.is_retryable(SoftTimeLimitExceeded())

    @pytest.mark.parametrize("exc", [AgentError("401"), SummarizationError("x"), ValueError()])
    def test_permanent_errors_are_not_retryable(self, exc):
        assert not resilience.is_retryable(exc)


class TestBackoff:
    def test_grows_exponentially_with_jitter_bounds(self):
        for retries in range(4):
            full = min(BACKOFF_CAP_SECONDS, 30 * 2**retries)
            for _ in range(50):
                assert full // 2 <= resilience.backoff_countdown(retries) <= full

    def test_is_capped(self):
        assert resilience.backoff_countdown(20) <= BACKOFF_CAP_SECONDS

    def test_jitter_varies(self):
        assert len({resilience.backoff_countdown(3) for _ in range(40)}) > 1


def _task(retries: int) -> MagicMock:
    task = MagicMock()
    task.request.retries = retries
    task.retry.side_effect = lambda **kw: Retry()
    return task


@pytest.fixture
def side_effects():
    with (
        patch.object(resilience, "run_async") as run_async,
        patch.object(resilience, "record_stage_event", new=MagicMock()) as event,
        patch.object(resilience, "publish_pipeline_event_sync") as publish,
    ):
        yield run_async, event, publish


class TestHandleRetryable:
    def test_transient_error_retries_with_backoff(self, side_effects):
        task = _task(retries=1)
        with pytest.raises(Retry):
            resilience.handle_retryable(
                task,
                TransientAgentError("503"),
                stage="summarize",
                artifact_id="a",
                event_user_id="u",
            )
        kwargs = task.retry.call_args.kwargs
        assert kwargs["max_retries"] == TRANSIENT_MAX_RETRIES
        assert 30 <= kwargs["countdown"] <= 60
        assert side_effects[2].call_args.args[2] == "retrying"

    def test_retry_count_is_bounded_then_artifact_fails_visibly(self, side_effects):
        task = _task(retries=TRANSIENT_MAX_RETRIES)
        err = TransientAgentError("503")
        with pytest.raises(TransientAgentError):
            resilience.handle_retryable(
                task, err, stage="summarize", artifact_id="a", event_user_id="u"
            )
        task.retry.assert_not_called()
        args = side_effects[1].call_args
        assert args.args[:3] == ("a", "summarize", "failed")
        assert args.kwargs["artifact_status"] == "failed"
        assert side_effects[2].call_args.args[2] == "failed"

    def test_time_limit_records_run_and_retries(self, side_effects):
        task = _task(retries=0)
        with pytest.raises(Retry):
            resilience.handle_retryable(
                task,
                SoftTimeLimitExceeded(),
                stage="classify",
                artifact_id="a",
                event_user_id=None,
            )
        assert "time limit" in side_effects[1].call_args.args[3]
        assert side_effects[1].call_args.args[2] == "failed"
        assert resilience.METRICS["pipeline_stage_timeouts_total|stage=classify"] >= 1


class TestTimeLimits:
    def test_every_stage_has_ordered_limits(self):
        assert len(STAGE_TIME_LIMITS) == 6
        for soft, hard in STAGE_TIME_LIMITS.values():
            assert 0 < soft < hard

    def test_limits_applied_to_celery_app(self):
        from app.worker import celery_app

        ann = celery_app.conf.task_annotations
        assert ann["app.pipeline.summarize.summarize_artifact"]["soft_time_limit"] > 600
        assert set(ann) == set(STAGE_TIME_LIMITS)

    def test_summarize_soft_limit_exceeds_longest_ai_call_plus_lock_wait(self):
        from app.pipeline.summarize import LOCK_WAIT_SECONDS

        soft = STAGE_TIME_LIMITS["app.pipeline.summarize.summarize_artifact"][0]
        assert soft > LOCK_WAIT_SECONDS + 600  # claude_code _SUMMARY_TIMEOUT = 600

    def test_stuck_threshold_exceeds_hard_limits_and_backoff(self):
        longest = max(hard for _, hard in STAGE_TIME_LIMITS.values())
        assert longest + BACKOFF_CAP_SECONDS < STUCK_THRESHOLD_SECONDS


class TestTaskWiring:
    """The three AI stages hand retryable errors to handle_retryable."""

    @pytest.mark.parametrize(
        ("module", "task", "stage"),
        [
            ("summarize", "summarize_artifact", "summarize"),
            ("classify", "classify_artifact", "classify"),
            ("assets", "generate_assets", "assets"),
        ],
    )
    def test_transient_error_triggers_retry(self, module, task, stage):
        mod = importlib.import_module(f"app.pipeline.{module}")
        celery_task = getattr(mod, task)

        def boom(coro):
            coro.close()
            raise TransientAgentError("429")

        with (
            patch.object(mod, "run_async", side_effect=boom),
            patch.object(mod, "publish_pipeline_event_sync"),
            patch.object(mod, "resolve_event_owner", return_value="u"),
            patch.object(mod, "handle_retryable", side_effect=Retry()) as handler,
            pytest.raises(Retry),
        ):
            celery_task.run({"artifact_id": "a", "user_id": "u"})
        assert handler.call_args.kwargs["stage"] == stage

    def test_permanent_agent_error_fails_fast(self):
        from app.pipeline import summarize

        def boom(coro):
            coro.close()
            raise AgentError("401 revoked")

        with (
            patch.object(summarize, "run_async", side_effect=boom),
            patch.object(summarize, "publish_pipeline_event_sync") as publish,
            patch.object(summarize, "resolve_event_owner", return_value="u"),
            patch.object(summarize, "handle_retryable") as handler,
            pytest.raises(AgentError),
        ):
            summarize.summarize_artifact.run({"artifact_id": "a", "user_id": "u"})
        handler.assert_not_called()
        assert publish.call_args.args[2] == "failed"
