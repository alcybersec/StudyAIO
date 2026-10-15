"""The targeted-generation Celery task (ADR 0007 Decision 5, pipeline.targeted_generation v1)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY
from sqlalchemy.dialects import postgresql

from app.agents.base import ExtractionData, FlashcardData, GenerationFocus, QuizQuestionData
from app.agents.transient import TransientAgentError
from app.core.exceptions import AgentError
from app.pipeline import targeted_task as tt

OWNER = "user-owner"
OTHER = "user-other"
GEN_ID = "gen-1"
SECRET_TEXT = "sk-live-0123456789 provider said no"


def _row(kind: str = "quiz", status: str = "running") -> SimpleNamespace:
    return SimpleNamespace(
        id=GEN_ID,
        user_id=OWNER,
        course_id="course-1",
        week=5,
        kind=kind,
        status=status,
        requested_count=5,
        topics=[],
    )


def _ctx(existing: list[str] | None = None) -> tt.TargetContext:
    return tt.TargetContext(
        owner_id=OWNER,
        course_code="CSIT302",
        artifact_id="art-1",
        extraction=ExtractionData(
            pages=[{"page_number": 1, "text": "x"}, {"page_number": 2, "text": "y"}],
            metadata={"course_code": "CSIT302", "week": 5},
        ),
        summary_md="# S",
        valid_pages={1, 2},
        focus=GenerationFocus(topics=["Open addressing"], page_refs=[2]),
        existing_stems=existing or [],
        next_version=3,
    )


def _quiz(question: str, page: int) -> QuizQuestionData:
    return QuizQuestionData(
        question_type="short_answer",
        question=question,
        correct_answer="a",
        explanation="e",
        source_page_ref=page,
    )


@pytest.fixture
def seams():
    """Patch every database and provider seam of ``_run``."""
    agent = MagicMock()
    agent.generate_quiz = AsyncMock(return_value=[])
    agent.generate_flashcards = AsyncMock(return_value=[])
    agent.refreshed_credentials = None
    session = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    with (
        patch.object(tt, "async_session_factory", factory),
        patch.object(tt, "_claim", new=AsyncMock(return_value=_row())) as claim,
        patch.object(tt, "_load_context", new=AsyncMock(return_value=_ctx())) as load,
        patch.object(tt, "_persist", new=AsyncMock(return_value=["i1"])) as persist,
        patch.object(tt, "_fail", new=AsyncMock()) as fail,
        patch.object(tt, "get_agent", return_value=agent) as get_agent,
        patch.object(
            tt, "get_user_ai_context", new=AsyncMock(return_value=({"k": "v"}, "ru"))
        ) as ai_context,
        patch.object(tt, "record_agent_usage", new=AsyncMock()) as usage,
    ):
        yield SimpleNamespace(
            agent=agent,
            session=session,
            claim=claim,
            load=load,
            persist=persist,
            fail=fail,
            get_agent=get_agent,
            ai_context=ai_context,
            usage=usage,
        )


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


class TestRun:
    async def test_success_drops_uncited_and_duplicates_then_persists(self, seams):
        seams.load.return_value = _ctx(existing=["What is a bucket?"])
        seams.agent.generate_quiz.return_value = [
            _quiz("What is probing?", 2),
            _quiz("What is a bucket", 1),
            _quiz("What is chaining?", 99),
        ]
        result = await tt._run(GEN_ID)
        assert result == {
            "generation_id": GEN_ID,
            "user_id": OWNER,
            "status": "completed",
            "created_count": 1,
        }
        selection = seams.persist.await_args.args[-1]
        assert [q.question for q in selection.kept] == ["What is probing?"]
        assert selection.dropped_uncited == 1 and selection.dropped_duplicate == 1
        seams.fail.assert_not_awaited()

    async def test_acts_as_the_rows_owner(self, seams):
        await tt._run(GEN_ID)
        seams.ai_context.assert_awaited_once()
        assert seams.ai_context.await_args.args[1] == OWNER
        assert seams.get_agent.call_args.kwargs == {
            "user_settings": {"k": "v"},
            "output_language": "ru",
        }
        assert seams.usage.await_args.args[1] == OWNER
        assert seams.load.await_args.args[-1].user_id == OWNER

    async def test_quiz_calls_generate_quiz_with_the_focus_and_count(self, seams):
        await tt._run(GEN_ID)
        kwargs = seams.agent.generate_quiz.await_args.kwargs
        assert kwargs["focus"] is seams.load.return_value.focus
        assert kwargs["count"] == 5 and kwargs["summary"] == "# S"
        seams.agent.generate_flashcards.assert_not_awaited()

    async def test_flashcards_call_generate_flashcards(self, seams):
        seams.claim.return_value = _row(kind="flashcards")
        seams.agent.generate_flashcards.return_value = [
            FlashcardData(front="f", back="b", source_page_ref=1)
        ]
        await tt._run(GEN_ID)
        assert seams.agent.generate_flashcards.await_args.kwargs["focus"] is not None
        seams.agent.generate_quiz.assert_not_awaited()

    async def test_usage_is_metered_even_when_everything_is_dropped(self, seams):
        seams.agent.generate_quiz.return_value = [_quiz("x y z", 99)]
        result = await tt._run(GEN_ID)
        seams.usage.assert_awaited_once()
        assert result["status"] == "completed" and result["created_count"] == 0

    async def test_a_row_that_is_not_claimable_is_skipped(self, seams):
        seams.claim.return_value = None
        result = await tt._run(GEN_ID)
        assert result["status"] == "skipped"
        seams.get_agent.assert_not_called()
        seams.persist.assert_not_awaited()

    async def test_no_source_fails_without_calling_the_model(self, seams):
        seams.load.side_effect = tt.TargetedError("no_source")
        result = await tt._run(GEN_ID)
        assert result["status"] == "failed"
        seams.fail.assert_awaited_once_with(GEN_ID, "no_source")
        seams.get_agent.assert_not_called()

    async def test_empty_model_output_fails(self, seams):
        seams.agent.generate_quiz.return_value = []
        result = await tt._run(GEN_ID)
        assert result["status"] == "failed"
        seams.fail.assert_awaited_once_with(GEN_ID, "empty_output")
        seams.persist.assert_not_awaited()

    async def test_provider_error_stores_a_code_never_the_text(self, seams):
        seams.agent.generate_quiz.side_effect = AgentError(SECRET_TEXT)
        result = await tt._run(GEN_ID)
        assert result["status"] == "failed"
        seams.fail.assert_awaited_once_with(GEN_ID, "ai_error")
        assert SECRET_TEXT not in repr(result)

    async def test_transient_error_propagates_for_a_retry(self, seams):
        seams.agent.generate_quiz.side_effect = TransientAgentError("429")
        with pytest.raises(TransientAgentError):
            await tt._run(GEN_ID)
        seams.fail.assert_not_awaited()

    async def test_persist_failure_marks_internal_error(self, seams):
        seams.persist.side_effect = RuntimeError(SECRET_TEXT)
        result = await tt._run(GEN_ID)
        assert result["status"] == "failed"
        seams.fail.assert_awaited_once_with(GEN_ID, "internal_error")

    async def test_metrics_use_only_the_allowed_labels(self, seams):
        before = _sample(
            "studyaio_targeted_generations_total",
            stage="quiz",
            outcome="completed",
            error_class="none",
        )
        items_before = _sample("studyaio_targeted_items_total", stage="quiz", outcome="created")
        await tt._run(GEN_ID)
        assert (
            _sample(
                "studyaio_targeted_generations_total",
                stage="quiz",
                outcome="completed",
                error_class="none",
            )
            == before + 1
        )
        assert _sample("studyaio_targeted_items_total", stage="quiz", outcome="created") == (
            items_before + 0
        )  # the persist seam is mocked with no kept items: nothing was created
        assert (
            _sample("studyaio_targeted_generation_seconds_count", stage="quiz", outcome="completed")
            >= 1
        )

    async def test_failure_metric_carries_the_class_name_only(self, seams):
        seams.agent.generate_quiz.side_effect = AgentError(SECRET_TEXT)
        before = _sample(
            "studyaio_targeted_generations_total",
            stage="quiz",
            outcome="failed",
            error_class="AgentError",
        )
        await tt._run(GEN_ID)
        after = _sample(
            "studyaio_targeted_generations_total",
            stage="quiz",
            outcome="failed",
            error_class="AgentError",
        )
        assert after == before + 1


def test_task_is_registered_and_bound():
    from app.worker import celery_app

    task = celery_app.tasks["app.pipeline.targeted_task.generate_targeted_items"]
    assert task.max_retries == tt.MAX_RETRIES


def test_task_in_worker_include_list():
    from app.worker import celery_app

    assert "app.pipeline.targeted_task" in celery_app.conf.include


def test_task_has_time_limits():
    from app.pipeline.limits import STAGE_TIME_LIMITS

    soft, hard = STAGE_TIME_LIMITS["app.pipeline.targeted_task.generate_targeted_items"]
    assert soft < hard


class TestTaskWrapper:
    def test_last_transient_failure_marks_the_row_failed(self):
        task = tt.generate_targeted_items
        with (
            patch.object(tt, "run_async") as run,
            patch.object(task, "retry") as retry,
        ):
            run.side_effect = [TransientAgentError("boom"), None]
            task.push_request(retries=tt.MAX_RETRIES)
            try:
                with pytest.raises(TransientAgentError):
                    task.run(GEN_ID)
            finally:
                task.pop_request()
        retry.assert_not_called()
        assert run.call_count == 2  # the run, then the failure write


def _sql(statement) -> tuple[str, dict]:
    compiled = statement.compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


class TestQueriesAreOwnerScoped:
    """Every read after the row is loaded carries the row's owner (floor 1)."""

    @pytest.mark.parametrize(
        "statement",
        [
            tt._course_stmt(OWNER, "course-1"),
            tt._artifacts_stmt(OWNER, "course-1", 5),
            tt._attempts_stmt(OWNER, "course-1", 5, datetime(2026, 9, 1, tzinfo=UTC)),
            tt._titles_stmt(OWNER, "art-1", [2]),
            tt._concepts_stmt(OWNER, "course-1", 5),
            tt._existing_stmt("quiz", OWNER, "course-1", 5),
            tt._existing_stmt("flashcards", OWNER, "course-1", 5),
            tt._summary_stmt(OWNER, "course-1", 5),
            tt._extraction_stmt(OWNER, "art-1"),
        ],
    )
    def test_the_owner_is_bound_in_the_query(self, statement):
        sql, params = _sql(statement)
        assert "user_id" in sql
        assert OWNER in params.values()
        assert OTHER not in params.values()

    def test_existing_items_exclude_archived(self):
        sql, _ = _sql(tt._existing_stmt("quiz", OWNER, "course-1", 5))
        assert "archived_at IS NULL" in sql

    def test_attempts_keep_archived_questions(self):
        sql, _ = _sql(tt._attempts_stmt(OWNER, "course-1", 5, datetime(2026, 9, 1, tzinfo=UTC)))
        assert "archived_at" not in sql


