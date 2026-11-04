"""Tests for review_service."""

import pytest

from app.services import review_service


class TestCreateReviewItem:
    """Tests for create_review_item()."""

    async def test_create_review_item(self, mock_session):
        """Creates a review item with correct fields."""
        result = await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={"context": "some text", "filename": "test.pdf"},
            suggested_values={"course_code": "CSIT302", "week": 5},
            user_id="user-001",
        )

        assert result.review_type == "classification_course"
        assert result.entity_type == "lecture_artifact"
        assert result.entity_id == "artifact-001"
        assert result.status == "pending"
        assert result.payload_json["filename"] == "test.pdf"
        assert result.suggested_values["course_code"] == "CSIT302"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestReviewCreationEmitsInbox:
    """Review-item creation emits a kind='review' inbox notification."""

    async def test_create_review_item_emits_notification(self, mock_session):
        """When the artifact owner is resolvable, an inbox row is added."""
        from unittest.mock import MagicMock

        from app.models.notification import Notification

        artifact = MagicMock()
        artifact.user_id = "user-001"
        artifact.original_filename = "lecture.pdf"
        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = artifact
        mock_session.execute.return_value = artifact_result

        await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={"filename": "lecture.pdf"},
            suggested_values={"course_code": "CSIT302"},
            user_id="user-001",
        )

        added = [c.args[0] for c in mock_session.add.call_args_list]
        notifications = [n for n in added if isinstance(n, Notification)]
        assert len(notifications) == 1
        assert notifications[0].kind == "review"
        assert notifications[0].user_id == "user-001"

    async def test_create_review_item_survives_emit_failure(self, mock_session):
        """Notification emit failure never breaks review creation."""
        mock_session.execute.side_effect = RuntimeError("lookup failed")

        item = await review_service.create_review_item(
            session=mock_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id="artifact-001",
            payload={},
            suggested_values={},
            user_id="user-001",
        )
        assert item.status == "pending"


# ── R-010: ownership is the review item's own user_id ────────────────
#
# ReviewItem used to be polymorphic-by-ownership: scoping resolved through the
# artifact or summary it referenced (#58 was a listing that missed the summary
# branch). The row now carries user_id, so every read is a single direct
# predicate and the two paths cannot drift. Legacy rows orphaned before the
# column existed may keep a NULL user_id; `user_id = <caller>` never matches
# NULL, so they are invisible to everyone -- fail-closed by construction.
#
# These assert on the compiled SQL: tests/unit/ has no database (the models use
# JSONB). The per-function wiring checks live in test_r010_user_id_wiring.py.

OWNER = "owner-user-58"
STRANGER = "stranger-user-58"


def _capturing_session():
    """AsyncMock session that records the query object handed to execute()."""
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=result)
    return session


def _sql(query) -> str:
    """Compile a query to Postgres SQL with user ids inlined."""
    from sqlalchemy.dialects import postgresql

    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


async def _executed_sql(service_fn, *args, **kwargs) -> str:
    session = _capturing_session()
    await service_fn(session, *args, **kwargs)
    return _sql(session.execute.await_args.args[0])


def _where(sql: str) -> str:
    return sql.split("WHERE ", 1)[1].split(" ORDER BY", 1)[0]


class TestReviewItemsScopedByOwnColumn:
    """Every listing is bound to the caller through review_items.user_id alone."""

    async def test_pending_listing_is_one_direct_predicate(self):
        sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)

        assert _where(sql) == (
            f"review_items.status = 'pending' AND review_items.user_id = '{OWNER}'"
        )
        assert "JOIN" not in sql and "EXISTS" not in sql

    async def test_only_the_caller_id_separates_two_callers(self):
        """An owner's query and a stranger's differ by the bound id, nothing else."""
        owner_sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        stranger_sql = await _executed_sql(review_service.list_pending_reviews, user_id=STRANGER)

        assert owner_sql != stranger_sql
        assert owner_sql.replace(OWNER, STRANGER) == stranger_sql
        assert STRANGER not in owner_sql

    async def test_count_agrees_with_the_listing(self):
        """The inbox badge counts exactly what the list shows."""
        list_sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        count_sql = await _executed_sql(review_service.count_pending_reviews, user_id=OWNER)

        assert _where(list_sql) == _where(count_sql)

    async def test_status_listing_and_get_use_the_same_predicate(self):
        by_status = await _executed_sql(
            review_service.list_reviews_by_status, "resolved", user_id=OWNER
        )
        one = await _executed_sql(review_service.get_review_item, "r1", user_id=OWNER)

        assert f"review_items.user_id = '{OWNER}'" in by_status
        assert f"review_items.user_id = '{OWNER}'" in one

    async def test_empty_user_id_scopes_rather_than_listing_everything(self):
        """A falsy-but-present user id must not fall through to "no filter"."""
        sql = await _executed_sql(review_service.list_pending_reviews, user_id="")

        assert "review_items.user_id = ''" in sql

    async def test_caller_is_required_so_no_unscoped_listing_exists(self):
        """R-021: omitting user_id is a TypeError, not an unscoped listing."""
        session = _capturing_session()

        with pytest.raises(TypeError):
            await review_service.list_pending_reviews(session)
        session.execute.assert_not_awaited()
