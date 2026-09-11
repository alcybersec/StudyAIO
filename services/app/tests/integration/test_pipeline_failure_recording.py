"""A pipeline stage that fails at flush time must still record and propagate (#93).

Every stage used to end its `except` block with `await session.commit()`. When
the exception came out of a flush, SQLAlchemy had already marked the session for
rollback, so that `commit()` raised `PendingRollbackError` and the `raise
IndexingError(...)` on the next line never ran. Three things followed: the
`"failed"` rows were rolled back (the artifact stuck at `"indexing"` with no
`pipeline_runs` row), `PendingRollbackError` escaped in place of the stage's
typed error, and the task's `except IndexingError: raise  # Don't retry` stopped
matching — so a deterministic failure was retried twice.

Why this suite and not `tests/unit`
-----------------------------------
The bug *is* SQLAlchemy's transaction state machine. A `MagicMock` session has
no "pending rollback" state: `mock.commit()` returns happily, the `raise` on the
next line executes, and a unit test asserting "the typed error propagates"
passes against the broken code. Only a real connection can be poisoned.

Why these tests do not use the `db_session` fixture
---------------------------------------------------
`db_session` hands out a session wrapped in an outer transaction and a SAVEPOINT.
The code under test does not take a session — each stage opens its own from
`async_session_factory` — and the thing being tested is what real `commit()` and
real `rollback()` do to it. Borrowing the fixture's connection would mean
reinterpreting both through savepoints, i.e. testing a different mechanism than
the one that broke. So these tests commit their own rows against the real engine,
exactly as the worker does, and delete them in the fixture's teardown.

How the flush failure is induced, and why this way
--------------------------------------------------
A duplicate `chunks.stable_id` was the obvious lever, and #95 removed it by
scoping the id to the artifact. Rather than reach for another uniqueness rule
that a later fix could also legitimately remove, both triggers here are
**values too long for their column** — a `varchar(n)` overflow, which Postgres
rejects at flush with `StringDataRightTruncation`:

* `index` — a `slide_title` in the extraction manifest longer than
  `chunks.slide_title`'s `varchar(500)`. `chunk_pages` copies `slide_title`
  straight from the manifest page to the `Chunk`, with no truncation or
  validation anywhere on the path, so the trigger lives entirely in this test's
  own input.
* `classify` — a `course_code` from the (stubbed) agent longer than
  `courses.code`'s `varchar(20)`, which fails in `_get_or_create_course`'s
  `flush()`.

Both are deterministic, need no concurrency, and cannot be neutralised by a fix
to some other bug. To stop them becoming silent no-ops if the schema changes,
`test_the_column_limits_these_tests_rely_on_are_real` reads the widths out of
`information_schema` and the failure assertions name the Postgres error.

Two stages, on purpose: the fix is one shared helper
(`app/pipeline/failures.record_stage_failure`), so the shared path is exercised
from two different call sites and two different kinds of failing flush.
"""

import asyncio
import hashlib
from dataclasses import dataclass

import pytest
import pytest_asyncio
import sqlalchemy

from app.agents.base import ClassificationResult
from app.agents.embeddings import EmbeddingProvider
from app.core.database import async_session_factory, engine
from app.core.exceptions import ClassificationError, IndexingError
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.extraction import Extraction
from app.models.pipeline_run import PipelineRun

# Longer than chunks.slide_title (varchar(500)) and courses.code (varchar(20)).
OVERSIZED_SLIDE_TITLE = "S" * 600
OVERSIZED_COURSE_CODE = "CSIT" + "9" * 40

# Postgres's own name for "value too long for type character varying(n)".
PG_TRUNCATION = "StringDataRightTruncation"

PAGES = [
    {
        "page_number": 1,
        "text": "Transport layer basics, flow control and congestion control.",
        "slide_title": OVERSIZED_SLIDE_TITLE,
    }
]


class _FixedEmbeddings(EmbeddingProvider):
    """No model behind it — this suite is about transactions, not vectors."""

    @property
    def dimensions(self) -> int:
        return 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]

    def preload(self) -> None:
        return None


@dataclass
class _StubAgent:
    """Just enough of the agent protocol for `_classify` to reach the database.

    Deliberately has no `refreshed_credentials` attribute: `classify` guards that
    branch with `hasattr`, and this suite has no business touching credentials.
    """

    course_code: str

    async def classify_lecture(self, **_kwargs) -> ClassificationResult:
        return ClassificationResult(
            course_code=self.course_code,
            week=1,
            title="Week 1 lecture",
            confidence=0.99,
        )


