"""Floor 4 — user data is never lost.

    nothing deletes uploads or generated content under data/ except explicit
    account deletion and the explicit user-initiated deletes of the user's own
    items enumerated in ADR 0004, and dedup/re-summarize/asset regeneration
    never destroys prior versions or study history

Static inventories (exact in both directions, so a new delete site fails until
someone classifies it, and a removed one fails until it is unlisted):

* every blob/file delete in ``app/**`` (``StorageBackend.delete`` /
  ``delete_prefix``, ``Path.unlink``, ``os.remove``, ``shutil.rmtree``);
* every DB delete of an uploaded or generated-content model.

Each site is one of:

* ``SANCTIONED`` — account deletion, one of ADR 0004's user-item deletes
  (exact allowlist, callers pinned), a temp file outside ``data/``, or a
  *move* (write the new key, then drop the old one) where the content survives;
* ``PENDING_RULING`` — the floor's text and a shipped, documented behaviour
  disagree and the user has not ruled. Empty since the 2026-10-04 rulings;
  ``test_floor4_no_delete_site_awaits_a_ruling`` keeps it that way;
* ``VIOLATIONS`` — a live breach. ``test_floor4_no_violation_site_remains`` is
  red while any is still in the code. A fixed site may vanish from the code
  before it is unlisted here; the inventory does not call that stale.

Plus behaviour: account purge and every user-item delete are reachable only
from their routes; lecture dedup writes and deletes nothing; re-summarize and
merge ``keep_source`` retain the superseded summary (row and blob); asset
regeneration keeps study history.
"""

from __future__ import annotations

import ast
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.safety._source import app_modules, dotted, parse, rel, walk_with_scope

# ── inventory 1: blob and file deletes ─────────────────────────────────

STORAGE_PRIMITIVES = "app/core/storage.py"  # defines delete/delete_prefix; not a caller
NOT_STORAGE_RECEIVERS = frozenset({"session", "db", "router", "client", "pipe", "r"})

# ── ADR 0004: explicit user-initiated deletes of the user's own items ──
# Verbatim from docs/adr/0004-floor4-user-initiated-item-deletes.md, Decision 3.
# Changing one of these sets is changing the floor: it needs ADR 0004 amended
# with the user's agreement, not a drive-by edit here.

#: (module, function) of each content-row delete this ADR sanctions.
USER_ITEM_DB_DELETE_SITES = {
    ("app/services/course_service.py", "delete_course"),
    ("app/services/course_service.py", "_discard_summary"),
    ("app/services/courseops_service.py", "delete_course_document"),
    ("app/services/courseops_service.py", "delete_deadline"),
    ("app/services/chat_service.py", "delete_session"),
}

#: (module, function, callee) of each blob delete this ADR sanctions.
USER_ITEM_BLOB_DELETE_SITES = {
    ("app/services/courseops_service.py", "_delete_blob_if_unreferenced", "store.delete"),
    ("app/services/course_service.py", "_discard_summary", "storage.delete"),
}

#: Reachability: callee (module, function) -> the exact set of its callers in app/**.
#: "Explicit" (condition 1) is pinned by these edges, so a new caller fails the floor.
USER_ITEM_DELETE_CALLERS = {
    ("app/services/course_service.py", "delete_course"): {
        ("app/api/courses.py", "delete_course"),
    },
    ("app/services/course_service.py", "merge_courses"): {
        ("app/api/courses.py", "merge_course"),
    },
    ("app/services/course_service.py", "_discard_summary"): {
        ("app/services/course_service.py", "merge_courses"),
    },
    ("app/services/courseops_service.py", "delete_course_document"): {
        ("app/api/courseops.py", "delete_document"),
    },
    ("app/services/courseops_service.py", "delete_deadline"): {
        ("app/api/courseops.py", "delete_deadline"),
    },
    ("app/services/chat_service.py", "delete_session"): {
        ("app/api/chat.py", "delete_session"),
    },
}

