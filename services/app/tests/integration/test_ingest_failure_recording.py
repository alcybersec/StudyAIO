"""An ingest failure must leave a `pipeline_runs` row behind (#103).

`ingest` built its `PipelineRun` up front but only ever `session.add`-ed it on
the success path, so a failed ingest recorded **no row at all**. The handler
logged and re-raised, which is correct transaction handling — the
commit-on-a-poisoned-session bug of #93 is genuinely absent from this stage —
but the operator-visible result was #93's: a failure with no explanation in
`pipeline_runs`, on the *first* stage, where there is least context elsewhere.

Why this suite and not `tests/unit`
-----------------------------------
The claim is about what lands in the database. `tests/unit/pipeline/test_ingest.py`
drives `_ingest` with an `AsyncMock` session, where `session.add` and
`session.commit` are recording mocks: asserting "a row was recorded" there
asserts that a mock was called, and a mock has no rollback state either, so the
poisoned-session case below cannot exist in that world at all.

What ingest can actually fail with, and what the FK allows
---------------------------------------------------------
`pipeline_runs.artifact_id` is a NOT NULL foreign key to `lecture_artifacts.id`,
so a run row cannot exist before the artifact row does. That splits ingest's
failures in two, and the split is the whole shape of the fix:

* **The artifact already exists** — every production caller. `api/uploads.py`
  commits the artifact so it can return a real id, then dispatches
  `run_pipeline(..., artifact_id=artifact.id)`; `resume_pipeline` likewise
  passes an id and no file path. Ingest adopts that row, and a failure here is
  recordable. `TestAnAdoptedArtifactRecordsItsFailure` covers it.
* **The artifact does not exist yet** — the legacy path where ingest itself
  hashes, dedups and creates. A failure before that INSERT (missing file,
  unsupported extension, storage error) has nothing to attach a run to, so the
  stage logs `ingest_failure_not_recorded` and records nothing. Pinned by
  `TestAFailureBeforeTheArtifactExists`, because "records nothing" is a
  constraint of the schema here, not an oversight to fix by reflex: the
  alternative is a run row pointing at no artifact, which needs a migration and
  means something different.

Why the adopted-path failure is injected
----------------------------------------
Once the artifact row exists, `ingest_file` only loads it — there is no file,
hash or storage work left to make fail deterministically, and the two failures
that remain in real life are a storage/filesystem error surfacing through the
service call and a database error. So these tests replace `ingest_file` with a
stub that raises what the real one raises. Everything the assertions look at is
real: a real session against a real Postgres, and the rows read back in a fresh
session afterwards.

The duplicate decision
----------------------
`TestADuplicateIsNotARun` pins it: a duplicate records no run row. It is not a
failed run and not work performed — the only artifact in play is the one
ingested earlier, and the FK would force the row onto *that* artifact, stamped
now, after its own extract/summarize/index runs, describing a re-ingest that
never happened. `pipeline_runs` is read as "what the pipeline did to this
artifact"; a phantom later ingest run would misread as exactly that. The
duplicate is already visible through the returned `"duplicate"` status, the
published event and `ingest_stage_duplicate`, and provenance for a rejected
re-upload belongs to the upload attempt rather than to the earlier artifact's
stage history. This test is here so that reversing the decision has to be
deliberate.

Why these tests do not use the `db_session` fixture
---------------------------------------------------
Same reason as `test_pipeline_failure_recording.py`: `_ingest` takes no session,
it opens its own from `async_session_factory`, and what is under test is what
real `commit()` and real `rollback()` do to it. These tests commit their own
rows against the real engine, as the worker does, and delete them afterwards.
"""

import hashlib

import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy.exc import DBAPIError

from app.core.database import async_session_factory
from app.core.exceptions import DuplicateFileError
from app.core.storage import LocalStorageBackend
from app.core.utils import compute_sha256, generate_id
from app.models.artifact import LectureArtifact
from app.models.pipeline_run import PipelineRun
from app.pipeline.ingest import _ingest
from app.services import artifact_service

# What a storage or filesystem error looks like coming out of the service call.
STORAGE_ERROR = "[Errno 5] Input/output error: uploads/lecture.pdf"

# Longer than lecture_artifacts.original_filename (varchar(500)), so the flush
# that would insert it fails with Postgres's own truncation error.
OVERSIZED_FILENAME = "L" * 600 + ".pdf"
PG_TRUNCATION = "StringDataRightTruncation"

