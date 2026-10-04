"""R-007 rulings (2026-10-04): retention of summaries and study history, leaderboard opt-in.

* re-summarize and merge ``keep_source`` snapshot the superseded summary
  (row and blob) before replacing it;
* asset regeneration archives (``archived_at``) instead of deleting;
* every read path ignores archived assets;
* the leaderboard shows only opted-in users (plus the caller).
"""

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Delete, Update

from app.agents.base import FlashcardData, QuizQuestionData
from app.models.summary import Summary
from app.models.summary_version import SummaryVersion
from app.services import (
    analytics_service,
    asset_service,
    course_service,
    exam_service,
    readiness_service,
    schedule_service,
    search_service,
    settings_service,
    srs_service,
    summary_service,
    timed_session_service,
    xp_service,
)

USER = "user-caller"


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


# ── summaries ───────────────────────────────────────────────────────────


def _old_summary(file_path: str = "summaries/course-1/Week3.md") -> Summary:
    return Summary(
        id="summary-1",
        course_id="course-1",
        week=3,
        content_md="# v1 content",
        file_path=file_path,
        version=1,
        source_artifacts=["artifact-1"],
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _summary_session(existing: Summary | None) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=USER)
    return session


class TestVersionedKey:
    def test_default_key_is_unchanged(self):
        assert summary_service.build_summary_storage_key("c1", 3) == "summaries/c1/Week3.md"

    def test_versioned_key(self):
        assert summary_service.build_summary_storage_key("c1", 3, version=2) == (
            "summaries/c1/Week3.v2.md"
        )


@pytest.mark.asyncio
class TestResummarizeRetainsPriorVersion:
    async def test_snapshot_row_is_added_before_replacement(self):
        existing = _old_summary()
        session = _summary_session(existing)
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        with patch("app.services.summary_service.get_storage", return_value=storage):
            await summary_service.create_or_update_summary(
                session, "course-1", 3, "# v2", "summaries/course-1/Week3.md", ["artifact-2"]
            )

        versions = [c.args[0] for c in session.add.call_args_list]
        snap = next(v for v in versions if isinstance(v, SummaryVersion))
        assert snap.content_md == "# v1 content"
        assert snap.version == 1
        assert snap.user_id == USER  # the course owner, not whoever triggered it
        assert snap.course_id == "course-1" and snap.week == 3
        assert snap.generated_at == datetime(2026, 1, 1, tzinfo=UTC)
        assert snap.file_path == "summaries/course-1/Week3.v1.md"
        assert snap.source_artifacts == ["artifact-1"]
        # and the live row moved on
        assert existing.content_md == "# v2" and existing.version == 2

    async def test_prior_blob_is_written_to_its_own_key(self):
        session = _summary_session(_old_summary())
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        with patch("app.services.summary_service.get_storage", return_value=storage):
            await summary_service.create_or_update_summary(
                session, "course-1", 3, "# v2", "summaries/course-1/Week3.md", []
            )
        storage.put.assert_awaited_once_with("summaries/course-1/Week3.v1.md", b"# v1 content")

    async def test_never_puts_over_an_existing_key(self):
        session = _summary_session(_old_summary())
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=True)
        with patch("app.services.summary_service.get_storage", return_value=storage):
            await summary_service.create_or_update_summary(
                session, "course-1", 3, "# v2", "summaries/course-1/Week3.md", []
            )
        storage.put.assert_not_awaited()

    async def test_first_summary_takes_no_snapshot(self):
        session = _summary_session(None)
        await summary_service.create_or_update_summary(
            session, "course-1", 3, "# v1", "summaries/course-1/Week3.md", ["a"]
        )
        assert not any(isinstance(c.args[0], SummaryVersion) for c in session.add.call_args_list)


@pytest.mark.asyncio
class TestMergeKeepSourceSnapshotsTarget:
    async def test_overwritten_target_summary_is_snapshotted_first(self):
        target_summary = Summary(
            id="t1",
            course_id="target",
            week=3,
            content_md="# target text",
            file_path="summaries/target/Week3.md",
            version=1,
            source_artifacts=["a1"],
        )
        source_summary = Summary(
            id="s1",
            course_id="source",
            week=3,
            content_md="# source text",
            file_path="summaries/source/Week3.md",
            version=1,
            source_artifacts=["a2"],
        )
        source = SimpleNamespace(id="source", archived_at=None)
        target = SimpleNamespace(id="target")

        def scalars(rows):
            r = MagicMock()
            r.scalars.return_value.all.return_value = rows
            return r

        session = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[scalars([target_summary]), scalars([source_summary]), MagicMock()]
            + [MagicMock()] * 20
        )
        storage = AsyncMock()
        calls: list[str] = []

        async def snapshot(sess, summary, **kw):
            # at snapshot time the target must still hold its own text
            calls.append(summary.content_md)

        with (
            patch(
                "app.services.course_service._get_owned_course",
                new_callable=AsyncMock,
                side_effect=[source, target],
            ),
            patch("app.services.course_service.get_storage", return_value=storage),
            patch(
                "app.services.course_service.summary_service.snapshot_summary",
                new_callable=AsyncMock,
                side_effect=snapshot,
            ) as snap,
        ):
            await course_service.merge_courses(session, USER, "SRC", "TGT", "keep_source")

        snap.assert_awaited_once()
        assert snap.await_args.args[1] is target_summary
        assert calls == ["# target text"]
        assert target_summary.content_md == "# source text"
        assert target_summary.version == 2
        # the new bytes go to a key of their own; the snapshot's key is never deleted
        put_keys = [c.args[0] for c in storage.put.await_args_list]
        assert "summaries/target/Week3.v2.md" in put_keys
        deleted = [c.args[0] for c in storage.delete.await_args_list]
        assert "summaries/target/Week3.v1.md" not in deleted