_ADR_0004_ITEM = {
    ("app/services/course_service.py", "delete_course"): (
        "ADR 0004 #1: DELETE /api/courses/{code} (X-Confirm); the course and its DB "
        "children, no blob"
    ),
    ("app/services/courseops_service.py", "delete_course_document"): (
        "ADR 0004 #2: DELETE /api/courseops/documents/{id}; one course_documents row"
    ),
    ("app/services/courseops_service.py", "_delete_blob_if_unreferenced"): (
        "ADR 0004 #2: the document's blob, only if no other row of the same user "
        "references it, only under courseops/<user_id>/. The failed-upload caller is "
        "sanctioned separately (REFERENCE_CHECKED_DELETE_CALLERS)"
    ),
    ("app/services/courseops_service.py", "delete_deadline"): (
        "ADR 0004 #3: DELETE /api/courseops/deadlines/{id}; one deadlines row"
    ),
    ("app/services/chat_service.py", "delete_session"): (
        "ADR 0004 #4: DELETE /api/chat/sessions/{id}; one session and its messages"
    ),
    ("app/services/course_service.py", "_discard_summary"): (
        "ADR 0004 #5 (narrowed on acceptance): merge-discard of the SOURCE-side "
        "summary row and blob only. The keep_source overwrite of the target is not "
        "this exemption; see test_floor4_merge_keep_source_snapshots_target_summary"
    ),
}

#: (module, function, callee) -> reason.
BLOB_SANCTIONED = {
    **{site: _ADR_0004_ITEM[site[:2]] for site in USER_ITEM_BLOB_DELETE_SITES},
    ("app/services/account_service.py", "purge_user_storage", "store.delete"): (
        "explicit account deletion; reachability pinned by "
        "test_floor4_account_purge_reachable_only_from_account_deletion"
    ),
    ("app/services/account_service.py", "purge_user_storage", "store.delete_prefix"): (
        "explicit account deletion (as above)"
    ),
    ("app/agents/claude_code.py", "ClaudeCodeAdapter._run_claude_code", "shutil.rmtree"): (
        "per-call tempfile.mkdtemp() credentials dir, outside data/"
    ),
    ("app/pipeline/classify.py", "_extract_text_preview", "path.unlink"): (
        "NamedTemporaryFile an S3 object was downloaded into, outside data/; "
        "the local-storage branch never unlinks"
    ),
    ("app/services/course_service.py", "_sync_summary_blob", "storage.delete"): (
        "move: the row's content_md is written to the new key first, then the "
        "old key dropped; the row is the source of truth"
    ),
    ("app/services/summary_service.py", "backfill_summary_storage_keys", "store.delete"): (
        "one-off key migration (#92): content rewritten to the new key first, "
        "only legacy keys not equal to any new key are dropped"
    ),
    ("app/services/courseops_service.py", "backfill_courseops_storage_keys", "store.delete"): (
        "one-off key migration (#107): rows rewritten first; a legacy key still "
        "referenced by any row is kept"
    ),
}

#: Floor questions the user has not ruled on. Emptied by the 2026-10-04
#: rulings (ADR 0004 for the item deletes).
BLOB_PENDING_RULING: dict[tuple[str, str, str], str] = {}

#: Empty since M31-S1-BACKEND-008 (a2cd687). Both courseops upload routes used
#: to ``storage.delete(storage_key)`` on failure, which for a re-upload of the
#: same file is the key an existing document points at. They now go through
#: ``courseops_service.discard_failed_upload_blob`` (classified below). The
#: behavioural tests further down stay as the regression pins.
BLOB_VIOLATIONS: dict[tuple[str, str, str], str] = {}

#: ``_delete_blob_if_unreferenced`` is one ``store.delete`` site with more than
#: one meaning, so its callers are pinned exactly as well. A new caller has to
#: be classified here; it cannot inherit the classification of the delete site.
#: (module, caller) -> classification and reason.
REFERENCE_CHECKED_DELETE_CALLERS = {
    ("app/services/courseops_service.py", "delete_course_document"): (
        "SANCTIONED: ADR 0004 #2, the user deletes one course document; its own "
        "callers are pinned in USER_ITEM_DELETE_CALLERS"
    ),
    ("app/services/courseops_service.py", "discard_failed_upload_blob"): (
        "SANCTIONED: cleanup of the blob a failed upload request just wrote. The "
        "helper refuses keys outside the caller's own courseops/<user_id>/ prefix "
        "and deletes only when no CourseDocument row of that user (course "
        "documents and assessment attachments share the table) points at the key"
    ),
}

