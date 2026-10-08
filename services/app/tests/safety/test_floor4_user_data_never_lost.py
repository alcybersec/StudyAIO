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
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import isolated_storage
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


def test_floor4_no_violation_site_remains():
    """No delete site ruled a violation is still in the code.

    RED until M31-S2-BACKEND-019 removes the regeneration deletes
    (``asset_service.save_flashcards`` / ``save_quiz_questions``). Once it is
    green, safety unlists the entries; the inventory tests do not force that,
    so the code fix can land without editing this file.
    """
    live = {k: v for k, v in db_content_delete_sites().items() if k in DB_VIOLATIONS}
    live |= {k: v for k, v in blob_delete_sites().items() if k in BLOB_VIOLATIONS}
    assert not live, "Floor 4 VIOLATION: ruled delete site(s) still present:\n" + "\n".join(
        f"  {loc}  {key}: {(DB_VIOLATIONS | BLOB_VIOLATIONS).get(key)}"
        for key, loc in sorted(live.items())
    )


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


# ── re-summarize and merge keep_source: the superseded version survives ─
#
# Ruled 2026-10-04: "fix the code" for re-summarize, and merge keep_source
# "keeps as a version" (ADR 0004 § Amendment). Both pins are
# implementation-agnostic about *how* the snapshot is written (an ORM object
# handed to session.add/add_all, or an INSERT into summary_versions), and
# strict about *what* survives: a summary_versions row carrying the old text
# and version, and a blob at that row's file_path still holding the old bytes.
# RED until M31-S2-BACKEND-019 lands.

OWNER = "00000000-0000-0000-0000-0000000000a1"


def _recording_session(on_execute=None):
    """An AsyncMock session that records every add, add_all and execute.

    ``log`` gets ``("add", obj)`` and ``("execute", statement)`` in call order,
    each with a ``probe()`` value captured at that moment, so a test can ask
    what the target row held when the snapshot was written.
    """
    log: list[tuple[str, object, object]] = []
    probe = {"fn": lambda: None}
    session = AsyncMock()

    def add(obj, *_a, **_k):
        log.append(("add", obj, probe["fn"]()))

    def add_all(objs, *_a, **_k):
        for obj in objs:
            add(obj)

    def execute(statement, *_a, **_k):
        log.append(("execute", statement, probe["fn"]()))
        if on_execute is not None:
            return on_execute(statement)
        return MagicMock()

    session.add = MagicMock(side_effect=add)
    session.add_all = MagicMock(side_effect=add_all)
    session.execute = AsyncMock(side_effect=execute)
    session.scalar = AsyncMock(return_value=OWNER)  # e.g. the course owner's id
    return session, log, probe


def _snapshots(log) -> list[tuple[SimpleNamespace, object]]:
    """Every summary_versions row written, as (row, probe value at write time)."""
    from sqlalchemy.sql.dml import Insert

    from app.models.summary_version import SummaryVersion

    rows = []
    for kind, obj, seen in log:
        if kind == "add" and isinstance(obj, SummaryVersion):
            rows.append(
                (
                    SimpleNamespace(
                        content_md=obj.content_md,
                        version=obj.version,
                        file_path=obj.file_path,
                    ),
                    seen,
                )
            )
        elif kind == "execute" and isinstance(obj, Insert) and obj.table.name == "summary_versions":
            params = obj.compile().params
            rows.append(
                (
                    SimpleNamespace(
                        content_md=params.get("content_md"),
                        version=params.get("version"),
                        file_path=params.get("file_path"),
                    ),
                    seen,
                )
            )
    return rows


async def _blob(storage, key: str | None) -> bytes | None:
    from app.core.storage import normalize_storage_key

    if not key:
        return None
    try:
        return await storage.get(normalize_storage_key(key))
    except Exception:
        return None


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


def _found(existing):
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    return lambda _statement: result


@pytest.mark.asyncio
async def test_floor4_resummarize_increments_version():
    """Same course+week summarized again is a version increment, not a duplicate row."""
    from app.services import summary_service

    existing = _existing_summary()
    session, _log, _probe = _recording_session(_found(existing))
    with isolated_storage():
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


