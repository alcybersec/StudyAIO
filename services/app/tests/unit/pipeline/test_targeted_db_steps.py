"""The database steps of the targeted task, against a scripted session."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import FlashcardData, GenerationFocus, QuizQuestionData
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.pipeline import targeted_task as tt
from app.pipeline.targeted_items import Selection

OWNER = "owner-1"
NOW = datetime.now(UTC)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def all(self):
        return self.value

    def scalars(self):
        return iter(self.value)


def _session(*results):
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(side_effect=[_Result(r) for r in results])
    return session


def _gen(kind: str = "quiz", status: str = "running") -> SimpleNamespace:
    return SimpleNamespace(
        id="g1",
        user_id=OWNER,
        course_id="c1",
        week=5,
        kind=kind,
        status=status,
        requested_count=5,
        topics=[],
        created_count=0,
        dropped_duplicate_count=0,
        dropped_uncited_count=0,
        error_code="x",
        completed_at=None,
    )


class TestClaim:
    async def test_marks_a_queued_row_running(self):
        row = _gen(status="queued")
        session = _session(row)
        assert await tt._claim(session, "g1") is row
        assert row.status == "running"
        session.commit.assert_awaited_once()

    async def test_a_running_row_is_claimable_for_a_retry(self):
        assert await tt._claim(_session(_gen(status="running")), "g1") is not None

    @pytest.mark.parametrize("status", ["completed", "failed"])
    async def test_a_finished_row_is_not_claimed(self, status):
        session = _session(_gen(status=status))
        assert await tt._claim(session, "g1") is None
        session.commit.assert_not_awaited()

    async def test_an_unknown_id_is_not_claimed(self):
        assert await tt._claim(_session(None), "nope") is None


def _attempt_row(qid, artifact, stem, page, correct, days_ago):
    return (qid, artifact, stem, page, correct, NOW - timedelta(days=days_ago))


class TestLoadContext:
    async def test_builds_the_focus_from_missed_questions_titles_and_concepts(self):
        extraction = SimpleNamespace(
            artifact_id="a2",
            manifest_json={
                "pages": [
                    {"page_number": 1, "text": "one"},
                    {"page_number": 2, "text": "two"},
                ]
            },
        )
        session = _session(
            "CSIT302",  # course code
            [("a1", NOW - timedelta(days=9)), ("a2", NOW - timedelta(days=2))],  # artifacts
            [
                _attempt_row("q1", "a2", "Why probing?", 2, False, 3),
                _attempt_row("q2", "a1", "Old miss?", 7, False, 4),
                _attempt_row("q3", "a2", "Fine?", 1, True, 1),
            ],
            extraction,
            "# Summary",
            [(2, "Open addressing")],  # titles at the missed pages
            ["Load factor", "open addressing"],  # concepts
            [("What is X?", 2), ("What is Y?", 4)],  # existing items
        )
        ctx = await tt._load_context(session, _gen())
        assert ctx.artifact_id == "a2"  # one miss on each, newest artifact wins the tie
        assert ctx.valid_pages == {1, 2}
        assert ctx.focus.topics == ["Open addressing", "Load factor"]
        assert ctx.focus.missed_questions == ["Why probing?", "Old miss?"]
        assert ctx.focus.page_refs == [2]  # only pages of the target artifact
        assert ctx.focus.avoid == ["What is X?", "What is Y?"]
        assert ctx.existing_stems == ["What is X?", "What is Y?"]
        assert ctx.next_version == 4
        assert ctx.summary_md == "# Summary"
        assert ctx.extraction.metadata["course_code"] == "CSIT302"

    async def test_falls_back_to_slide_titles_then_a_week_label(self):
        extraction = SimpleNamespace(
            artifact_id="a1", manifest_json={"pages": [{"page_number": 1, "text": "t"}]}
        )
        session = _session(
            "C", [("a1", NOW)], [], extraction, None, [], [(1, "Intro to hashing")], []
        )
        ctx = await tt._load_context(session, _gen())
        assert ctx.focus.topics == ["Intro to hashing"]
        assert ctx.summary_md == "" and ctx.next_version == 1 and ctx.focus.page_refs == []

        session = _session("C", [("a1", NOW)], [], extraction, None, [], [], [])
        ctx = await tt._load_context(session, _gen())
        assert ctx.focus.topics == ["Week 5 key ideas"]

    @pytest.mark.parametrize(
        "results",
        [
            pytest.param([None], id="foreign-or-missing-course"),
            pytest.param(["C", []], id="no-processed-artifact"),
            pytest.param(["C", [("a1", NOW)], [], None], id="no-extraction"),
            pytest.param(
                [
                    "C",
                    [("a1", NOW)],
                    [],
                    SimpleNamespace(artifact_id="a1", manifest_json={"pages": []}),
                ],
                id="no-pages",
            ),
        ],
    )
    async def test_missing_source_is_a_coded_error(self, results):
        with pytest.raises(tt.TargetedError) as caught:
            await tt._load_context(_session(*results), _gen())
        assert caught.value.code == "no_source"


def _ctx() -> tt.TargetContext:
    return tt.TargetContext(
        owner_id=OWNER,
        course_code="C",
        artifact_id="a1",
        extraction=MagicMock(),
        summary_md="",
        valid_pages={1},
        focus=GenerationFocus(topics=["Load factor", "Probing"]),
        existing_stems=[],
        next_version=3,
    )


class TestPersist:
    async def test_quiz_items_are_inserted_as_targeted_and_the_row_completes(self):
        row = _gen()
        session = _session(row)
        selection = Selection(
            kept=[
                QuizQuestionData(
                    question_type="multiple_choice",
                    question="What is the load factor?",
                    options=["A", "B"],
                    correct_answer="A",
                    explanation="e",
                    source_page_ref=1,
                )
            ],
            dropped_uncited=2,
            dropped_duplicate=1,
        )
        await tt._persist(session, row, _ctx(), selection)
        (added,) = (c.args[0] for c in session.add.call_args_list)
        assert isinstance(added, QuizQuestion)
        assert (added.origin, added.targeted_generation_id) == ("targeted", "g1")
        assert (added.focus_topic, added.generation_version) == ("Load factor", 3)
        assert (added.source_artifact_id, added.course_id, added.week) == ("a1", "c1", 5)
        assert added.options_json == ["A", "B"]
        assert (row.status, row.created_count) == ("completed", 1)
        assert (row.dropped_uncited_count, row.dropped_duplicate_count) == (2, 1)
        assert row.topics == ["Load factor", "Probing"] and row.error_code is None
        assert row.completed_at is not None
        session.commit.assert_awaited_once()

    async def test_flashcards_are_inserted_with_their_tags(self):
        row = _gen(kind="flashcards")
        session = _session(row)
        card = FlashcardData(front="f", back="b", tags=["probing"], source_page_ref=1)
        await tt._persist(session, row, _ctx(), Selection(kept=[card]))
        (added,) = (c.args[0] for c in session.add.call_args_list)
        assert isinstance(added, Flashcard)
        assert added.tags == ["probing"] and added.focus_topic == "Probing"
        assert added.origin == "targeted"

    async def test_the_lock_is_scoped_to_the_owner(self):
        row = _gen()
        session = _session(row)
        await tt._persist(session, row, _ctx(), Selection())
        sql = str(session.execute.await_args.args[0].compile())
        assert "user_id" in sql and "FOR UPDATE" in sql

    @pytest.mark.parametrize("current", [None, "failed", "completed"])
    async def test_a_row_that_is_no_longer_running_gets_nothing(self, current):
        row = None if current is None else _gen(status=current)
        session = _session(row)
        selection = Selection(kept=[QuizQuestionData("short_answer", "q", None, "a", "e", 1)])
        with pytest.raises(tt.TargetedError) as caught:
            await tt._persist(session, _gen(), _ctx(), selection)
        assert caught.value.code == "superseded"
        session.add.assert_not_called()
        session.commit.assert_not_awaited()

    async def test_nothing_is_ever_updated_or_deleted(self):
        row = _gen()
        session = _session(row)
        await tt._persist(session, row, _ctx(), Selection())
        session.delete.assert_not_called()


class TestFail:
    async def test_marks_only_in_flight_rows_with_the_code(self):
        session = AsyncMock()

        @asynccontextmanager
        async def factory():
            yield session

        with patch.object(tt, "async_session_factory", factory):
            await tt._fail("g1", OWNER, "no_source")
        compiled = session.execute.await_args.args[0].compile()
        assert "status IN" in str(compiled) and "user_id" in str(compiled)
        assert OWNER in compiled.params.values()
        assert "no_source" in compiled.params.values() and "failed" in compiled.params.values()
        session.commit.assert_awaited_once()


class TestRecoveryTask:
    def test_counts_and_reports(self):
        with (
            patch.object(tt, "run_async", return_value=["a", "b"]),
            patch.object(tt, "_recover_stuck", new=MagicMock()),
        ):
            assert tt.recover_stuck_generations.run() == {"failed": 2}

    def test_nothing_stuck_reports_zero(self):
        with (
            patch.object(tt, "run_async", return_value=[]),
            patch.object(tt, "_recover_stuck", new=MagicMock()),
        ):
            assert tt.recover_stuck_generations.run() == {"failed": 0}