# ── asset regeneration ──────────────────────────────────────────────────


def _recording_session() -> tuple[AsyncMock, list]:
    captured: list = []
    result = MagicMock()
    result.scalar.return_value = 0

    async def execute(stmt, *a, **k):
        captured.append(stmt)
        return result

    session = AsyncMock()
    session.add = MagicMock()
    session.execute = execute
    return session, captured


@pytest.mark.asyncio
class TestRegenerationArchivesInsteadOfDeleting:
    async def test_flashcards_archived_not_deleted(self):
        session, captured = _recording_session()
        await asset_service.save_flashcards(
            session, "c1", 3, "art-1", [FlashcardData(front="q", back="a")]
        )
        assert not [s for s in captured if isinstance(s, Delete)]
        updates = [s for s in captured if isinstance(s, Update)]
        assert len(updates) == 1
        sql = _sql(updates[0])
        assert "UPDATE flashcards SET archived_at=" in sql
        assert "source_artifact_id = 'art-1'" in sql
        assert "archived_at IS NULL" in sql  # re-archiving must not move the timestamp

    async def test_quiz_questions_archived_not_deleted(self):
        session, captured = _recording_session()
        await asset_service.save_quiz_questions(
            session,
            "c1",
            3,
            "art-1",
            [QuizQuestionData(question_type="short_answer", question="q", correct_answer="a")],
        )
        assert not [s for s in captured if isinstance(s, Delete)]
        updates = [s for s in captured if isinstance(s, Update)]
        assert len(updates) == 1
        sql = _sql(updates[0])
        assert "UPDATE quiz_questions SET archived_at=" in sql
        assert "source_artifact_id = 'art-1'" in sql
        assert "archived_at IS NULL" in sql

    async def test_new_rows_are_active(self):
        session, _ = _recording_session()
        records = await asset_service.save_flashcards(
            session, "c1", 3, "art-1", [FlashcardData(front="q", back="a")]
        )
        assert records[0].archived_at is None

    async def test_generation_version_still_counts_archived_rows(self):
        session, captured = _recording_session()
        await asset_service.save_flashcards(session, "c1", 3, "art-1", [])
        max_stmt = [s for s in captured if "max(" in _sql(s)][0]
        assert "archived_at" not in _sql(max_stmt)


# ── read paths ──────────────────────────────────────────────────────────


class _Result:
    """Permissive stand-in for a SQLAlchemy result."""

    def __init__(self, exam):
        self._exam = exam

    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return self._exam

    def scalars(self):
        return SimpleNamespace(all=lambda: [], first=lambda: None)

    def all(self):
        return []

    def one(self):
        return SimpleNamespace(total=0, correct=0)

    def first(self):
        return None

    def __iter__(self):
        return iter([])


def _exam():
    return SimpleNamespace(
        id="exam-1",
        course_id="c1",
        weeks_scope=[1, 2],
        exam_date=datetime.now(UTC) + timedelta(days=10),
        status="active",
        title="Final",
        target_mastery_pct=80,
        user_id=USER,
    )


async def _statements(fn, *args, **kwargs) -> list:
    captured: list = []
    result = _Result(_exam())

    async def execute(stmt, *a, **k):
        captured.append(stmt)
        return result

    session = AsyncMock()
    session.execute = execute
    session.scalar = AsyncMock(return_value=None)
    try:
        await fn(session, *args, **kwargs)
    except Exception:  # the stand-in result is not a real one; only the SQL matters
        pass
    return captured


def _unfiltered(statements: list) -> tuple[int, list[str]]:
    """(statements touching an asset table, those missing the archived filter)."""
    touched = 0
    bad: list[str] = []
    for stmt in statements:
        if isinstance(stmt, Update | Delete):
            continue
        sql = _sql(stmt)
        for table in ("flashcards", "quiz_questions"):
            if re.search(rf"(?:FROM|JOIN)\s+{table}\b", sql):
                touched += 1
                if f"{table}.archived_at IS NULL" not in sql:
                    bad.append(f"[{table}] {sql}")
    return touched, bad