@pytest.mark.asyncio
async def test_floor4_resummarize_preserves_prior_version():
    """After re-summarizing, version 1 survives as a row and as a blob.

    The summarize stage writes the new markdown to the key it hands the service
    *before* calling it, so the test does the same. Version 1's snapshot must
    therefore point at a key that still holds version 1's bytes, which rules
    out pointing it at the key version 2 was just written to.
    """
    from app.core.storage import get_storage
    from app.services import summary_service

    existing = _existing_summary()
    key = existing.file_path
    session, log, _probe = _recording_session(_found(existing))
    with isolated_storage():
        storage = get_storage()
        await storage.put(key, b"# v1 content")  # what the first run stored
        await storage.put(key, b"# v2 content")  # what the second run stores first
        await summary_service.create_or_update_summary(
            session=session,
            course_id="course-1",
            week=3,
            content_md="# v2 content",
            file_path=key,
            source_artifact_ids=["artifact-2"],
        )
        assert existing.version == 2, "control: the re-summarize did not run"
        kept = [row for row, _seen in _snapshots(log) if row.content_md == "# v1 content"]
        assert kept, (
            "Floor 4 VIOLATION: re-summarize wrote no summary_versions row holding "
            "version 1, so version 1 of the summary is destroyed."
        )
        assert kept[0].version == 1, f"snapshot carries version {kept[0].version}, not 1"
        assert await _blob(storage, kept[0].file_path) == b"# v1 content", (
            "Floor 4 VIOLATION: version 1's summary_versions row points at "
            f"{kept[0].file_path!r}, which no longer holds version 1's markdown."
        )


def _merge_session(source, target, target_summary, source_summary):
    """Answer merge_courses' lookups the way the database would for one owner."""
    from tests.safety._tenant import bind_values, tables_in

    def execute(statement):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        tables = tables_in(statement)
        binds = set(bind_values(statement))
        if statement.is_select and tables == {"courses"} and OWNER in binds:
            course = source if "SRC" in binds else target if "TGT" in binds else None
            result.scalar_one_or_none.return_value = course
        elif statement.is_select and "summaries" in tables:
            if target.id in binds:
                result.scalars.return_value.all.return_value = [target_summary]
            elif source.id in binds:
                result.scalars.return_value.all.return_value = [source_summary]
        return result

    return execute


@pytest.mark.asyncio
async def test_floor4_merge_keep_source_snapshots_target_summary():
    """Merge keep_source writes a summary_versions row for the target before overwriting it.

    ADR 0004 § Amendment 2026-10-04: the overwritten target is not
    merge-discard; it is under the same retention rule as re-summarize.
    """
    from app.core.storage import get_storage
    from app.models.summary import Summary
    from app.services import course_service

    source = SimpleNamespace(id="course-src", user_id=OWNER, code="SRC", archived_at=None)
    target = SimpleNamespace(id="course-tgt", user_id=OWNER, code="TGT", archived_at=None)
    target_summary = Summary(
        id="sum-t",
        course_id=target.id,
        week=3,
        content_md="# target text",
        file_path=f"summaries/{target.id}/Week3.md",
        version=1,
        source_artifacts=["a-t"],
    )
    source_summary = Summary(
        id="sum-s",
        course_id=source.id,
        week=3,
        content_md="# source text",
        file_path=f"summaries/{source.id}/Week3.md",
        version=1,
        source_artifacts=["a-s"],
    )
    session, log, probe = _recording_session(
        _merge_session(source, target, target_summary, source_summary)
    )
    session.delete = AsyncMock()
    probe["fn"] = lambda: target_summary.content_md

    with isolated_storage():
        storage = get_storage()
        await storage.put(target_summary.file_path, b"# target text")
        await storage.put(source_summary.file_path, b"# source text")
        await course_service.merge_courses(session, OWNER, "SRC", "TGT", "keep_source")

        assert target_summary.content_md == "# source text", "control: keep_source did not run"
        assert target_summary.version == 2, "control: keep_source did not bump the version"
        kept = [(row, seen) for row, seen in _snapshots(log) if row.content_md == "# target text"]
        assert kept, (
            "Floor 4 VIOLATION: merge keep_source overwrote the target summary without "
            "writing a summary_versions row, so the target's version 1 is destroyed."
        )
        row, seen = kept[0]
        assert row.version == 1, f"snapshot carries version {row.version}, not 1"
        assert seen == "# target text", (
            "Floor 4: the summary_versions row was written after the target was overwritten."
        )
        assert await _blob(storage, row.file_path) == b"# target text", (
            "Floor 4 VIOLATION: the target's prior version row points at "
            f"{row.file_path!r}, which no longer holds its markdown."
        )


