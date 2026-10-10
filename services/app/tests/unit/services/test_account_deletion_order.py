"""Deletion order is FK-safe even across the courseops cycle (M32 C2a / R-016)."""

from app.services import account_service


def _positions() -> dict[str, int]:
    return {t.name: i for i, t in enumerate(reversed(account_service._ordered_tables()))}


def test_course_documents_and_assessments_are_deleted_before_courses() -> None:
    pos = _positions()
    assert pos["course_documents"] < pos["courses"]
    assert pos["assessments"] < pos["courses"]


def test_every_fk_child_is_deleted_before_its_parent_except_set_null_edges() -> None:
    pos = _positions()
    for table in account_service._ordered_tables():
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent == table.name or fk.ondelete == "SET NULL":
                continue
            assert pos[table.name] < pos[parent], f"{table.name} must precede {parent}"
