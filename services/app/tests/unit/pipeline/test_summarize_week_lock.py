"""Summarize serialises per (user, course, week) (TECH-05, GL#23)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ExtractionData, SummaryResult
from app.core.exceptions import SummarizationError
from app.core.storage import LocalStorageBackend
from app.pipeline import summarize
from app.pipeline.resilience import StageBusyError

# Captured at import: the autouse conftest fixture stubs the module attribute.
REAL_WEEK_LOCK = summarize._week_lock


class FakeAdvisoryDb:
    """Stands in for `engine`: Postgres session-level advisory lock semantics."""

    def __init__(self) -> None:
        self.held: set[str] = set()
        self.connections_open = 0

    def connect(self):
        db = self

        class _Conn:
            async def __aenter__(self_inner):
                db.connections_open += 1
                return self_inner

            async def __aexit__(self_inner, *exc):
                db.connections_open -= 1
                return False

            async def execution_options(self_inner, **kw):
                return self_inner

            async def execute(self_inner, stmt, params):
                sql = str(stmt)
                result = MagicMock()
                if "pg_try_advisory_lock" in sql:
                    free = params["k"] not in db.held
                    if free:
                        db.held.add(params["k"])
                    result.scalar.return_value = free
                else:
                    db.held.discard(params["k"])
                return result

        return _Conn()


@pytest.fixture
def db():
    fake = FakeAdvisoryDb()
    with (
        patch.object(summarize, "engine", fake),
        patch.object(summarize, "_week_lock", REAL_WEEK_LOCK),
        patch.object(summarize, "LOCK_POLL_SECONDS", 0.001),
    ):
        yield fake


class TestWeekLock:
    async def test_lock_is_released_on_exit(self, db):
        async with summarize._week_lock("u", "c", 1):
            assert len(db.held) == 1
        assert db.held == set()

    async def test_lock_is_released_when_body_raises(self, db):
        with pytest.raises(RuntimeError):
            async with summarize._week_lock("u", "c", 1):
                raise RuntimeError("boom")
        assert db.held == set()

    async def test_same_week_is_mutually_exclusive(self, db):
        inside = 0
        max_inside = 0

        async def critical() -> None:
            nonlocal inside, max_inside
            async with summarize._week_lock("u", "c", 1):
                inside += 1
                max_inside = max(max_inside, inside)
                await asyncio.sleep(0.01)
                inside -= 1

        await asyncio.gather(critical(), critical(), critical())
        assert max_inside == 1

    async def test_different_weeks_users_and_courses_do_not_block(self, db):
        async with summarize._week_lock("u", "c", 1):
            async with summarize._week_lock("u", "c", 2):
                async with summarize._week_lock("u", "c2", 1):
                    async with summarize._week_lock("u2", "c", 1):
                        assert len(db.held) == 4

    async def test_wait_budget_exhausted_raises_retryable_busy(self, db):
        with patch.object(summarize, "LOCK_WAIT_SECONDS", 0.02):
            async with summarize._week_lock("u", "c", 1):
                with pytest.raises(StageBusyError):
                    async with summarize._week_lock("u", "c", 1):
                        pytest.fail("must not enter")
        assert db.held == set()

    def test_busy_is_a_summarization_error(self):
        assert issubclass(StageBusyError, SummarizationError)


def _fake_week(shared: dict, tmp_path, artifact_ids: list[str]):
    """Mocks for N artifacts of one (course, week) racing on one shared 'DB'."""
    course = MagicMock(id="course-001", code="CSIT302")

    def make_artifact(aid: str) -> MagicMock:
        art = MagicMock()
        art.id = aid
        art.user_id = "user-1"
        art.course_id = "course-001"
        art.week = 5
        art.course = course
        return art

    artifacts = {aid: make_artifact(aid) for aid in artifact_ids}

    def session_for(aid: str) -> AsyncMock:
        session = AsyncMock()
        session.add = MagicMock()
        result = MagicMock()
        result.unique.return_value = result
        result.scalar_one_or_none.return_value = artifacts[aid]
        session.execute.return_value = result
        return session

    return artifacts, session_for


class TestConcurrentSummarize:
    async def test_two_artifacts_same_week_both_succeed_and_version_increments(self, db, tmp_path):
        shared: dict = {"summary": None}
        artifacts, session_for = _fake_week(shared, tmp_path, ["art-a", "art-b"])
        sessions = {aid: session_for(aid) for aid in artifacts}
        order = iter(["art-a", "art-b"])

        async def get_existing(session, course_id, week):
            await asyncio.sleep(0.005)  # yield: a racing run reads here too
            return shared["summary"]

        async def create_or_update(**kwargs):
            await asyncio.sleep(0.005)
            current = shared["summary"]
            if current is None:
                shared["summary"] = MagicMock(id="s1", version=1)
            else:
                if kwargs["file_path"].endswith(f"v{current.version}"):
                    raise AssertionError("version lost: overwrote a prior version")
                current.version += 1
            return shared["summary"]

        svc = MagicMock()
        svc.get_week_extractions = AsyncMock(return_value=[MagicMock()])
        svc.merge_extractions.side_effect = lambda _: ExtractionData(
            pages=[{"page_number": 1, "text": "x", "images": []}], metadata={}
        )
        svc.get_existing_summary = get_existing
        svc.create_or_update_summary = create_or_update
        svc.build_summary_storage_key.side_effect = lambda cid, week, version=1: (
            f"summaries/{cid}/Week{week}.v{version}"
        )

        agent = AsyncMock()
        agent.generate_summary.return_value = SummaryResult(content_md="# T\n", embedded_images=[])
        storage = LocalStorageBackend(base_dir=str(tmp_path))

        def factory():
            cm = MagicMock()
            aid = next(order)
            cm.__aenter__ = AsyncMock(return_value=sessions[aid])
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        with (
            patch.object(summarize, "async_session_factory", side_effect=factory),
            patch.object(summarize, "summary_service", svc),
            patch.object(summarize, "get_agent", return_value=agent),
            patch.object(summarize, "get_storage", return_value=storage),
        ):
            results = await asyncio.gather(
                summarize._summarize("art-a"), summarize._summarize("art-b")
            )

        assert [r["status"] for r in results] == ["summarized", "summarized"]
        assert sorted(r["version"] for r in results) == [1, 2]
        assert shared["summary"].version == 2
        assert db.held == set()

    async def test_without_the_lock_the_same_scenario_races(self, tmp_path):
        """Control: proves the scenario above would fail without serialisation."""
        shared = {"summary": None}

        async def run() -> None:
            await asyncio.sleep(0)
            seen = shared["summary"]
            await asyncio.sleep(0.005)
            if seen is None and shared["summary"] is not None:
                raise RuntimeError("unique violation: both created version 1")
            shared["summary"] = object()

        results = await asyncio.gather(run(), run(), return_exceptions=True)
        assert any(isinstance(r, RuntimeError) for r in results)