def _version_row(sv) -> dict[tuple[str, str], object]:
    cols = ("id", "user_id", "course_id", "week", "version", "file_path")
    return {("summary_versions", c): getattr(sv, c) for c in cols}


def _set_values(statement) -> dict[str, object]:
    """Column name -> value an UPDATE sets."""
    out = {}
    for key, bind in (statement._values or {}).items():  # noqa: SLF001
        name = getattr(key, "key", None) or getattr(key, "name", None) or str(key)
        out[name] = getattr(bind, "effective_value", bind)
    return out


@pytest.mark.asyncio
async def test_floor4_merge_carries_moved_summarys_versions_to_target():
    """A summary that merge moves to the target takes its retained versions with it.

    ``merge_courses`` moves a week summarized only in the source to the target
    and archives the emptied source. If the moved summary's ``summary_versions``
    rows stay keyed to the source, the user's later, sanctioned delete of that
    archived husk (ADR 0004 #1 deletes the course's ``summary_versions``)
    destroys the prior versions of a summary that lives on in the target:
    re-summarize history lost through a delete the user aimed at an empty
    course. ADR 0004 § 3 condition 3 ("bounded") does not stretch to that.

    Implementation-agnostic: the rows may be re-homed by an UPDATE on
    ``summary_versions`` or by loading and mutating them. Either way the moved
    week's versions must end on the target, and the re-home must not collide
    with the target's own versions (``uq_summary_versions_course_week_ver``).
    Week 3 (a ``keep_source`` conflict) is the collision probe: the target's
    snapshot of its own v1 and the source's v1 of week 3 cannot both be
    ``(target, 3, 1)``. Where the conflict week's source history goes is
    ADR 0004 #5's business (the source-side summary), not this pin's.

    RED until the merge re-homes the moved week's versions (M31-S2 follow-up).
    """
    from sqlalchemy.sql.dml import Update

    from app.core.storage import get_storage
    from app.models.summary import Summary
    from app.models.summary_version import SummaryVersion
    from app.services import course_service
    from tests.safety._predicate import Unreadable, admits, value
    from tests.safety._tenant import bind_values, tables_in

    source = SimpleNamespace(id="course-src", user_id=OWNER, code="SRC", archived_at=None)
    target = SimpleNamespace(id="course-tgt", user_id=OWNER, code="TGT", archived_at=None)

    def summary(sid, course, week, version, text):
        return Summary(
            id=sid,
            course_id=course.id,
            week=week,
            content_md=text,
            file_path=f"summaries/{course.id}/Week{week}.md",
            version=version,
            source_artifacts=[f"a-{sid}"],
        )

    def kept(vid, course, week, version):
        return SummaryVersion(
            id=vid,
            user_id=OWNER,
            course_id=course.id,
            week=week,
            version=version,
            content_md=f"# {course.code} week {week} v{version}",
            file_path=f"summaries/{course.id}/Week{week}.v{version}.md",
            source_artifacts=[],
        )

    target_w3 = summary("sum-t3", target, 3, 1, "# target w3 v1")
    source_w3 = summary("sum-s3", source, 3, 2, "# source w3 v2")
    source_w4 = summary("sum-s4", source, 4, 3, "# source w4 v3")
    moved = [kept("sv-s4-1", source, 4, 1), kept("sv-s4-2", source, 4, 2)]
    conflict_history = [kept("sv-s3-1", source, 3, 1)]
    versions = moved + conflict_history

    def execute(statement):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        tables = tables_in(statement)
        binds = set(bind_values(statement))
        if statement.is_select and tables == {"courses"} and OWNER in binds:
            course = source if "SRC" in binds else target if "TGT" in binds else None
            result.scalar_one_or_none.return_value = course
        elif statement.is_select and tables == {"summaries"}:
            if target.id in binds:
                result.scalars.return_value.all.return_value = [target_w3]
            elif source.id in binds:
                result.scalars.return_value.all.return_value = [source_w3, source_w4]
        elif statement.is_select and "summary_versions" in tables:
            hits = [sv for sv in versions if admits(statement, _version_row(sv))]
            result.scalars.return_value.all.return_value = hits
            result.all.return_value = [(sv,) for sv in hits]
        return result

    session, log, _probe = _recording_session(execute)
    session.delete = AsyncMock()

    with isolated_storage():
        storage = get_storage()
        for s in (target_w3, source_w3, source_w4):
            await storage.put(s.file_path, s.content_md.encode())
        await course_service.merge_courses(session, OWNER, "SRC", "TGT", "keep_source")

    assert source_w4.course_id == target.id, "control: the non-conflict week did not move"
    assert target_w3.version == 2, "control: keep_source did not run"

    # Final (course_id, week, version) of every version row, whichever way it moved.
    try:
        for kind, statement, _seen in log:
            if (
                kind == "execute"
                and isinstance(statement, Update)
                and statement.table.name == "summary_versions"
            ):
                sets = _set_values(statement)
                for sv in versions:
                    where = statement.whereclause
                    if where is None or value(where, _version_row(sv)) is True:
                        for column, new in sets.items():
                            setattr(sv, column, new)
    except Unreadable as exc:
        pytest.fail(f"The summary_versions re-home uses a construct _predicate cannot read: {exc}")

    stranded = sorted(sv.id for sv in moved if sv.course_id != target.id)
    assert not stranded, (
        "Floor 4 VIOLATION: merge moved week 4's summary to the target but left its "
        f"retained versions {stranded} on the archived source; deleting that emptied "
        "course (ADR 0004 #1) would destroy them."
    )

    snapshots = [
        obj for kind, obj, _seen in log if kind == "add" and isinstance(obj, SummaryVersion)
    ]
    keys = [(sv.course_id, sv.week, sv.version) for sv in versions + snapshots]
    clashes = sorted({k for k in keys if keys.count(k) > 1})
    assert not clashes, (
        f"The re-home collides with the target's own versions on {clashes} "
        "(uq_summary_versions_course_week_ver): the merge would fail on commit."
    )