# ── Committed fixtures, cleaned up by hand ────────────────────────────


async def _delete_test_rows(artifact_id: str) -> None:
    """Undo everything these tests could have committed, innermost FK first."""
    async with async_session_factory() as session:
        for statement in (
            sqlalchemy.text("DELETE FROM chunks WHERE artifact_id = :aid"),
            sqlalchemy.text("DELETE FROM pipeline_runs WHERE artifact_id = :aid"),
            sqlalchemy.text("DELETE FROM extractions WHERE artifact_id = :aid"),
            sqlalchemy.text("UPDATE lecture_artifacts SET course_id = NULL WHERE id = :aid"),
            sqlalchemy.text("DELETE FROM lecture_artifacts WHERE id = :aid"),
        ):
            await session.execute(statement, {"aid": artifact_id})
        # Only reachable if a future change lets the oversized code through.
        await session.execute(
            sqlalchemy.text("DELETE FROM courses WHERE code = :code"),
            {"code": OVERSIZED_COURSE_CODE},
        )
        await session.commit()


async def _commit_artifact(user_id: str, *, status: str, with_extraction: bool) -> str:
    """A real, committed artifact — the state a stage actually starts from.

    Committed rather than flushed because each stage opens its own session from
    `async_session_factory`; an uncommitted row would be invisible to it.
    """
    artifact_id = generate_id()
    body = f"pipeline failure recording {artifact_id}".encode()
    async with async_session_factory() as session:
        session.add(
            LectureArtifact(
                id=artifact_id,
                user_id=user_id,
                original_filename="week1.pdf",
                file_path=f"/data/uploads/{user_id}/week1.pdf",
                file_type="pdf",
                sha256=hashlib.sha256(body).hexdigest(),
                file_size_bytes=len(body),
                status=status,
            )
        )
        if with_extraction:
            session.add(
                Extraction(
                    id=generate_id(),
                    artifact_id=artifact_id,
                    manifest_json={"pages": PAGES},
                    image_count=0,
                    page_count=len(PAGES),
                    extraction_path=f"extractions/{artifact_id}",
                )
            )
        await session.commit()
    return artifact_id


def _run_isolated(coro):
    """Drive a coroutine on a throwaway loop, leaving no pooled connection behind.

    Mirrors `app.core.database.run_async`, and for the same reason: a pooled
    asyncpg connection belongs to the event loop that opened it. The synchronous
    test below runs its setup this way, so that none of its connections can later
    be handed to the session-scoped loop the async tests share — which would
    surface as `MissingGreenlet` or "attached to a different loop", somewhere
    else entirely.
    """
    engine.sync_engine.dispose(close=False)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        engine.sync_engine.dispose(close=False)


@pytest_asyncio.fixture(loop_scope="session")
async def indexable_artifact(_run_migrations, test_user_id):
    """An artifact ready for `index`, whose manifest will break the chunk flush."""
    artifact_id = await _commit_artifact(test_user_id, status="extracted", with_extraction=True)
    try:
        yield artifact_id
    finally:
        await _delete_test_rows(artifact_id)


@pytest_asyncio.fixture(loop_scope="session")
async def classifiable_artifact(_run_migrations, test_user_id):
    """An artifact ready for `classify`, whose course code will break its flush."""
    artifact_id = await _commit_artifact(test_user_id, status="ingested", with_extraction=False)
    try:
        yield artifact_id
    finally:
        await _delete_test_rows(artifact_id)


# ── Reading back what the stage recorded ──────────────────────────────


async def _artifact_status(artifact_id: str) -> str | None:
    async with async_session_factory() as session:
        return await session.scalar(
            sqlalchemy.select(LectureArtifact.status).where(LectureArtifact.id == artifact_id)
        )


async def _runs(artifact_id: str, stage: str) -> list[PipelineRun]:
    async with async_session_factory() as session:
        rows = await session.execute(
            sqlalchemy.select(PipelineRun)
            .where(PipelineRun.artifact_id == artifact_id, PipelineRun.stage == stage)
            .order_by(PipelineRun.started_at)
        )
        return list(rows.scalars())


async def _chunk_count(artifact_id: str) -> int:
    async with async_session_factory() as session:
        return await session.scalar(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(Chunk)
            .where(Chunk.artifact_id == artifact_id)
        )


