"""Account export and deletion.

Deleting an account has to remove every row a user owns, across 40 tables,
without tripping a foreign key on the way. Three design choices make that
maintainable:

* **Ownership is snapshotted first.** `collect_owned_ids()` resolves the parent
  IDs before anything is deleted, and the predicates match against those literal
  lists. Scoping a child with a live subquery over its parent looks equivalent
  but is not: a child deleted after its parent matches nothing and is left
  behind. See `OwnedIds` for the bug this actually caused.
* **Ordering comes from SQLAlchemy**, not from a hand-kept list. Iterating
  `Base.metadata.sorted_tables` in reverse orders children before parents, so
  adding a table with a new relationship cannot silently break the sequence.
  Two FK cycles make that order ambiguous; `_ordered_tables()` explains why
  that is harmless and which test holds it that way.
* **Every table must be classified.** Each one is either user-scoped (with a
  predicate saying which rows belong to the user) or explicitly global.
  `tests/unit/services/test_account_deletion.py` fails on any table that is
  neither, so a new user-owned table cannot be forgotten here.

The rows are only half the job. `purge_user_storage()` removes the blobs, and
it has no `Base.metadata` to enumerate from — every storage namespace has to be
derived from a key builder by hand, which is a weaker guarantee. #97 is what
that costs: the purge swept `summaries/<artifact_id>`, a prefix no summary key
has ever used, so the rows vanished while the files stayed. Read that function's
docstring before adding a namespace.

`tests/integration/test_account_deletion.py` exercises all of this against a
real database — the unit tests can only check the shape of the predicates.
"""

import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.storage import StorageBackend, get_storage
from app.models.artifact import LectureArtifact
from app.models.chat_session import ChatSession
from app.models.concept import Concept
from app.models.course import Course
from app.models.exam import Exam
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services import preview_service, summary_service

logger = structlog.get_logger()

# Tables that belong to nobody: shared catalogs, and `users` itself (deleted
# last, by primary key). Anything not here and not user-scoped is a bug.
GLOBAL_TABLES = frozenset(
    {
        "achievements",
        "daily_challenges",
        "alembic_version",
        "users",
        # Invites survive their creator: `created_by` is ON DELETE SET NULL, so
        # revoking access to one tester does not void codes held by others.
        "invite_codes",
    }
)