# ── asset regeneration ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor4_asset_regeneration_keeps_study_history():
    """Regenerating assets never deletes a card or question a user has studied.

    Any DELETE on flashcards / quiz_questions must be conditioned on the
    absence of reviews / attempts; an unconditional one destroys history.
    Ruled "fix the code" (R-007, ADR 0004 §4). RED until M31-S2-BACKEND-019
    archives instead of deleting.
    """
    from sqlalchemy.sql.dml import Delete

    from app.agents.base import FlashcardData, QuizQuestionData
    from app.models.flashcard import Flashcard
    from app.models.quiz import QuizQuestion
    from app.services import asset_service
    from tests.safety._tenant import tables_in

    def answer(_statement):
        result = MagicMock()
        result.scalar.return_value = 0
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    session, log, _probe = _recording_session(answer)

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

    added = {type(obj) for kind, obj, _seen in log if kind == "add"}
    assert {Flashcard, QuizQuestion} <= added, "control: regeneration saved nothing"

    history_of = {"flashcards": "flashcard_reviews", "quiz_questions": "quiz_attempts"}
    unconditional = [
        str(s)
        for kind, s, _seen in log
        if kind == "execute"
        and isinstance(s, Delete)
        and s.table.name in history_of
        and history_of[s.table.name] not in tables_in(s)
    ]
    assert not unconditional, "Floor 4: regeneration deletes studied items:\n" + "\n".join(
        unconditional
    )
