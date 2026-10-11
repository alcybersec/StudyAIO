"""Stuck-artifact recovery beat job (TECH-04, GL#22)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline import recovery
from app.pipeline.limits import STUCK_THRESHOLD_SECONDS

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def _artifact(status: str, idle_minutes: int = 90) -> MagicMock:
    art = MagicMock()
    art.id = f"art-{status}"
    art.user_id = "user-1"
    art.status = status
    art.updated_at = NOW - timedelta(minutes=idle_minutes)
    return art


def _session(artifacts: list[MagicMock], attempts: list[int]) -> AsyncMock:
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = artifacts
    count_results = []
    for n in attempts:
        r = MagicMock()
        r.scalar_one.return_value = n
        count_results.append(r)
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [select_result, *count_results]
    return session


def _factory(session: AsyncMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


async def _run(session: AsyncMock) -> tuple[dict, MagicMock]:
    with (
        patch.object(recovery, "async_session_factory", _factory(session)),
        patch("app.pipeline.orchestrator.resume_pipeline") as resume,
    ):
        result = await recovery._recover(now=NOW)
    return result, resume


class TestRecovery:
    async def test_stuck_artifact_is_requeued_from_its_stage(self):
        art = _artifact("summarizing")
        session = _session([art], [0])
        result, resume = await _run(session)

        assert result == {"requeued": [art.id], "failed": []}
        resume.assert_called_once_with(art.id, from_stage="summarize", user_id="user-1")
        run = session.add.call_args.args[0]
        assert run.stage == "recovery"
        assert run.status == "recovered"
        assert "attempt 1/3" in run.error_message
        # Pushed forward so the next tick does not re-pick it.
        assert art.updated_at == NOW
        assert art.status == "summarizing"
        session.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        ("status", "stage"),
        [
            ("classifying", "classify"),
            ("extracting", "extract"),
            ("indexing", "index"),
            ("generating_assets", "assets"),
        ],
    )
    async def test_every_in_progress_status_maps_to_a_stage(self, status, stage):
        _, resume = await _run(_session([_artifact(status)], [0]))
        assert resume.call_args.kwargs["from_stage"] == stage

    async def test_attempts_are_bounded_then_artifact_fails_visibly(self):
        art = _artifact("indexing")
        session = _session([art], [recovery.MAX_RECOVERY_ATTEMPTS])
        result, resume = await _run(session)

        assert result == {"requeued": [], "failed": [art.id]}
        resume.assert_not_called()
        assert art.status == "failed"
        run = session.add.call_args.args[0]
        assert (run.stage, run.status) == ("recovery", "failed")
        assert "gave up" in run.error_message

    async def test_nothing_stuck_is_a_noop(self):
        session = _session([], [])
        result, resume = await _run(session)
        assert result == {"requeued": [], "failed": []}
        resume.assert_not_called()

    async def test_dispatch_failure_does_not_abort_the_batch(self):
        arts = [_artifact("classifying"), _artifact("indexing")]
        session = _session(arts, [0, 0])
        with (
            patch.object(recovery, "async_session_factory", _factory(session)),
            patch(
                "app.pipeline.orchestrator.resume_pipeline",
                side_effect=[RuntimeError("broker down"), None],
            ) as resume,
        ):
            result = await recovery._recover(now=NOW)
        assert len(result["requeued"]) == 2
        assert resume.call_count == 2

    async def test_query_uses_the_threshold_and_skip_locked(self):
        session = _session([], [])
        await _run(session)
        from sqlalchemy.dialects import postgresql

        stmt = str(session.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE SKIP LOCKED" in stmt
        assert "updated_at <" in stmt

    def test_threshold_exceeds_longest_stage_limit(self):
        from app.pipeline.limits import STAGE_TIME_LIMITS

        assert max(h for _, h in STAGE_TIME_LIMITS.values()) < STUCK_THRESHOLD_SECONDS


class TestSchedule:
    def test_recovery_is_in_the_beat_schedule(self):
        from app.worker import celery_app

        entry = celery_app.conf.beat_schedule["recover-stuck-artifacts"]
        assert entry["task"] == "app.pipeline.recovery.recover_stuck_artifacts"

    def test_task_runs_recover_and_returns_result(self):
        def fake_run_async(coro):
            coro.close()
            return {"requeued": ["a"], "failed": []}

        with patch.object(recovery, "run_async", side_effect=fake_run_async):
            out = recovery.recover_stuck_artifacts.run()
        assert out["requeued"] == ["a"]