def _ordered_tables() -> list[Any]:
    """All mapped tables, parents first.

    SQLAlchemy warns that it cannot fully sort the schema: `assessments` and
    `course_documents` reference each other, as do `users` and `invite_codes`.
    Both cycles are safe to ignore here because every edge in them is
    ON DELETE SET NULL or CASCADE — never RESTRICT — so either order works.
    `test_cyclic_foreign_keys_are_nullable_or_cascading` holds that property in
    place; if someone adds a RESTRICT edge to a cycle, that test fails.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*unresolvable cycles.*")
        return list(Base.metadata.sorted_tables)


# ── Ownership ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OwnedIds:
    """Primary keys of the parent rows a user owns.

    Resolved **once, before any deletion**, and then used as literal ID lists.

    This is not an optimization — it is what makes deletion correct. An earlier
    version scoped child tables with live subqueries (`artifact_id IN (SELECT id
    FROM lecture_artifacts WHERE user_id = ...)`). Any child deleted *after* its
    parent then matched nothing and was silently left behind. `review_items` has
    no foreign key at all, so it sorted after `lecture_artifacts` and survived
    deletion entirely. Snapshotting the IDs first removes the ordering hazard.
    """

    artifacts: list[str]
    courses: list[str]
    exams: list[str]
    chat_sessions: list[str]
    concepts: list[str]
    quiz_questions: list[str]

    @classmethod
    def empty(cls) -> "OwnedIds":
        """A probe instance for table classification."""
        return cls([], [], [], [], [], [])


async def collect_owned_ids(session: AsyncSession, user_id: str) -> OwnedIds:
    """Snapshot the IDs of every parent row the user owns.

    Args:
        session: Database session.
        user_id: The user being purged or exported.

    Returns:
        The owned primary keys.
    """

    async def ids(statement: Select) -> list[str]:
        return list((await session.execute(statement)).scalars().all())

    courses = await ids(select(Course.id).where(Course.user_id == user_id))
    artifacts = await ids(select(LectureArtifact.id).where(LectureArtifact.user_id == user_id))
    return OwnedIds(
        artifacts=artifacts,
        courses=courses,
        exams=await ids(select(Exam.id).where(Exam.user_id == user_id)),
        chat_sessions=await ids(select(ChatSession.id).where(ChatSession.user_id == user_id)),
        concepts=await ids(select(Concept.id).where(Concept.user_id == user_id)),
        quiz_questions=await ids(
            select(QuizQuestion.id).where(QuizQuestion.course_id.in_(courses))
        ),
    )


def _build_predicates(table: Any, user_id: str, owned: OwnedIds) -> Any:
    """Return the WHERE clause selecting this user's rows in `table`.

    Args:
        table: A SQLAlchemy Table.
        user_id: The user being purged.
        owned: Pre-resolved IDs of the parent rows the user owns.

    Returns:
        A SQLAlchemy boolean clause, or None if the table is not user-scoped.
    """
    cols = table.c

    # The common case — an explicit tenancy column.
    if "user_id" in cols:
        return cols.user_id == user_id

    name = table.name

    # Children reached through a parent the user owns.
    if name in ("chunks", "extractions", "pipeline_runs"):
        return cols.artifact_id.in_(owned.artifacts)
    if name in ("flashcards", "quiz_questions"):
        return cols.course_id.in_(owned.courses) | cols.source_artifact_id.in_(owned.artifacts)
    if name in ("summaries", "assessments", "deadlines"):
        return cols.course_id.in_(owned.courses)
    if name == "chat_messages":
        return cols.session_id.in_(owned.chat_sessions)
    if name == "concept_relations":
        return cols.source_concept_id.in_(owned.concepts) | cols.target_concept_id.in_(
            owned.concepts
        )
    if name == "quiz_attempts":
        return cols.exam_id.in_(owned.exams) | cols.quiz_question_id.in_(owned.quiz_questions)
    if name == "review_items":
        # Polymorphic: no FK, referenced by entity_type + entity_id.
        return cols.entity_id.in_(owned.artifacts + owned.courses)

    return None


def classify_tables() -> tuple[list[str], list[str]]:
    """Split every mapped table into (user-scoped, global).

    Used by the guard test to prove no table is unaccounted for.

    Returns:
        (user_scoped_table_names, unclassified_table_names)
    """
    user_scoped: list[str] = []
    unclassified: list[str] = []
    for table in _ordered_tables():
        if table.name in GLOBAL_TABLES:
            continue
        if _build_predicates(table, "probe", OwnedIds.empty()) is not None:
            user_scoped.append(table.name)
        else:
            unclassified.append(table.name)
    return user_scoped, unclassified


# ── Deletion ─────────────────────────────────────────────────────────


async def purge_user_storage(
    session: AsyncSession, user_id: str, storage: StorageBackend | None = None
) -> int:
    """Delete the user's uploaded and generated files from blob storage.

    Storage keys are not namespaced per user, so every key has to be derived
    from rows the user owns. That is why this runs *before* the table-driven
    row deletion in `delete_user_account`, and why it issues its own queries
    instead of taking `OwnedIds`: it is callable on its own, and a version that
    depended on the caller having snapshotted first would be a trap.

    **Each namespace is asked the same question: is this key reachable from
    what the purge enumerates?** The shape of #97 was that it enumerated by
    artifact only, which structurally cannot reach a key scoped any other way:

    * ``uploads/<artifact_id>_<name>`` — ``lecture_artifacts.file_path``, by key.
    * ``extractions/<artifact_id>/...`` — a prefix per artifact.
    * ``previews/v<N>/<artifact_id>.pdf`` — exact keys, every cache version, via
      `preview_service.preview_keys_for_artifact`. Artifact-scoped, but it was
      *not* reachable before #97: nothing swept it at all.
    * ``summaries/<course_id>/...`` — a prefix per **course**, via
      `summary_service.summary_key_prefix_for_course`. This is the #97 bug:
      the prefix used to be built from the artifact id, which no summary key
      has ever carried, so the whole branch was a permanent no-op and every
      summary file outlived the account that produced it.

    The two course/preview prefixes come from the key builders rather than
    being spelled out again here, so changing a key shape cannot leave this
    sweeping a prefix nothing is stored under. ``extractions/`` is still
    literal: its only builder is inline in `app.pipeline.extract`, and reaching
    into the pipeline layer from here to borrow it is not worth the coupling.

    The prefixes carry no trailing slash, which is only safe because
    `generate_id` is UUID7: every id is the same length, so no id can be a
    string prefix of another. `LocalStorageBackend` resolves a prefix to a
    directory and is unaffected either way, but S3's `list_objects_v2` matches
    on the raw string — under variable-length ids, one user's sweep could reach
    another's objects, and a trailing slash would become load-bearing.

    ``courseops/<sha256[:16]>_<name>`` is **deliberately not purged**. It is
    content-addressed with no owner in the key, so it is reachable from neither
    artifacts nor courses, and two users who upload the same handbook share one
    blob byte for byte — deleting it on one account's closure would silently
    remove the other user's document. Needs ownership tracking (or refcounting)
    before it can be purged safely; see the issue thread on #97.

    Args:
        session: Database session.
        user_id: The user being purged.
        storage: Storage backend, defaulting to the configured singleton.

    Returns:
        Number of storage objects deleted.
    """
    store = storage if storage is not None else get_storage()

    artifacts = (
        await session.execute(
            select(LectureArtifact.id, LectureArtifact.file_path).where(
                LectureArtifact.user_id == user_id
            )
        )
    ).all()
    course_ids = list(
        (await session.execute(select(Course.id).where(Course.user_id == user_id))).scalars().all()
    )

    keys: list[str] = []
    prefixes: list[str] = []
    for artifact_id, storage_key in artifacts:
        if storage_key:
            keys.append(storage_key)
        keys.extend(preview_service.preview_keys_for_artifact(artifact_id))
        prefixes.append(f"extractions/{artifact_id}")
    prefixes.extend(summary_service.summary_key_prefix_for_course(cid) for cid in course_ids)

    deleted = 0
    for key in keys:
        try:
            # Count what was actually there, so the number reported is not
            # inflated by every cache version an artifact never had.
            if await store.exists(key):
                await store.delete(key)
                deleted += 1
        except Exception:
            # A missing or unreadable blob must not block the account deletion.
            logger.warning("storage_delete_failed", key=key, user_id=user_id, exc_info=True)

    for prefix in prefixes:
        try:
            deleted += await store.delete_prefix(prefix)
        except Exception:
            logger.warning(
                "storage_delete_prefix_failed", prefix=prefix, user_id=user_id, exc_info=True
            )

    logger.info(
        "user_storage_purged",
        user_id=user_id,
        objects_deleted=deleted,
        artifacts=len(artifacts),
        courses=len(course_ids),
    )
    return deleted


async def delete_user_account(
    session: AsyncSession, user_id: str, storage: StorageBackend | None = None
) -> dict[str, int]:
    """Hard-delete a user and everything they own.

    Deletes in reverse dependency order so no foreign key is violated, then
    removes the user row itself. The caller commits.

    Args:
        session: Database session.
        user_id: The user to delete.
        storage: Storage backend, defaulting to the configured singleton. Tests
            pass a backend rooted in a temporary directory — this function
            deletes files, so it must never be pointed at a real data dir.

    Returns:
        Mapping of table name to rows deleted (tables with 0 rows omitted).
    """
    # Snapshot ownership before anything is deleted — see OwnedIds.
    owned = await collect_owned_ids(session, user_id)

    # Enumerate blobs before the rows they are derived from are gone: the purge
    # reads `lecture_artifacts` and `courses` to build its keys (#97).
    objects_deleted = await purge_user_storage(session, user_id, storage)

    counts: dict[str, int] = {}
    for table in reversed(_ordered_tables()):
        if table.name in GLOBAL_TABLES:
            continue
        predicate = _build_predicates(table, user_id, owned)
        if predicate is None:
            # classify_tables()'s guard test keeps this unreachable; if a new
            # table slips through, log it rather than silently leaving data.
            logger.error("account_delete_unclassified_table", table=table.name)
            continue
        result = await session.execute(delete(table).where(predicate))
        if result.rowcount:
            counts[table.name] = result.rowcount

    result = await session.execute(delete(User.__table__).where(User.__table__.c.id == user_id))
    counts["users"] = result.rowcount

    logger.info(
        "user_account_deleted",
        user_id=user_id,
        tables_touched=len(counts),
        storage_objects_deleted=objects_deleted,
    )
    return counts


# ── Export ───────────────────────────────────────────────────────────


def _serialize(value: Any) -> Any:
    """JSON-safe representation of a column value."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)


