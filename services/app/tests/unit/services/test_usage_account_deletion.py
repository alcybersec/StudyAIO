"""Account deletion removes AI feedback and usage events (floor 4 deletion path)."""

from app.core.database import Base
from app.services import account_service


def test_new_tables_are_user_scoped_and_deleted():
    user_scoped, unclassified = account_service.classify_tables()
    assert "ai_feedback" in user_scoped
    assert "usage_events" in user_scoped
    assert unclassified == []


def test_predicates_filter_on_user_id():
    for name in ("ai_feedback", "usage_events"):
        table = Base.metadata.tables[name]
        clause = account_service._build_predicates(table, "u-1", account_service.OwnedIds.empty())
        assert f"{name}.user_id" in str(clause)
        assert "u-1" in clause.compile().params.values()