PDF_BYTES = b"%PDF-1.4\n% ingest failure recording\n"


# ── Committed fixtures, cleaned up by hand ────────────────────────────


def _write_pdf(tmp_path, name: str = "lecture.pdf") -> tuple[str, str]:
    """Write a file into the storage root and return its key and real hash.

    The bytes carry a nonce so no two tests — and no leftover row from an
    interrupted run — can collide on `uq_artifacts_sha256_user`, which would fail
    these tests in the setup rather than in the assertion they exist for.
    """
    source = tmp_path / "uploads" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(PDF_BYTES + generate_id().encode())
    return f"uploads/{name}", compute_sha256(source)


async def _commit_artifact(user_id: str, *, sha256: str, status: str = "ingested") -> str:
    """A real, committed artifact — the state the adopting path starts from.

    Committed rather than flushed because `_ingest` opens its own session; an
    uncommitted row would be invisible to it.
    """
    artifact_id = generate_id()
    async with async_session_factory() as session:
        session.add(
            LectureArtifact(
                id=artifact_id,
                user_id=user_id,
                original_filename="lecture.pdf",
                file_path="uploads/lecture.pdf",
                file_type="pdf",
                sha256=sha256,
                file_size_bytes=len(PDF_BYTES),
                status=status,
            )
        )
        await session.commit()
    return artifact_id


async def _delete_test_rows(artifact_id: str) -> None:
    """Undo everything these tests could have committed, innermost FK first."""
    async with async_session_factory() as session:
        for statement in (
            sqlalchemy.text("DELETE FROM pipeline_runs WHERE artifact_id = :aid"),
            sqlalchemy.text("DELETE FROM lecture_artifacts WHERE id = :aid"),
        ):
            await session.execute(statement, {"aid": artifact_id})
        # Only reachable if a future change lets the oversized filename through.
        await session.execute(
            sqlalchemy.text("DELETE FROM lecture_artifacts WHERE original_filename = :name"),
            {"name": OVERSIZED_FILENAME},
        )
        await session.commit()


@pytest_asyncio.fixture(loop_scope="session")
async def adopted_artifact(_run_migrations, test_user_id):
    """The artifact the upload endpoint committed before dispatching the pipeline."""
    artifact_id = await _commit_artifact(
        test_user_id, sha256=hashlib.sha256(generate_id().encode()).hexdigest()
    )
    try:
        yield artifact_id
    finally:
        await _delete_test_rows(artifact_id)


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    """Point `artifact_service` at a real storage tree under `tmp_path`.

    The legacy path genuinely touches the filesystem — `resolve_path`, `exists`,
    `compute_sha256`, `put_file`. `settings.data_dir` defaults to `/app/data`,
    which exists inside the container and not here, so the backend is rebuilt on
    a temporary root rather than stubbed: the file operations stay real.
    """
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    monkeypatch.setattr(artifact_service, "get_storage", lambda: storage)
    return storage


# ── Reading back what the stage recorded ──────────────────────────────


async def _runs(artifact_id: str) -> list[PipelineRun]:
    async with async_session_factory() as session:
        rows = await session.execute(
            sqlalchemy.select(PipelineRun)
            .where(PipelineRun.artifact_id == artifact_id, PipelineRun.stage == "ingest")
            .order_by(PipelineRun.started_at)
        )
        return list(rows.scalars())


async def _artifact_status(artifact_id: str) -> str | None:
    async with async_session_factory() as session:
        return await session.scalar(
            sqlalchemy.select(LectureArtifact.status).where(LectureArtifact.id == artifact_id)
        )


async def _count_runs_for(artifact_id: str) -> int:
    async with async_session_factory() as session:
        return await session.scalar(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(PipelineRun)
            .where(PipelineRun.artifact_id == artifact_id)
        )


async def _count_artifacts_named(original_filename: str) -> int:
    async with async_session_factory() as session:
        return await session.scalar(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(LectureArtifact)
            .where(LectureArtifact.original_filename == original_filename)
        )