READ_PATHS = {
    "srs.get_due_cards": (srs_service.get_due_cards, ("NET101", None, 5), {"user_id": USER}),
    "srs.get_study_stats": (srs_service.get_study_stats, ("NET101", None), {"user_id": USER}),
    "srs.get_per_course_due_counts": (
        srs_service.get_per_course_due_counts,
        (),
        {"user_id": USER},
    ),
    "asset.flashcards_for_week": (
        asset_service.get_flashcards_for_week,
        ("NET101", 1),
        {"user_id": USER},
    ),
    "asset.quiz_for_week": (
        asset_service.get_quiz_questions_for_week,
        ("NET101", 1),
        {"user_id": USER},
    ),
    "asset.flashcards_for_course": (
        asset_service.get_flashcards_for_course,
        ("NET101",),
        {"user_id": USER},
    ),
    "asset.quiz_for_course": (
        asset_service.get_quiz_questions_for_course,
        ("NET101",),
        {"user_id": USER},
    ),
    "exam.get_exam_progress": (exam_service.get_exam_progress, ("exam-1",), {"user_id": USER}),
    "readiness.collect_week_stats": (readiness_service.collect_week_stats, ("c1", [1]), {}),
    "readiness.compute_readiness_detail": (
        readiness_service.compute_readiness_detail,
        ("exam-1", USER),
        {},
    ),
    "schedule.generate_study_schedule": (
        schedule_service.generate_study_schedule,
        ("exam-1",),
        {"user_id": USER},
    ),
    "course.get_course_weeks": (course_service.get_course_weeks, ("c1",), {}),
    "search.search_all": (search_service.search_all, (USER, "tcp"), {}),
    "analytics.get_overview": (analytics_service.get_overview, (USER,), {}),
    "analytics.get_mastery_breakdown": (analytics_service.get_mastery_breakdown, (USER,), {}),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(READ_PATHS))
async def test_read_path_ignores_archived_assets(name):
    fn, args, kwargs = READ_PATHS[name]
    touched, bad = _unfiltered(await _statements(fn, *args, **kwargs))
    assert touched, f"{name} issued no query on flashcards/quiz_questions: the probe is blind"
    assert not bad, f"{name} reads archived assets:\n" + "\n".join(bad)


@pytest.mark.asyncio
async def test_timed_plan_ignores_archived_assets():
    captured: list = []
    result = _Result(None)

    async def execute(stmt, *a, **k):
        captured.append(stmt)
        return result

    session = AsyncMock()
    session.execute = execute
    # due-cards go through srs_service.get_due_cards (covered above); the quiz
    # query is the timed plan's own.
    with patch(
        "app.services.timed_session_service.srs_service.get_due_cards",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await timed_session_service.generate_timed_plan(session, 30, user_id=USER)
    touched, bad = _unfiltered(captured)
    assert touched and not bad, "\n".join(bad)


def test_export_queries_ignore_archived_assets():
    import inspect

    from app.services import export_service

    src = inspect.getsource(export_service.generate_obsidian_vault)
    assert src.count("archived_at.is_(None)") >= 2


# ── leaderboard opt-in ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestLeaderboardOptIn:
    async def test_query_joins_settings_and_requires_opt_in_or_caller(self):
        captured: list = []
        result = MagicMock()
        result.all.return_value = []

        async def execute(stmt, *a, **k):
            captured.append(stmt)
            return result

        session = AsyncMock()
        session.execute = execute
        await xp_service.get_leaderboard(session, user_id=USER)
        sql = _sql(captured[0])
        assert "user_settings" in sql
        assert "user_settings.leaderboard_opt_in IS true" in sql
        assert "user_xp.user_id = 'user-caller'" in sql  # caller still sees own XP


@pytest.mark.asyncio
class TestLeaderboardOptInSetting:
    async def test_get_includes_flag_default_false(self):
        row = SimpleNamespace(
            settings_json={},
            theme="system",
            language="en",
            content_language=False,
            dashboard_layout=None,
            leaderboard_opt_in=False,
        )
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=row,
        ):
            got = await settings_service.get_user_settings(AsyncMock(), USER)
        assert got["leaderboard_opt_in"] is False

    async def test_update_sets_flag_and_rejects_non_bool(self):
        row = SimpleNamespace(
            settings_json={},
            theme="system",
            language="en",
            content_language=False,
            dashboard_layout=None,
            leaderboard_opt_in=False,
            updated_at=None,
        )
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=row,
        ):
            session = AsyncMock()
            got = await settings_service.update_user_settings(
                session, USER, {"leaderboard_opt_in": True}
            )
            assert row.leaderboard_opt_in is True and got["leaderboard_opt_in"] is True
            with pytest.raises(ValueError):
                await settings_service.update_user_settings(
                    session, USER, {"leaderboard_opt_in": "yes"}
                )
