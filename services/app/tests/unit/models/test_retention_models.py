"""Schema contract for the 2026-10-04 R-007 rulings (floor 1/4)."""

from sqlalchemy import Boolean, DateTime, UniqueConstraint

from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.summary_version import SummaryVersion
from app.models.user_settings import UserSettings


def test_summary_version_is_user_owned_and_unique_per_version() -> None:
    table = SummaryVersion.__table__
    assert not table.c.user_id.nullable
    assert {fk.column.table.name for fk in table.c.user_id.foreign_keys} == {"users"}
    uniques = {
        tuple(c.name for c in u.columns)
        for u in table.constraints
        if isinstance(u, UniqueConstraint)
    }
    assert ("course_id", "week", "version") in uniques


def test_summary_version_keeps_content_and_blob_key() -> None:
    cols = SummaryVersion.__table__.c
    assert not cols.content_md.nullable
    assert not cols.file_path.nullable


def test_assets_have_nullable_archived_at() -> None:
    for model in (Flashcard, QuizQuestion):
        col = model.__table__.c.archived_at
        assert col.nullable
        assert isinstance(col.type, DateTime)
        assert col.default is None


def test_leaderboard_opt_in_defaults_hidden() -> None:
    col = UserSettings.__table__.c.leaderboard_opt_in
    assert isinstance(col.type, Boolean)
    assert not col.nullable
    assert col.default.arg is False