def _assert_ingest_failure_recorded(runs: list[PipelineRun], artifact_id: str, message: str):
    """The row an operator needs, and the error that explains it."""
    assert len(runs) == 1, (
        f"expected exactly one ingest pipeline_runs row, got {len(runs)}. Pre-fix "
        "there are none: the run was built but never added to the session on the "
        "failure path, so nothing in the database records that ingest ran at all."
    )
    run = runs[0]
    assert run.artifact_id == artifact_id
    assert run.status == "failed", f"the run is {run.status!r}, not 'failed'"
    assert run.completed_at is not None, "a terminal run needs a completed_at"
    assert run.duration_ms is not None, "a terminal run needs a duration_ms"
    assert run.error_message and message in run.error_message, (
        "the run does not record the error that ended the stage, so the row "
        f"explains nothing: {run.error_message!r}"
    )


# ── The tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
class TestTheSchemaTheseTestsRelyOn:
    """The premises, asserted, so nothing below can pass vacuously."""

    async def test_a_run_row_requires_an_artifact_row(self, _run_migrations):
        """`pipeline_runs.artifact_id` is a NOT NULL FK to `lecture_artifacts`.

        This is why a failure before the artifact exists records nothing. If the
        column is ever made nullable or the FK dropped, that decision should be
        revisited rather than silently inherited — so this fails loudly instead.

        Revert check — `ALTER TABLE pipeline_runs ALTER COLUMN artifact_id DROP
        NOT NULL` against the test database:

            AssertionError: pipeline_runs.artifact_id is nullable now, so a run
            row no longer needs an artifact — revisit the guard in ingest's
            failure handler.
        """
        async with async_session_factory() as session:
            nullable = await session.scalar(
                sqlalchemy.text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'pipeline_runs' AND column_name = 'artifact_id'"
                )
            )
            referenced = await session.scalar(
                sqlalchemy.text(
                    "SELECT ccu.table_name FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON kcu.constraint_name = tc.constraint_name "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "  ON ccu.constraint_name = tc.constraint_name "
                    "WHERE tc.table_name = 'pipeline_runs' "
                    "  AND tc.constraint_type = 'FOREIGN KEY' "
                    "  AND kcu.column_name = 'artifact_id'"
                )
            )

        assert nullable == "NO", (
            "pipeline_runs.artifact_id is nullable now, so a run row no longer "
            "needs an artifact — revisit the guard in ingest's failure handler."
        )
        assert referenced == "lecture_artifacts", (
            "pipeline_runs.artifact_id no longer references lecture_artifacts "
            f"(found {referenced!r}), so the constraint this suite reasons about is gone."
        )

    async def test_the_column_limit_the_poisoned_session_test_relies_on_is_real(
        self, _run_migrations
    ):
        """`lecture_artifacts.original_filename` must still be a bounded varchar.

        The poisoned-session test below induces a flush failure by overflowing
        it. Widen it to `text` and the oversized value inserts cleanly, no flush
        fails, and that test would go green while testing nothing.

        Revert check — `ALTER TABLE lecture_artifacts ALTER COLUMN
        original_filename TYPE text`:

            AssertionError: lecture_artifacts.original_filename is no longer
            varchar(500), so OVERSIZED_FILENAME may no longer fail the flush.
            Found: None

        and the poisoned-session test then fails loudly rather than vacuously
        passing: `Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>`.
        """
        async with async_session_factory() as session:
            width = await session.scalar(
                sqlalchemy.text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name = 'lecture_artifacts' "
                    "  AND column_name = 'original_filename'"
                )
            )
        assert width == 500, (
            "lecture_artifacts.original_filename is no longer varchar(500), so "
            f"OVERSIZED_FILENAME may no longer fail the flush. Found: {width}"
        )
        assert len(OVERSIZED_FILENAME) > 500