class TestRecovery:
    async def test_stuck_in_flight_rows_fail_with_a_code_and_nothing_else_changes(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["g1", "g2"]
        session.execute.return_value = result

        @asynccontextmanager
        async def factory():
            yield session

        now = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
        with patch.object(tt, "async_session_factory", factory):
            failed = await tt._recover_stuck(now=now)
        assert failed == ["g1", "g2"]
        statement = session.execute.await_args.args[0]
        sql, params = _sql(statement)
        assert sql.startswith("UPDATE targeted_generations")
        assert "status IN" in sql and "updated_at <" in sql
        assert "timeout" in params.values()
        assert "DELETE" not in sql.upper()
        session.commit.assert_awaited_once()

    def test_recovery_task_is_scheduled(self):
        from app.worker import celery_app

        tasks = {v["task"] for v in celery_app.conf.beat_schedule.values()}
        assert "app.pipeline.targeted_task.recover_stuck_generations" in tasks
        assert "app.pipeline.targeted_task.recover_stuck_generations" in celery_app.tasks

    def test_stuck_threshold_exceeds_the_hard_limit_and_backoff(self):
        from app.pipeline.limits import STAGE_TIME_LIMITS

        _, hard = STAGE_TIME_LIMITS["app.pipeline.targeted_task.generate_targeted_items"]
        retries_worst_case = (tt.MAX_RETRIES + 1) * hard + tt.MAX_RETRIES * 600
        assert tt.STUCK_GENERATION_SECONDS > retries_worst_case
