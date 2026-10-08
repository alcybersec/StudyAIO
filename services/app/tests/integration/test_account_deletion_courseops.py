"""Account deletion for users who own CourseOps rows.

`account_service._ordered_tables` relies on `Base.metadata.sorted_tables` and
documents that the `assessments` <-> `course_documents` cycle is "safe to ignore
because every edge is SET NULL or CASCADE". The order SQLAlchemy falls back to
for a cyclic graph, however, places both tables *before* `courses`, and deletion
walks that list in reverse, so `DELETE FROM courses` runs while rows still
reference it. These tests ask the real database whether that matters.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.core.utils import generate_id
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.deadline import Deadline
from app.models.user import User
from app.services import account_service

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def _owner_with(db_session, make_user, *, document=False, assessment=False, deadline=False):
    user = await make_user()
    course = Course(id=generate_id(), code="DEL101", name="Del", user_id=user.id)
    db_session.add(course)
    await db_session.flush()
    if assessment:
        db_session.add(
            Assessment(id=generate_id(), course_id=course.id, title="A", assessment_type="exam")
        )
    if deadline:
        db_session.add(
            Deadline(
                id=generate_id(),
                course_id=course.id,
                title="D",
                due_date=date(2030, 1, 1),
                deadline_type="exam",
            )
        )
    if document:
        db_session.add(
            CourseDocument(
                id=generate_id(),
                user_id=user.id,
                course_id=course.id,
                document_type="outline",
                original_filename="o.pdf",
                file_path=f"courseops/{user.id}/o.pdf",
                file_type="pdf",
                sha256=generate_id().replace("-", "") * 2,
                file_size_bytes=1,
                status="pending",
            )
        )
    await db_session.flush()
    return user, course


async def test_user_with_deadline_only_is_deleted(db_session, make_user, storage):
    user, course = await _owner_with(db_session, make_user, deadline=True)
    counts = await account_service.delete_user_account(db_session, user.id, storage=storage)
    assert counts["deadlines"] == 1 and counts["courses"] == 1
    assert (await db_session.execute(select(User).where(User.id == user.id))).first() is None


async def test_user_with_course_document_is_deleted(db_session, make_user, storage):
    user, course = await _owner_with(db_session, make_user, document=True)
    await account_service.delete_user_account(db_session, user.id, storage=storage)
    assert (await db_session.execute(select(User).where(User.id == user.id))).first() is None


async def test_user_with_assessment_is_deleted(db_session, make_user, storage):
    user, course = await _owner_with(db_session, make_user, assessment=True)
    await account_service.delete_user_account(db_session, user.id, storage=storage)
    assert (await db_session.execute(select(User).where(User.id == user.id))).first() is None