def _assert_failure_recorded(artifact_status: str | None, runs: list[PipelineRun], stage: str):
    """The two rows the stage owes an operator, and the error that explains them."""
    assert artifact_status == "failed", (
        f"the artifact is {artifact_status!r}, not 'failed'. The {stage} stage's "
        "terminal status was rolled back with the transaction, leaving the row in "
        "a non-terminal state that nothing will ever move on."
    )
    assert len(runs) == 1, (
        f"expected exactly one {stage} pipeline_runs row, got {len(runs)}. Pre-fix "
        "there are none: the run's INSERT was flushed inside the transaction the "
        "failure poisoned, so the rollback un-inserted it."
    )
    run = runs[0]
    assert run.status == "failed"
    assert run.completed_at is not None, "a terminal run needs a completed_at"
    assert run.error_message, "the run records no error, so nothing explains the failure"
    assert PG_TRUNCATION in run.error_message, (
        "the recorded error is not the varchar overflow this test induces, so the "
        f"stage failed for some other reason: {run.error_message!r}"
    )


# ── The tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
class TestColumnLimitsArePresent:
    """The premise, asserted, so neither test below can pass vacuously."""

    async def test_the_column_limits_these_tests_rely_on_are_real(self, _run_migrations):
        """`chunks.slide_title` and `courses.code` must still be bounded varchars.

        Both triggers in this file are varchar overflows. If either column is
        ever widened to `text`, the oversized value inserts cleanly, no flush
        fails, and the tests below would go green while testing nothing. This
        is what makes that loud instead of silent.
        """
        async with async_session_factory() as session:
            rows = await session.execute(
                sqlalchemy.text(
                    "SELECT table_name, column_name, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE (table_name, column_name) "
                    "IN (('chunks', 'slide_title'), ('courses', 'code'))"
                )
            )
            widths = {(t, c): n for t, c, n in rows}

        assert widths.get(("chunks", "slide_title")) == 500, (
            "chunks.slide_title is no longer varchar(500), so OVERSIZED_SLIDE_TITLE "
            f"may no longer fail the flush. Found: {widths}"
        )
        assert widths.get(("courses", "code")) == 20, (
            "courses.code is no longer varchar(20), so OVERSIZED_COURSE_CODE may no "
            f"longer fail the flush. Found: {widths}"
        )
        assert len(OVERSIZED_SLIDE_TITLE) > 500
        assert len(OVERSIZED_COURSE_CODE) > 20


@pytest.mark.asyncio(loop_scope="session")
class TestIndexStageRecordsItsFailure:
    """`index`: the stage the issue was reported against."""

    async def test_failure_is_recorded_and_the_typed_error_propagates(
        self, indexable_artifact, monkeypatch
    ):
        """Revert check — `git stash` the fix and this fails twice over:

            FAILED ... - sqlalchemy.exc.PendingRollbackError: This Session's
            transaction has been rolled back due to a previous exception during
            flush. ... (Background on this error at: ...)

        i.e. `pytest.raises(IndexingError)` sees `PendingRollbackError` instead.
        Loosen it to `pytest.raises(Exception)` and the next assertion goes too:
        the artifact reads `'indexing'`, not `'failed'`.
        """
        from app.pipeline import index

        monkeypatch.setattr(index, "get_embedding_provider", lambda: _FixedEmbeddings())

        with pytest.raises(IndexingError) as caught:
            await index._index(indexable_artifact)

        # The stage's own error type, not the transaction's complaint about it.
        assert PG_TRUNCATION in str(caught.value), (
            "IndexingError was raised but does not carry the original database "
            f"error, so the cause is lost: {caught.value}"
        )

        _assert_failure_recorded(
            await _artifact_status(indexable_artifact),
            await _runs(indexable_artifact, "index"),
            "index",
        )

    async def test_the_partial_work_is_not_committed_alongside_the_failure(
        self, indexable_artifact, monkeypatch
    ):
        """No half-indexed artifact: the rollback discards the chunks too.

        `index_artifact_chunks` deletes the artifact's existing chunks and adds
        the new ones before the flush that fails. Rolling back before recording
        the failure means neither the delete nor the inserts survive, so a
        `"failed"` artifact never has a partial chunk set attached to it.
        """
        from app.pipeline import index

        monkeypatch.setattr(index, "get_embedding_provider", lambda: _FixedEmbeddings())

        with pytest.raises(IndexingError):
            await index._index(indexable_artifact)

        assert await _chunk_count(indexable_artifact) == 0