@pytest.mark.asyncio(loop_scope="session")
class TestAnAdoptedArtifactRecordsItsFailure:
    """The production shape: the artifact row exists, so the failure is recordable."""

    async def test_a_failed_ingest_records_a_failed_run_row(self, adopted_artifact, monkeypatch):
        """Revert check — drop the `record_stage_failure` call from `_ingest` and:

            AssertionError: expected exactly one ingest pipeline_runs row, got 0.
            Pre-fix there are none: the run was built but never added to the
            session on the failure path, so nothing in the database records that
            ingest ran at all.

        The `pytest.raises(OSError)` above it still passes either way — the stage
        always re-raised correctly. Only the row was missing.
        """

        async def _storage_is_broken(_session, _file_path, **_kwargs):
            raise OSError(STORAGE_ERROR)

        monkeypatch.setattr(artifact_service, "ingest_file", _storage_is_broken)

        with pytest.raises(OSError) as caught:
            await _ingest("uploads/lecture.pdf", user_id=None, artifact_id=adopted_artifact)

        assert STORAGE_ERROR in str(caught.value), (
            "the stage's own error must reach the caller unchanged; recording the "
            f"failure must not replace it: {caught.value!r}"
        )
        _assert_ingest_failure_recorded(
            await _runs(adopted_artifact), adopted_artifact, STORAGE_ERROR
        )
        assert await _artifact_status(adopted_artifact) == "failed", (
            "the artifact is not 'failed', so nothing will ever move this row on "
            "— the same half-recorded state #93 left behind."
        )

    async def test_it_is_recorded_even_when_the_failure_poisoned_the_session(
        self, adopted_artifact, test_user_id, monkeypatch
    ):
        """A flush failure marks the session for rollback; the row must still land.

        This is why ingest uses the shared helper rather than adding the run and
        committing. `ingest_file`'s own artifact INSERT and `_ingest`'s run INSERT
        are both flushes, and after either fails every further statement on that
        session — `commit()` included — raises `PendingRollbackError`. The stub
        poisons the session with the same statement the real `ingest_file` emits,
        an artifact INSERT, given a filename too long for its column.

        Revert check — replace the `record_stage_failure` call with the naive
        `session.add(run)` + `await session.commit()`:

            FAILED ... - sqlalchemy.exc.PendingRollbackError: This Session's
            transaction has been rolled back due to a previous exception during
            flush.

        i.e. `pytest.raises(OSError)` sees `PendingRollbackError` instead, and
        past that there is still no row.
        """

        async def _poison_then_fail(session, _file_path, **_kwargs):
            with pytest.raises(DBAPIError) as flush_failed:
                session.add(
                    LectureArtifact(
                        id=generate_id(),
                        user_id=test_user_id,
                        original_filename=OVERSIZED_FILENAME,
                        file_path="uploads/lecture.pdf",
                        file_type="pdf",
                        sha256=hashlib.sha256(OVERSIZED_FILENAME.encode()).hexdigest(),
                        file_size_bytes=len(PDF_BYTES),
                        status="ingested",
                    )
                )
                await session.flush()
            assert PG_TRUNCATION in str(flush_failed.value), (
                "the premise: the flush must fail with the varchar overflow, "
                f"not something else: {flush_failed.value}"
            )
            assert session.in_transaction(), "the premise: the session is not clean"
            raise OSError(STORAGE_ERROR)

        monkeypatch.setattr(artifact_service, "ingest_file", _poison_then_fail)

        with pytest.raises(OSError):
            await _ingest("uploads/lecture.pdf", user_id=None, artifact_id=adopted_artifact)

        _assert_ingest_failure_recorded(
            await _runs(adopted_artifact), adopted_artifact, STORAGE_ERROR
        )
        assert await _artifact_status(adopted_artifact) == "failed"
        assert await _count_artifacts_named(OVERSIZED_FILENAME) == 0, (
            "the half-written artifact was committed alongside the failure; the "
            "rollback is supposed to discard whatever the failed transaction left."
        )


@pytest.mark.asyncio(loop_scope="session")
class TestADuplicateIsNotARun:
    """The deliberate decision, pinned: a duplicate records no `pipeline_runs` row.

    Fully real — a real file on a real storage root, hashed by the real
    `compute_sha256`, matched against a committed artifact by the real
    `check_duplicate`. Nothing is stubbed but the storage root.
    """

    async def test_a_duplicate_records_no_pipeline_run(
        self, _run_migrations, test_user_id, local_storage, tmp_path
    ):
        """Revert check — make the `except DuplicateFileError` branch record a run
        (`session.add(run)` + `commit()`, or a call to `record_stage_failure`):

            AssertionError: a duplicate recorded 1 ingest pipeline_runs row(s) on
            the artifact that was ingested earlier. ...

        The row count fires first in both variants; the `record_stage_failure`
        variant additionally moves the earlier artifact to `"failed"`, which is
        what the last assertion here is for.
        """
        key, sha256 = _write_pdf(tmp_path)

        existing_id = await _commit_artifact(test_user_id, sha256=sha256, status="completed")
        try:
            result = await _ingest(key, user_id=test_user_id)

            assert result["status"] == "duplicate", (
                f"the premise: this file must be detected as a duplicate, got {result!r}"
            )
            assert result["artifact_id"] == existing_id

            runs = await _runs(existing_id)
            assert len(runs) == 0, (
                f"a duplicate recorded {len(runs)} ingest pipeline_runs row(s) on the "
                "artifact that was ingested earlier. A duplicate is a successful "
                "no-op, not a run: the row would be stamped now, after that "
                "artifact's own later stages, and read as a re-ingest that never "
                "happened. Reversing this decision is fine, but it needs a "
                "provenance story that is not the earlier artifact's stage history."
            )
            assert await _artifact_status(existing_id) == "completed", (
                "the earlier artifact's status was changed by someone else's duplicate upload."
            )
        finally:
            await _delete_test_rows(existing_id)


