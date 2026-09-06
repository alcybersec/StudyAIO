"""Tests for review_service."""

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
        )
        assert item.status == "pending"


# ── #58: pending-review listing must cover every entity type ─────────
#
# ReviewItem is polymorphic (entity_type + entity_id, no FK) and both live
# types are created in production: `lecture_artifact` by pipeline/classify.py
# and `summary` by course_service.merge_courses. list_pending_reviews used to
# inner-join LectureArtifact, which structurally excluded every summary-backed
# item -- created, then unreachable by its owner.
#
# These assert on the compiled SQL rather than on rows. `tests/unit/` has no
# database (no sqlite driver is installed, and the models use JSONB), and the
# integration suite that does have one cannot be run locally right now (#56).
# The same technique is already used on this predicate in
# tests/unit/api/test_idor_scoping.py::TestReviewItemOwnershipPredicate. It
# proves what matters here: which entity types the query can reach, and that
# every branch reaching one is bound to the calling user's id.

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


async def _executed_sql(service_fn, **kwargs) -> str:
    session = _capturing_session()
    await service_fn(session, **kwargs)
    return _sql(session.execute.await_args.args[0])


def _ownership_clause(sql: str) -> str:
    """The part of a pending-review WHERE clause that resolves ownership."""
    marker = "review_items.status = 'pending' AND "
    assert marker in sql, f"expected a pending-status filter in:\n{sql}"
    return sql.split(marker, 1)[1].split(" ORDER BY", 1)[0]


class TestPendingReviewsCoverEveryEntityType:
    """#58: a summary-backed pending item must reach its owner -- and only them."""

    async def test_summary_backed_item_is_reachable_by_its_owner(self):
        """The scoped listing can match a `summary` item, not just artifacts.

        The bug was structural, not a missing filter: an inner join onto
        lecture_artifacts can never yield a row whose entity_id is a
        summaries.id, whoever is asking.
        """
        sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)

        assert "summaries" in sql, "summary-backed review items are still unreachable"
        assert "courses" in sql, "summary ownership must resolve through Course.user_id"
        assert "lecture_artifacts" in sql, "artifact-backed items must stay reachable"
        assert "\nFROM review_items \n" in f"\n{sql}\n", (
            "the ownership check must not be an inner join that filters out "
            f"whole entity types:\n{sql}"
        )

    async def test_summary_backed_item_is_not_reachable_by_anyone_else(self):
        """Widening the query must not widen who can see a row.

        This is the half that matters: list_pending_reviews now uses the same
        predicate the id-addressed authorization paths use, so a loosening
        here would loosen those too.
        """
        sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        clause = _ownership_clause(sql)

        assert STRANGER not in sql
        # Every ownership branch -- not merely one of them -- is bound to the
        # caller. An unbound branch would make those items public.
        branches = clause.split("EXISTS")[1:]
        assert len(branches) == 2, f"expected one branch per entity type:\n{clause}"
        assert all(f"user_id = '{OWNER}'" in branch for branch in branches), clause
        assert clause.count(f"'{OWNER}'") == 2, clause
        # ...and there is no third disjunct alongside them. "OR entity_type =
        # 'summary'" would make summary items visible to everyone, which is
        # the tempting wrong fix for #58.
        assert clause.count(" OR ") == 1, f"unexpected extra disjunct:\n{clause}"

    async def test_only_the_caller_id_separates_two_callers(self):
        """An owner's query and a stranger's differ by the bound id, nothing else."""
        owner_sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        stranger_sql = await _executed_sql(review_service.list_pending_reviews, user_id=STRANGER)

        assert owner_sql != stranger_sql
        assert owner_sql.replace(OWNER, STRANGER) == stranger_sql

    async def test_unhandled_entity_type_matches_nothing(self):
        """Fail-closed: a future third entity type is invisible, not public.

        Ownership is an allow-list of entity tables. Nothing in the clause
        matches a row whose entity_id is neither an artifact nor a summary, so
        adding an entity type without adding its branch hides items from their
        owner (a bug report) rather than showing them to everyone (an incident).
        """
        sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        clause = _ownership_clause(sql)

        referenced = {
            table
            for table in ("lecture_artifacts", "summaries", "courses", "review_items")
            if table in clause
        }
        assert referenced == {"lecture_artifacts", "summaries", "courses", "review_items"}
        # No branch that holds regardless of the row.
        assert "1 = 1" not in clause
        assert "true" not in clause.lower()

    async def test_uses_the_same_predicate_as_the_authorization_path(self):
        """The listing and the id-addressed paths must share one predicate.

        get/resolve/dismiss scope with _owned_by. If the listing resolved
        ownership its own way the two would drift, and an item could be listed
        but not openable (#58's shape) or the reverse.
        """
        from sqlalchemy import select

        from app.models.review_item import ReviewItem

        reference = _sql(select(ReviewItem).where(review_service._owned_by(OWNER)))
        reference_clause = reference.split("WHERE ", 1)[1]

        sql = await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        clause = _ownership_clause(sql)
        if clause.startswith("(") and clause.endswith(")"):
            clause = clause[1:-1]

        # Equality, not containment: an extra OR'd disjunct would still
        # *contain* the predicate while quietly widening it.
        assert clause == reference_clause, (
            "list_pending_reviews scopes differently from _owned_by, the "
            f"predicate get/resolve/dismiss authorize with:\n{clause}"
        )

    async def test_count_agrees_with_the_listing(self):
        """The dashboard badge counts exactly what the list shows.

        count_pending_reviews carried the same artifact-only join. A badge that
        disagrees with the page it links to is its own bug.
        """
        list_clause = _ownership_clause(
            await _executed_sql(review_service.list_pending_reviews, user_id=OWNER)
        )
        count_sql = await _executed_sql(review_service.count_pending_reviews, user_id=OWNER)

        assert list_clause in count_sql, f"count scopes differently from list:\n{count_sql}"

    async def test_empty_user_id_scopes_rather_than_listing_everything(self):
        """A falsy-but-present user id must not fall through to "no filter".

        The old `if user_id:` treated "" as an unscoped internal call and
        returned every user's pending items. `is not None` makes it scope to a
        user that owns nothing.
        """
        sql = await _executed_sql(review_service.list_pending_reviews, user_id="")

        assert "EXISTS" in sql, f"empty user_id fell through to an unscoped listing:\n{sql}"
        assert "user_id = ''" in sql

    async def test_no_user_id_stays_unscoped_for_internal_callers(self):
        """Omitting user_id keeps the trusted-caller behaviour (pipeline, CLI)."""
        sql = await _executed_sql(review_service.list_pending_reviews, user_id=None)

        assert "EXISTS" not in sql
        assert "lecture_artifacts" not in sql