@pytest.mark.asyncio(loop_scope="session")
class TestClassifyStageRecordsItsFailure:
    """`classify`: the same shared helper, a different stage and a different flush.

    Worth having as well as `index` because the failing flush is in a different
    place — `_get_or_create_course`, mid-stage, rather than the chunk insert —
    and because a helper used from six call sites should be proven at more than
    one of them.
    """

    async def test_failure_is_recorded_and_the_typed_error_propagates(
        self, classifiable_artifact, monkeypatch
    ):
        """Revert check — with the fix stashed:

            FAILED ... - sqlalchemy.exc.PendingRollbackError: This Session's
            transaction has been rolled back due to a previous exception during
            flush.

        and, past that, the artifact stays at `'classifying'`.
        """
        import app.services.billing_service as billing_service
        import app.services.settings_service as settings_service
        from app.pipeline import classify

        monkeypatch.setattr(classify, "_extract_text_preview", lambda *_a, **_k: "lecture text")
        monkeypatch.setattr(classify, "get_effective_setting", lambda _name: 0.5)
        monkeypatch.setattr(
            classify, "get_agent", lambda **_k: _StubAgent(course_code=OVERSIZED_COURSE_CODE)
        )

        async def _no_agent_config(*_a, **_k):
            return None

        async def _no_metering(*_a, **_k):
            return None

        monkeypatch.setattr(settings_service, "get_user_agent_config", _no_agent_config)
        monkeypatch.setattr(billing_service, "record_agent_usage", _no_metering)

        with pytest.raises(ClassificationError) as caught:
            await classify._classify(classifiable_artifact)

        assert PG_TRUNCATION in str(caught.value)

        _assert_failure_recorded(
            await _artifact_status(classifiable_artifact),
            await _runs(classifiable_artifact, "classify"),
            "classify",
        )


class TestTheTaskDoesNotRetryADeterministicFailure:
    """The consequence the issue cared about most, asserted on the Celery task.

    `index_artifact` catches `IndexingError` and re-raises it under the comment
    "Don't retry on indexing errors". Pre-fix the exception arriving there is
    `PendingRollbackError`, which that clause does not match, so control falls
    to `raise self.retry(exc=exc)` and a failure that will fail identically
    every time is retried twice.

    This test is synchronous because the task is: `index_artifact` calls
    `run_async`, which disposes the engine's pool and drives the coroutine on a
    brand-new event loop. Awaiting it from inside an async test would run the
    stage's session on a loop that is not the one the test is using.
    """

    def test_index_task_does_not_call_retry(
        self, request, _run_migrations, test_user_id, monkeypatch
    ):
        """Revert check — with the fix stashed:

            AssertionError: the task called self.retry on a deterministic
            failure. Pre-fix this is PendingRollbackError arriving at a handler
            that only matches IndexingError.

        Post-fix `retry_calls` stays empty and the task's result is the
        `IndexingError` its own handler re-raised.
        """
        from app.pipeline import index
        from app.pipeline.index import index_artifact

        # Sync test, so it owns its own row lifecycle rather than using the async
        # fixtures above — and drives it through _run_isolated so no connection
        # from this loop is left in the pool for the session loop to pick up.
        artifact_id = _run_isolated(
            _commit_artifact(test_user_id, status="extracted", with_extraction=True)
        )
        request.addfinalizer(lambda: _run_isolated(_delete_test_rows(artifact_id)))

        monkeypatch.setattr(index, "get_embedding_provider", lambda: _FixedEmbeddings())

        retry_calls: list[dict] = []

        def _record_retry(*_args, **kwargs):
            retry_calls.append(kwargs)
            # Return, not raise: `raise self.retry(...)` needs a value, and
            # raising here would be indistinguishable from the typed error.
            return RuntimeError("retry requested")

        monkeypatch.setattr(index_artifact, "retry", _record_retry)

        outcome = index_artifact.apply(args=[artifact_id], throw=False)

        assert retry_calls == [], (
            "the task called self.retry on a deterministic failure. Pre-fix this "
            "is PendingRollbackError arriving at a handler that only matches "
            f"IndexingError. Retry kwargs: {retry_calls}"
        )
        assert isinstance(outcome.result, IndexingError), (
            "the task did not fail with its own typed error, so the handler that "
            f"decides not to retry cannot have matched: {outcome.result!r}"
        )
        assert _run_isolated(_artifact_status(artifact_id)) == "failed"