#: ``discard_failed_upload_blob`` deletes whatever the caller hands it (subject
#: to the reference check), so it may be called only from the failure branch of
#: the two upload routes, with the key that request built.
DISCARD_FAILED_UPLOAD_CALLERS = {
    ("app/api/courseops.py", "upload_course_document"),
    ("app/api/courseops.py", "upload_assessment_document"),
}


def blob_delete_sites() -> dict[tuple[str, str, str], str]:
    """Every call that removes a blob or file, keyed (module, function, callee)."""
    found: dict[tuple[str, str, str], str] = {}
    for path in app_modules(exclude=(STORAGE_PRIMITIVES,)):
        module = rel(path)
        for node, scope in walk_with_scope(parse(path)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr = node.func.attr
            receiver = dotted(node.func.value)
            callee = dotted(node.func)
            if attr in {"delete", "delete_prefix"}:
                if receiver in NOT_STORAGE_RECEIVERS or "redis" in receiver:
                    continue
            elif attr in {"unlink", "rmdir"}:
                if receiver.endswith("_service"):  # telegram_service.unlink: not a file
                    continue
            elif callee not in {"os.remove", "os.unlink", "os.rmdir", "shutil.rmtree"}:
                continue
            found[(module, scope, callee)] = f"{module}:{node.lineno}"
    return found


# ── inventory 2: DB deletes of uploaded / generated content ────────────

CONTENT_MODELS = frozenset(
    {
        "LectureArtifact",
        "Extraction",
        "Summary",
        "SummaryVersion",
        "Flashcard",
        "FlashcardReview",
        "QuizQuestion",
        "QuizAttempt",
        "Chunk",
        "CourseDocument",
        "Course",
        "Concept",
        "ConceptRelation",
        "ChatSession",
        "ChatMessage",
        "StudySession",
        "Exam",
        "Assessment",
        "Deadline",
    }
)

#: (module, function) -> reason. ``session.delete(x)`` is listed whatever x is:
#: the type is not knowable statically, so every one is classified by hand.
DB_SANCTIONED = {
    **{site: _ADR_0004_ITEM[site] for site in USER_ITEM_DB_DELETE_SITES},
    ("app/services/index_service.py", "index_artifact_chunks"): (
        "chunks are a derived search index, rebuilt from the stored extraction"
    ),
    ("app/services/gcal_service.py", "disconnect_calendar"): (
        "session.delete(cal_sync): a calendar connection, not content"
    ),
    ("app/services/telegram_service.py", "unlink"): (
        "session.delete(link): a Telegram link, not content"
    ),
}

#: Emptied by the 2026-10-04 rulings: item deletes went to ADR 0004
#: (DB_SANCTIONED), regeneration to DB_VIOLATIONS ("fix the code").
DB_PENDING_RULING: dict[tuple[str, str], str] = {}

#: Live breaches. Ruled "fix the code" on 2026-10-04 (R-007, ADR 0004 §4);
#: M31-S2-BACKEND-019 archives (``archived_at``) instead of deleting.
DB_VIOLATIONS = {
    ("app/services/asset_service.py", "save_flashcards"): (
        "regeneration deletes the artifact's flashcards; flashcard_reviews "
        "cascade, so SRS history is lost. "
        "Behaviour: test_floor4_asset_regeneration_keeps_study_history"
    ),
    ("app/services/asset_service.py", "save_quiz_questions"): (
        "regeneration deletes the artifact's quiz questions; quiz_attempts cascade"
    ),
}


def db_content_delete_sites() -> dict[tuple[str, str], str]:
    """Functions that DELETE content rows, keyed (module, function)."""
    found: dict[tuple[str, str], str] = {}
    for path in app_modules():
        module = rel(path)
        for node, scope in walk_with_scope(parse(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Name)
                and func.id == "delete"
                and node.args
                and dotted(node.args[0]) in CONTENT_MODELS
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "delete"
                and dotted(func.value) in {"session", "db"}
            ):
                found.setdefault((module, scope), f"{module}:{node.lineno}")
    return found


# The account purge deletes every owned table generically (``delete(table)``),
# so it never matches a model name above; its reachability is pinned instead.


def _assert_exact(found: dict, *classified: dict, violations: dict, what: str) -> None:
    """``found`` equals the classified sets; a violation may already be fixed away.

    Sanctioned and pending entries are pinned both ways. A ``violations`` entry
    is not called stale when it disappears, so the code fix can land green
    before safety unlists it; ``test_floor4_no_violation_site_remains`` holds
    the other direction.
    """
    known = set().union(*classified)
    new = {k: v for k, v in found.items() if k not in known and k not in violations}
    stale = sorted(known - set(found))
    assert not new, (
        f"Floor 4: unclassified {what}:\n"
        + "\n".join(f"  {loc}  {key}" for key, loc in sorted(new.items()))
        + "\nA delete of user data is allowed only on account deletion and the "
        "user-item deletes ADR 0004 enumerates. Classify it in "
        "tests/safety/test_floor4_user_data_never_lost.py with a reason, or remove it."
    )
    assert not stale, f"Classified {what} no longer present — unlist them:\n" + "\n".join(
        f"  {k}" for k in stale
    )


def test_floor4_every_blob_delete_is_classified():
    """No blob/file delete exists outside the classified inventory."""
    _assert_exact(
        blob_delete_sites(),
        BLOB_SANCTIONED,
        BLOB_PENDING_RULING,
        violations=BLOB_VIOLATIONS,
        what="blob/file delete site(s)",
    )


def test_floor4_every_content_row_delete_is_classified():
    """No DB delete of uploaded/generated content exists outside the inventory."""
    _assert_exact(
        db_content_delete_sites(),
        DB_SANCTIONED,
        DB_PENDING_RULING,
        violations=DB_VIOLATIONS,
        what="content row delete(s)",
    )


def test_floor4_no_delete_site_awaits_a_ruling():
    """Every delete of user data is sanctioned, ruled a violation, or gone.

    The 2026-10-04 rulings emptied both pending dicts (ADR 0004 for the item
    deletes, "fix the code" for regeneration). A new entry here is a floor
    question for the user, and the floor is not green while one is open.
    """
    pending = {**BLOB_PENDING_RULING, **DB_PENDING_RULING}
    assert not pending, "\n".join(f"  {k}: {v}" for k, v in pending.items())


def test_floor4_user_item_allowlist_is_exactly_adr_0004():
    """The sanctioned user-item sites are ADR 0004's, and every one is still in the code.

    The inventory tests prove nothing outside the classified sets deletes.
    This proves the ADR 0004 part of the classification is the ADR's list and
    nothing wider: a site cannot be slipped into DB_SANCTIONED under another
    reason and still claim the exemption.
    """
    db_found = set(db_content_delete_sites())
    blob_found = set(blob_delete_sites())
    assert db_found >= USER_ITEM_DB_DELETE_SITES, USER_ITEM_DB_DELETE_SITES - db_found
    assert blob_found >= USER_ITEM_BLOB_DELETE_SITES, USER_ITEM_BLOB_DELETE_SITES - blob_found
    adr_db = {k for k, v in DB_SANCTIONED.items() if v.startswith("ADR 0004")}
    adr_blob = {k for k, v in BLOB_SANCTIONED.items() if v.startswith("ADR 0004")}
    assert adr_db == USER_ITEM_DB_DELETE_SITES
    assert adr_blob == USER_ITEM_BLOB_DELETE_SITES
    assert {k[:2] for k in USER_ITEM_BLOB_DELETE_SITES} | USER_ITEM_DB_DELETE_SITES <= set(
        _ADR_0004_ITEM
    )


# ── account purge reachability ─────────────────────────────────────────


def _callers(name: str) -> set[tuple[str, str]]:
    out = set()
    for path in app_modules():
        for node, scope in walk_with_scope(parse(path)):
            if isinstance(node, ast.Call):
                callee = dotted(node.func)
                if callee == name or callee.endswith(f".{name}"):
                    out.add((rel(path), scope))
    return out


def test_floor4_account_purge_reachable_only_from_account_deletion():
    """purge_user_storage <- delete_user_account <- {DELETE /api/auth/account, admin delete}."""
    assert _callers("purge_user_storage") == {
        ("app/services/account_service.py", "delete_user_account")
    }
    assert _callers("delete_user_account") == {
        ("app/api/auth.py", "delete_account"),
        ("app/services/admin_service.py", "delete_user"),
    }
    assert _callers("admin_service.delete_user") == {("app/api/admin.py", "delete_user")}


def test_floor4_user_item_deletes_reachable_only_from_their_routes():
    """ADR 0004 condition 1 ("explicit"): each sanctioned delete has exactly its listed callers.

    Callers are matched by function name across ``app/**``, so a same-named
    function elsewhere shows up as an extra caller and fails here rather than
    hiding one. A Celery task, a beat job or another route reaching one of
    these deletes needs ADR 0004 amended first.
    """
    for (module, function), callers in USER_ITEM_DELETE_CALLERS.items():
        found = _callers(function)
        assert found == callers, (
            f"Floor 4: {module}:{function} is an ADR 0004 user-item delete and must be "
            f"reached only from its route.\n  found:  {sorted(found)}\n  listed: {sorted(callers)}"
        )


def test_floor4_reference_checked_delete_has_only_classified_callers():
    """The shared courseops blob delete is reached only from classified callers.

    ``store.delete`` inside ``_delete_blob_if_unreferenced`` is one site in the
    blob inventory, but it serves both a user's single-document delete (pending
    a ruling) and the failed-upload cleanup (sanctioned). Pinning the callers
    keeps a third use from hiding behind either classification.
    """
    assert _callers("_delete_blob_if_unreferenced") == set(REFERENCE_CHECKED_DELETE_CALLERS)
    assert _callers("discard_failed_upload_blob") == DISCARD_FAILED_UPLOAD_CALLERS


# ── dedup ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor4_lecture_upload_dedup_writes_and_deletes_nothing(async_client, simple_pdf):
    """A duplicate lecture upload is a no-op: no store, no delete, same artifact id."""
    from app.core.storage import LocalStorageBackend

    existing = MagicMock(id="existing-artifact")
    with (
        patch("app.api.uploads.quota_service.check_upload_quota", new=AsyncMock()),
        patch("app.api.uploads.quota_service.check_ai_quota", new=AsyncMock()),
        patch(
            "app.api.uploads.artifact_service.check_duplicate",
            new=AsyncMock(return_value=existing),
        ),
        patch("app.api.uploads.artifact_service.create_upload_artifact", new=AsyncMock()) as create,
        patch.object(LocalStorageBackend, "put", new=AsyncMock()) as put,
        patch.object(LocalStorageBackend, "delete", new=AsyncMock()) as delete,
        patch.object(LocalStorageBackend, "delete_prefix", new=AsyncMock()) as delete_prefix,
        patch("app.api.uploads.run_pipeline") as run_pipeline,
    ):
        response = await async_client.post(
            "/api/uploads",
            files={"file": ("lecture.pdf", simple_pdf.read_bytes(), "application/pdf")},
        )

    assert response.status_code in (200, 201), response.text
    assert response.json()["status"] == "duplicate"
    assert response.json()["artifact_id"] == "existing-artifact"
    create.assert_not_awaited()
    put.assert_not_awaited()
    delete.assert_not_awaited()
    delete_prefix.assert_not_awaited()
    run_pipeline.assert_not_called()


async def _seed_existing_courseops_blob(user_id: str, content: bytes, filename: str) -> str:
    from app.core.storage import get_storage
    from app.services import courseops_service

    sha = hashlib.sha256(content).hexdigest()
    key = courseops_service.courseops_key(user_id, sha, filename)
    await get_storage().put(key, content)
    return key


def _references(rows: set[tuple[str, str]]):
    """A fake ``session.execute`` holding ``course_documents`` rows (user_id, file_path).

    Answers a ``count`` over ``course_documents`` with the number of rows the
    statement's ``user_id`` and ``file_path`` binds both match, the way the
    database would. Every other statement finds nothing. The shared
    ``mock_session`` would otherwise answer every count with a truthy
    ``MagicMock``, so a cleanup that skipped the reference check would still
    look like it kept the blob.
    """

    def execute(statement, *_a, **_k):
        from tests.safety._tenant import tables_in

        result = MagicMock()
        result.scalar_one.return_value = 0
        result.scalar.return_value = 0
        result.scalar_one_or_none.return_value = None
        if "course_documents" in tables_in(statement):
            binds = {v for v in statement.compile().params.values() if isinstance(v, str)}
            hits = sum(1 for user_id, key in rows if user_id in binds and key in binds)
            result.scalar_one.return_value = hits
            result.scalar.return_value = hits
        return result

    return AsyncMock(side_effect=execute)


@pytest.mark.asyncio
async def test_floor4_duplicate_course_document_upload_keeps_original_blob(
    async_client, mock_session, default_test_user, simple_pdf
):
    """Re-uploading a course document that already exists must not delete its file."""
    from app.core.storage import get_storage
    from app.services.courseops_service import CourseOpsError

    content = simple_pdf.read_bytes()
    key = await _seed_existing_courseops_blob(default_test_user.id, content, "outline.pdf")
    mock_session.execute = _references({(default_test_user.id, key)})

    with patch(
        "app.api.courseops.courseops_service.upload_course_document",
        new=AsyncMock(side_effect=CourseOpsError("Document already uploaded for CSIT302")),
    ):
        response = await async_client.post(
            "/api/courseops/documents?course_code=CSIT302&document_type=outline",
            files={"file": ("outline.pdf", content, "application/pdf")},
        )

    assert response.status_code == 409, response.text
    assert await get_storage().exists(key), (
        "Floor 4 VIOLATION: a duplicate course-document upload deleted the blob the "
        f"existing document points at ({key})."
    )


@pytest.mark.asyncio
async def test_floor4_failed_assessment_attach_keeps_existing_blob(
    async_client, mock_session, default_test_user, simple_pdf
):
    """A failed attach must not delete a blob another document of the user's uses."""
    from app.core.storage import get_storage

    content = simple_pdf.read_bytes()
    key = await _seed_existing_courseops_blob(default_test_user.id, content, "rubric.pdf")
    mock_session.execute = _references({(default_test_user.id, key)})

    with patch(
        "app.api.courseops.courseops_service.attach_assessment_document",
        new=AsyncMock(return_value=None),
    ):
        response = await async_client.post(
            "/api/courseops/assessments/no-such-assessment/documents?document_type=rubric",
            files={"file": ("rubric.pdf", content, "application/pdf")},
        )

    assert response.status_code == 404, response.text
    assert await get_storage().exists(key), (
        "Floor 4 VIOLATION: a failed assessment attach deleted the blob an existing "
        f"course document points at ({key})."
    )


@pytest.mark.asyncio
async def test_floor4_failed_upload_never_deletes_another_users_blob(
    async_client, mock_session, default_test_user, simple_pdf
):
    """User B's failed upload of user A's exact file leaves A's blob alone.

    Two halves. Through the route: B's failed attach of the same bytes under
    the same name must not touch the blob A's document points at. Directly: the
    cleanup must refuse a key outside the caller's own prefix even when nothing
    of the caller's references it, since a reference count over B's rows says
    nothing about A's.
    """
    from app.core.storage import get_storage
    from app.services import courseops_service

    owner_a = "00000000-0000-0000-0000-00000000000a"
    content = simple_pdf.read_bytes()
    key_a = await _seed_existing_courseops_blob(owner_a, content, "rubric.pdf")
    mock_session.execute = _references({(owner_a, key_a)})

    with patch(
        "app.api.courseops.courseops_service.attach_assessment_document",
        new=AsyncMock(return_value=None),
    ):
        response = await async_client.post(
            "/api/courseops/assessments/no-such-assessment/documents?document_type=rubric",
            files={"file": ("rubric.pdf", content, "application/pdf")},
        )
    assert response.status_code == 404, response.text
    assert await get_storage().exists(key_a), (
        f"Floor 4 VIOLATION: user B's failed upload deleted user A's blob ({key_a})."
    )

    session = AsyncMock()
    session.execute = _references(set())
    deleted = await courseops_service.discard_failed_upload_blob(
        session, default_test_user.id, key_a, get_storage()
    )
    assert deleted is False
    assert await get_storage().exists(key_a), (
        "Floor 4 VIOLATION: discard_failed_upload_blob deleted a blob under another "
        f"user's prefix ({key_a})."
    )


# ── re-summarize ───────────────────────────────────────────────────────


def _session_with_existing(existing) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result)
    return session


