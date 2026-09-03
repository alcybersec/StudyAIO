"""Integration tests for account deletion against a real database.

The unit tests can only check the shape of the predicates. Whether deletion
*actually* leaves nothing behind depends on foreign keys, table ordering and
the real schema, so it has to be exercised end to end.

This suite caught a live bug: `review_items` has no foreign key, so it sorted
after `lecture_artifacts` and its rows survived, because the predicate used a
subquery over already-deleted parents. See `account_service.OwnedIds`.
"""

import secrets
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.database import Base
from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.exam import Exam
from app.models.extraction import Extraction
from app.models.review_item import ReviewItem
from app.models.summary import Summary
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services import account_service


def _tag() -> str:
    """A short, collision-free prefix for one test's rows."""
    return secrets.token_hex(5)


async def _seed_user(session, tag: str) -> dict[str, str]:
    """Create a user with one of everything. Returns the IDs created."""
    now = datetime.now(UTC)
    uid, cid, aid, sid = (f"{tag}-user", f"{tag}-course", f"{tag}-art", f"{tag}-chat")

    session.add(
        User(
            id=uid,
            email=f"{tag}@delete.test",
            username=f"{tag}_user",
            hashed_password="x",
            created_at=now,
            updated_at=now,
        )
    )
    # Everything below references the user, so it must exist first.
    await session.flush()

    session.add(Course(id=cid, user_id=uid, code=f"DEL{tag}", name=f"Course {tag}"))
    session.add(
        LectureArtifact(
            id=aid,
            user_id=uid,
            course_id=cid,
            week=1,
            title="Lecture 1",
            original_filename="a.pdf",
            file_path=f"uploads/{aid}.pdf",
            file_type="pdf",
            sha256=f"sha-{tag}",
            file_size_bytes=10,
            status="processed",
        )
    )
    await session.flush()

    session.add(
        Extraction(
            id=f"{tag}-ex",
            artifact_id=aid,
            manifest_json={},
            page_count=1,
            image_count=0,
            extraction_path=f"extractions/{aid}",
        )
    )
    session.add(
        Summary(
            id=f"{tag}-sum",
            course_id=cid,
            week=1,
            content_md="# x",
            file_path=f"summaries/{cid}.md",
            version=1,
            source_artifacts=[aid],
        )
    )
    session.add(
        Chunk(id=f"{tag}-chunk", artifact_id=aid, stable_id=f"{aid}-0", text="c", page_ref=1)
    )
    # Polymorphic — no foreign key. This is the row that regressed.
    session.add(
        ReviewItem(
            id=f"{tag}-review",
            review_type="classification",
            entity_type="lecture_artifact",
            entity_id=aid,
            payload_json={},
            suggested_values={},
        )
    )
    session.add(
        Exam(
            id=f"{tag}-exam",
            user_id=uid,
            course_id=cid,
            title="Midterm",
            exam_date=now,
            weeks_scope=[1],
        )
    )
    session.add(ChatSession(id=sid, user_id=uid, title="chat"))
    await session.flush()
    session.add(ChatMessage(id=f"{tag}-msg", session_id=sid, role="user", content="hi"))
    session.add(UserSettings(id=f"{tag}-settings", user_id=uid, settings_json={}))
    await session.flush()

    return {"user": uid, "course": cid, "artifact": aid, "chat": sid}


@pytest.mark.asyncio(loop_scope="session")
class TestDeleteUserAccount:
    """Deleting an account must remove everything it owns — and nothing else."""

    async def test_leaves_no_row_behind_in_any_table(self, db_session):
        ids = await _seed_user(db_session, _tag())

        await account_service.delete_user_account(db_session, ids["user"])
        await db_session.flush()

        survivors = []
        owned_values = {ids["artifact"], ids["course"], ids["chat"]}
        for table in Base.metadata.tables.values():
            cols = table.c
            clauses = []
            if "user_id" in cols:
                clauses.append(cols.user_id == ids["user"])
            elif table.name == "users":
                clauses.append(cols.id == ids["user"])
            for name in ("artifact_id", "course_id", "session_id", "entity_id"):
                if name in cols:
                    clauses.append(cols[name].in_(owned_values))
            for clause in clauses:
                count = await db_session.scalar(
                    select(func.count()).select_from(table).where(clause)
                )
                if count:
                    survivors.append(f"{table.name}={count}")

        assert survivors == [], f"Rows survived account deletion: {survivors}"

    async def test_review_items_are_deleted(self, db_session):
        """Regression: review_items has no FK and was previously left behind."""
        tag = _tag()
        ids = await _seed_user(db_session, tag)

        await account_service.delete_user_account(db_session, ids["user"])
        await db_session.flush()

        remaining = await db_session.scalar(
            select(func.count())
            .select_from(ReviewItem)
            .where(ReviewItem.entity_id == ids["artifact"])
        )
        assert remaining == 0

    async def test_does_not_touch_another_users_data(self, db_session):
        victim = await _seed_user(db_session, _tag())
        keeper = await _seed_user(db_session, _tag())

        await account_service.delete_user_account(db_session, victim["user"])
        await db_session.flush()

        assert await db_session.get(User, keeper["user"]) is not None
        for model, key in ((Course, "course"), (LectureArtifact, "artifact")):
            assert await db_session.get(model, keeper[key]) is not None
        still_there = await db_session.scalar(
            select(func.count())
            .select_from(ReviewItem)
            .where(ReviewItem.entity_id == keeper["artifact"])
        )
        assert still_there == 1

    async def test_reports_what_it_deleted(self, db_session):
        ids = await _seed_user(db_session, _tag())

        counts = await account_service.delete_user_account(db_session, ids["user"])

        assert counts["users"] == 1
        assert counts["review_items"] == 1
        assert sum(counts.values()) >= 10


@pytest.mark.asyncio(loop_scope="session")
class TestExportUserData:
    """Export must cover the same ground as deletion, minus credentials."""

    async def test_exports_the_users_own_rows(self, db_session):
        ids = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, ids["user"])

        assert data["user_id"] == ids["user"]
        assert "courses" in data["tables"]
        assert "lecture_artifacts" in data["tables"]
        assert data["tables"]["users"][0]["id"] == ids["user"]

    async def test_never_exports_the_password_hash(self, db_session):
        ids = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, ids["user"])

        assert "hashed_password" not in data["tables"]["users"][0]
        assert "x" not in data["tables"]["users"][0].values()

    async def test_excludes_other_users(self, db_session):
        mine = await _seed_user(db_session, _tag())
        theirs = await _seed_user(db_session, _tag())

        data = await account_service.export_user_data(db_session, mine["user"])

        course_ids = {row["id"] for row in data["tables"]["courses"]}
        assert mine["course"] in course_ids
        assert theirs["course"] not in course_ids