@pytest.mark.asyncio(loop_scope="session")
class TestAFailureBeforeTheArtifactExists:
    """The legacy path: no artifact row yet, so the FK leaves nowhere to record.

    Not a gap left open by accident — recording here would mean a run row that
    references no artifact, which the schema forbids. What the stage owes instead
    is to say so (`ingest_failure_not_recorded`) and to let its own error through
    unchanged, which is what these assert.
    """

    async def test_a_missing_file_records_nothing_and_keeps_its_own_error(
        self, _run_migrations, test_user_id, local_storage
    ):
        """An unreadable upload: `ingest_file` raises before it creates anything.

        Revert check — swallow the failure instead of re-raising it (replace the
        handler's `raise` with a returned `{"status": "failed"}`):

            FAILED ... - Failed: DID NOT RAISE <class 'FileNotFoundError'>

        Note what is *not* a revert check here: dropping the
        `if recordable_artifact_id:` guard and calling the helper unconditionally
        leaves both assertions passing, because the helper's INSERT violates the
        FK and it logs `pipeline_failure_not_recorded` rather than letting that
        escape. The guard buys a stated reason instead of a doomed INSERT and an
        ERROR-level traceback for an ordinary missing file; the row count cannot
        tell the two apart, and `test_a_run_row_requires_an_artifact_row` above
        is what keeps the FK — the thing that makes them equivalent — honest.
        """
        with pytest.raises(FileNotFoundError) as caught:
            await _ingest("uploads/not-there.pdf", user_id=test_user_id)

        assert "not-there.pdf" in str(caught.value), (
            f"the stage's own error must reach the caller unchanged: {caught.value!r}"
        )
        assert await _count_runs_for("pending") == 0, (
            "a run row was recorded against the 'pending' placeholder, which "
            "references no artifact — pipeline_runs.artifact_id is a FK."
        )

    async def test_an_unsupported_file_records_nothing_either(
        self, _run_migrations, test_user_id, local_storage, tmp_path
    ):
        """The other pre-INSERT failure: a real file of a type ingest will not take.

        Revert check — the same swallowed-failure mutation:

            FAILED ... - Failed: DID NOT RAISE <class 'ValueError'>

        Here to cover the second branch that raises before the artifact INSERT,
        since they are the two failures a user is most likely to reach on this
        path.
        """
        key, _sha256 = _write_pdf(tmp_path, name="notes.txt")

        with pytest.raises(ValueError, match="Unsupported file type"):
            await _ingest(key, user_id=test_user_id)

        assert await _count_runs_for("pending") == 0

    async def test_a_duplicate_of_a_real_file_still_short_circuits(
        self, _run_migrations, test_user_id, local_storage, tmp_path
    ):
        """Guard for the duplicate test's premise: `DuplicateFileError` is reachable.

        If dedup ever moves out of `ingest_file`, `TestADuplicateIsNotARun` would
        stop exercising the duplicate branch and start asserting that a
        *successful* ingest records no failure row — true, and meaningless.

        Revert check — commit the existing artifact under a different hash
        (`sha256=sha256[::-1]`), i.e. make the file no longer a duplicate:

            FAILED ... - Failed: DID NOT RAISE
            <class 'app.core.exceptions.DuplicateFileError'>
        """
        key, sha256 = _write_pdf(tmp_path)

        existing_id = await _commit_artifact(test_user_id, sha256=sha256)
        try:
            async with async_session_factory() as session:
                with pytest.raises(DuplicateFileError) as caught:
                    await artifact_service.ingest_file(session, key, user_id=test_user_id)
            assert caught.value.existing_artifact_id == existing_id
        finally:
            await _delete_test_rows(existing_id)
