"""Schema contract for ai_feedback, usage_events and AI-processing consent."""

from sqlalchemy import DateTime, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models import AIFeedback, UsageEvent, User


def _indexed_cols(table) -> set[tuple[str, ...]]:
    return {tuple(c.name for c in i.columns) for i in table.indexes}


def test_ai_feedback_user_owned_indexed_and_unique_per_target() -> None:
    table = AIFeedback.__table__
    assert table.name == "ai_feedback"
    assert not table.c.user_id.nullable
    assert {fk.column.table.name for fk in table.c.user_id.foreign_keys} == {"users"}
    assert ("user_id",) in _indexed_cols(table)
    uniques = {
        tuple(c.name for c in u.columns)
        for u in table.constraints
        if isinstance(u, UniqueConstraint)
    }
    assert ("user_id", "target_type", "target_id") in uniques


def test_ai_feedback_columns() -> None:
    cols = AIFeedback.__table__.c
    assert isinstance(cols.rating.type, SmallInteger)
    assert not cols.rating.nullable
    for name in ("reason", "comment", "course_id"):
        assert cols[name].nullable
    for name in ("target_type", "target_id"):
        assert not cols[name].nullable
    assert "updated_at" in cols


def test_usage_events_user_owned_with_cohort_indexes() -> None:
    table = UsageEvent.__table__
    assert not table.c.user_id.nullable
    assert ("event", "occurred_at") in _indexed_cols(table)
    assert ("user_id", "occurred_at") in _indexed_cols(table)


def test_usage_events_columns_and_append_only() -> None:
    cols = UsageEvent.__table__.c
    assert isinstance(cols.occurred_at.type, DateTime)
    assert cols.occurred_at.server_default is not None
    assert isinstance(cols.properties.type, JSONB)
    assert not cols.properties.nullable
    assert cols.course_id.nullable
    assert "updated_at" not in cols


def test_user_consent_columns_nullable() -> None:
    cols = User.__table__.c
    assert cols.ai_processing_consent_at.nullable
    assert isinstance(cols.ai_processing_consent_at.type, DateTime)
    assert cols.ai_processing_consent_version.nullable
    assert isinstance(cols.ai_processing_consent_version.type, SmallInteger)