# Columns that must never appear in an export handed to the user.
EXPORT_EXCLUDED_COLUMNS = frozenset(
    {
        "hashed_password",
        "mfa_secret",
        "backup_codes",
        "token_hash",
        "access_token",
        "refresh_token",
        "stripe_customer_id",
        "stripe_subscription_id",
    }
)


async def export_user_data(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Export everything a user owns as a JSON-serializable dict.

    Covers the same tables as deletion, so "download my data" and "delete my
    data" cannot disagree about what is owned. Credential columns are excluded.

    Args:
        session: Database session.
        user_id: The user to export.

    Returns:
        `{"exported_at": ..., "user_id": ..., "tables": {name: [rows]}}`
    """
    owned = await collect_owned_ids(session, user_id)
    tables: dict[str, list[dict[str, Any]]] = {}

    for table in _ordered_tables():
        if table.name in GLOBAL_TABLES:
            continue
        predicate = _build_predicates(table, user_id, owned)
        if predicate is None:
            continue
        result = await session.execute(select(table).where(predicate))
        rows = [
            {
                key: _serialize(value)
                for key, value in row._mapping.items()
                if key not in EXPORT_EXCLUDED_COLUMNS
            }
            for row in result
        ]
        if rows:
            tables[table.name] = rows

    # The user's own row, minus credentials.
    user_result = await session.execute(
        select(User.__table__).where(User.__table__.c.id == user_id)
    )
    user_row = user_result.first()
    if user_row is not None:
        tables["users"] = [
            {
                key: _serialize(value)
                for key, value in user_row._mapping.items()
                if key not in EXPORT_EXCLUDED_COLUMNS
            }
        ]

    logger.info("user_data_exported", user_id=user_id, tables=len(tables))
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "tables": tables,
    }