def _existing_summary():
    from app.models.summary import Summary

    return Summary(
        id="summary-1",
        course_id="course-1",
        week=3,
        content_md="# v1 content",
        file_path="summaries/course-1/Week3.md",
        version=1,
        source_artifacts=["artifact-1"],
    )


@pytest.mark.asyncio
async def test_floor4_resummarize_increments_version():
    """Same course+week summarized again is a version increment, not a duplicate row."""
    from app.services import summary_service

    existing = _existing_summary()
    session = _session_with_existing(existing)
    result = await summary_service.create_or_update_summary(
        session=session,
        course_id="course-1",
        week=3,
        content_md="# v2 content",
        file_path="summaries/course-1/Week3.md",
        source_artifact_ids=["artifact-2"],
    )
    assert result.version == 2
    assert result.content_md == "# v2 content"
    assert set(result.source_artifacts) == {"artifact-1", "artifact-2"}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VETO-relevant, awaiting user ruling: create_or_update_summary overwrites "
    "content_md in place and summarize.py rewrites the same Week<N>.md key, so "
    "version N-1 is destroyed; PRD.md specifies update-with-increment, floor 4 "
    "says re-summarize never destroys prior versions",
)
@pytest.mark.asyncio
async def test_floor4_resummarize_preserves_prior_version():
    """After re-summarizing, version 1's text still exists somewhere persistent.

    Implementation-agnostic: a fix may snapshot the old row into a history
    table (an object passed to ``session.add``) or insert a new row and leave
    the old one untouched. Either way ``# v1 content`` must survive.
    """
    from app.services import summary_service

    existing = _existing_summary()
    session = _session_with_existing(existing)
    await summary_service.create_or_update_summary(
        session=session,
        course_id="course-1",
        week=3,
        content_md="# v2 content",
        file_path="summaries/course-1/Week3.md",
        source_artifact_ids=["artifact-2"],
    )
    survivors = [existing] + [c.args[0] for c in session.add.call_args_list]
    assert any(getattr(o, "content_md", None) == "# v1 content" for o in survivors), (
        "Floor 4: re-summarize destroyed version 1 of the summary."
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VETO-relevant, awaiting user ruling: asset regeneration deletes the "
    "artifact's flashcards/quiz questions and their reviews/attempts cascade "
    "(see DB_PENDING_RULING)",
)
@pytest.mark.asyncio
async def test_floor4_asset_regeneration_keeps_study_history():
    """Regenerating assets never deletes a card or question a user has studied.

    Any DELETE on flashcards / quiz_questions must be conditioned on the
    absence of reviews / attempts; an unconditional one destroys history.
    """
    from sqlalchemy.sql.dml import Delete

    from app.agents.base import FlashcardData, QuizQuestionData
    from app.services import asset_service
    from tests.safety._tenant import tables_in

    captured = []

    def record(statement, *_a, **_k):
        captured.append(statement)
        result = MagicMock()
        result.scalar.return_value = 0
        return result

    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(side_effect=record)

    await asset_service.save_flashcards(
        session, "course-1", 3, "artifact-1", [FlashcardData(front="q", back="a")]
    )
    await asset_service.save_quiz_questions(
        session,
        "course-1",
        3,
        "artifact-1",
        [QuizQuestionData(question_type="short_answer", question="q", correct_answer="a")],
    )

    history_of = {"flashcards": "flashcard_reviews", "quiz_questions": "quiz_attempts"}
    unconditional = [
        str(s)
        for s in captured
        if isinstance(s, Delete)
        and s.table.name in history_of
        and history_of[s.table.name] not in tables_in(s)
    ]
    assert not unconditional, "Floor 4: regeneration deletes studied items:\n" + "\n".join(
        unconditional
    )
