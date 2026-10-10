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
    ("app/agents/claude_code.py", "ClaudeCodeAdapter._run_once", "shutil.rmtree"): (
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

#: Live breaches. Empty since M31-S2-BACKEND-019: asset regeneration archives
#: (``archived_at``) instead of deleting, unlisted by SAFETY-025.
#: test_floor4_asset_regeneration_keeps_study_history pins the behaviour.
DB_VIOLATIONS: dict[tuple[str, str], str] = {}


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

    Empty, and green, since M31-S2-BACKEND-019 removed the regeneration deletes
    (``asset_service.save_flashcards`` / ``save_quiz_questions``). A new entry
    is red until fixed; safety unlists it then. The inventory tests do not force that,
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


#: ADR 0004 #1 "What goes", as the models ``course_service.delete_course`` may
#: ``delete()``. The inventory above is keyed on the enclosing function, so once
#: ``delete_course`` is sanctioned it would wave through a delete of *any* model
#: added to it; this pins condition 3 ("bounded") model by model.
COURSE_DELETE_MODELS = {
    "Course": "the course itself",
    "LectureArtifact": "artifacts",
    "Extraction": "extractions",
    "Chunk": "chunks",
    "Summary": "summaries",
    "SummaryVersion": (
        "summaries: the retained prior versions of the course's own summaries "
        "(BACKEND-019). Inside 'the course and every DB child'; SAFETY-025 asks "
        "architect to name summary_versions in ADR 0004 #1 verbatim"
    ),
    "Flashcard": "flashcards",
    "FlashcardReview": "plus reviews",
    "QuizQuestion": "quiz questions",
    "QuizAttempt": "plus attempts",
    "Concept": "concepts",
    "ConceptRelation": "plus relations",
    "Exam": "exams",
    "StudySession": "study sessions",
    "ReviewItem": "review items",
    "PipelineRun": "pipeline runs",
    "CourseDocument": "course documents",
    "Assessment": "assessments",
    "Deadline": "deadlines",
}


def test_floor4_course_delete_is_bounded_to_adr_0004_item_1():
    """``delete_course`` deletes exactly the models ADR 0004 #1 lists, no blob, nothing wider."""
    module = "app/services/course_service.py"
    deleted: set[str] = set()
    session_deletes = []
    for path in app_modules():
        if rel(path) != module:
            continue
        for node, scope in walk_with_scope(parse(path)):
            if scope != "delete_course" or not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "delete" and node.args:
                deleted.add(dotted(node.args[0]))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "delete":
                session_deletes.append(f"{dotted(node.func)}:{node.lineno}")
    assert deleted, "detector found no delete() in course_service.delete_course; it has gone blind"
    assert not session_deletes, (
        f"delete_course gained a .delete() call {session_deletes}: ADR 0004 #1 deletes "
        "rows by model and no blob."
    )
    wider = sorted(deleted - set(COURSE_DELETE_MODELS))
    assert not wider, (
        f"Floor 4: delete_course now deletes {wider}, which ADR 0004 #1 does not list. "
        "Amend the ADR (with the user) before widening a sanctioned delete."
    )
    gone = sorted(set(COURSE_DELETE_MODELS) - deleted)
    assert not gone, f"COURSE_DELETE_MODELS lists models delete_course no longer deletes: {gone}"


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
# Green since M31-S2-BACKEND-019.

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

    Found in SAFETY-025; green since M31-S2-BACKEND-026.
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
    Ruled "fix the code" (R-007, ADR 0004 §4). Green since M31-S2-BACKEND-019
    archived instead of deleting.
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


# ── account deletion reaches every summary blob the user ever had (R-020) ─
#
# The other side of retention: floor 4 names explicit account deletion as the
# one path that may remove a user's generated content, and ADR 0004 #1 says
# course delete keeps the course's blobs because "the account purge sweeps the
# user's prefix later". Summary keys are per *course*, and the purge builds its
# summary prefixes from the courses still in the DB, so every summary blob of
# a course deleted earlier, all its retained ``Week<N>.v<k>.md`` versions
# included, outlives the account. So do the versions merge re-homes to the
# target, whose blobs stay under the archived source's prefix (M31 re-run
# F-3, M32 condition C5).
#
# The pin runs the real calls end to end over an in-memory table set that
# answers like a database (``_minidb``) and a real local storage root: the
# summarize stage's write (blob, then ``create_or_update_summary``), a
# re-summarize, ``merge_courses``, two ``delete_course`` calls, then
# ``delete_user_account``. It is agnostic about the fix: it looks for the
# bytes left anywhere under the storage root, by content, not by key.


@pytest.mark.asyncio
async def test_floor4_minidb_answers_like_a_database():
    """``_minidb`` gives the answers Postgres would, and refuses what it does not model.

    The R-020 pin is only as good as this fake: a WHERE it misread would
    delete or keep the wrong rows and the pin would judge a fiction.
    """
    import sqlalchemy as sa

    from app.models.course import Course
    from app.models.summary import Summary
    from tests.safety._minidb import MiniDB, MiniSession
    from tests.safety._predicate import Unreadable

    db = MiniDB()
    session = MiniSession(db)
    session.add_all(
        [
            Course(id="c1", user_id="u1", code="A"),
            Course(id="c2", user_id="u1", code="B"),
            Course(id="c3", user_id="u2", code="A"),
        ]
    )
    session.add(Summary(id="s1", course_id="c1", week=1, content_md="x", file_path="k1"))
    session.add(Summary(id="s2", course_id="c3", week=1, content_md="y", file_path="k2"))
    assert db.rows["summaries"][0].version == 1, "a scalar column default was not applied"

    mine = sa.select(Course.id).where(Course.user_id == "u1").order_by(Course.code.desc())
    assert (await session.execute(mine)).scalars().all() == ["c2", "c1"]
    assert await session.scalar(mine.limit(1)) == "c2"
    count = sa.select(sa.func.count()).select_from(Course).where(Course.code == "A")
    assert await session.scalar(count) == 2
    owned = sa.select(Course.id).where(Course.user_id == "u1")
    paths = sa.select(Summary.file_path).where(Summary.course_id.in_(owned))
    assert (await session.execute(paths)).scalars().all() == ["k1"], "IN (subquery) misread"
    joined = (
        sa.select(Summary.file_path)
        .join(Course, Course.id == Summary.course_id)
        .where(Course.user_id == "u2")
    )
    assert (await session.execute(joined)).all() == [("k2",)], "inner join misread"
    got = (await session.execute(sa.select(Course).where(Course.id == "c3"))).scalar_one()
    assert got is await session.get(Course, "c3")

    moved = await session.execute(sa.update(Summary).where(Summary.id == "s1").values(week=7))
    assert moved.rowcount == 1 and db.get(Summary, "s1").week == 7
    gone = await session.execute(sa.delete(Course).where(Course.user_id == "u2"))
    assert gone.rowcount == 1 and [c.id for c in db.rows["courses"]] == ["c1", "c2"]
    await session.execute(sa.insert(Course).values(id="c4", user_id="u3", code="Z"))
    await session.delete(db.get(Course, "c1"))
    await session.flush()
    assert sorted(c.id for c in db.rows["courses"]) == ["c2", "c4"]

    with pytest.raises(AssertionError):
        (await session.execute(sa.select(Course))).one_or_none()
    with pytest.raises(AssertionError):
        (await session.execute(sa.select(Course).where(Course.id == "none"))).scalar_one()

    unmodelled = {
        "outer join": sa.select(Summary).outerjoin(Course, Course.id == Summary.course_id),
        "FROM subquery": sa.select(sa.select(Course.id).subquery()),
        "count beside a column": sa.select(Course.user_id, sa.func.count()),
        "multi-row insert": sa.insert(Course).values([{"id": "c8"}, {"id": "c9"}]),
        "group by": sa.select(Course.user_id).group_by(Course.user_id),
        "text": sa.text("DELETE FROM courses"),
    }
    for label, statement in unmodelled.items():
        with pytest.raises(Unreadable):
            await session.execute(statement)
            pytest.fail(f"MiniDB answered a statement it does not model: {label}")


R020_USER = "00000000-0000-7000-8000-0000000000a1"
R020_OTHER = "00000000-0000-7000-8000-0000000000b2"


def _r020_marker(user: str, course: str, week: int, version: int) -> str:
    return f"r020-{user[-2:]}-{course}-week{week}-v{version}"


def _summary_key(course_id: str, week: int, version: int, user_id: str) -> str:
    """The summarize stage's key, passing the owner if the builder takes one."""
    import inspect

    from app.services import summary_service

    builder = summary_service.build_summary_storage_key
    kwargs: dict[str, object] = {"version": version}
    if "user_id" in inspect.signature(builder).parameters:
        kwargs["user_id"] = user_id
    return builder(course_id, week, **kwargs)


async def _r020_summarize(session, storage, course, week: int) -> str:
    """One summarize-stage write for ``course``/``week``, as ``pipeline/summarize.py`` does it."""
    from app.services import summary_service

    existing = await summary_service.get_existing_summary(session, course.id, week)
    version = existing.version + 1 if existing else 1
    text = _r020_marker(course.user_id, course.code, week, version)
    key = _summary_key(course.id, week, version, course.user_id)
    await storage.put(key, f"# {text}\n".encode())
    await summary_service.create_or_update_summary(
        session=session,
        course_id=course.id,
        week=week,
        content_md=f"# {text}\n",
        file_path=key,
        source_artifact_ids=[],
    )
    return text


def _markers_on_disk(root: str) -> set[str]:
    import pathlib
    import re

    pattern = re.compile(r"r020-[0-9a-z]{2}-[A-Z0-9]+-week\d+-v\d+")
    found: set[str] = set()
    for path in pathlib.Path(root).rglob("*"):
        if path.is_file():
            found |= set(pattern.findall(path.read_text(errors="replace")))
    return found


@pytest.mark.asyncio
async def test_floor4_account_deletion_purges_every_summary_blob_of_the_user():
    """After account deletion no summary or summary-version blob of the user remains.

    Covers a course still live at deletion, a course the user deleted earlier
    (ADR 0004 #1 keeps its blobs), and the versions ``merge_courses``
    re-homed to the target before the archived source was deleted. Another
    user's summaries must survive untouched: a purge that sweeps all of
    ``summaries/`` breaches floor 4 for that user, so it is not a fix.

    RED until M32-S1-BACKEND-005 (R-020).
    """
    from app.core.storage import get_storage
    from app.models.course import Course
    from app.models.user import User
    from app.services import account_service, course_service
    from tests.safety._minidb import MiniDB, MiniSession

    db = MiniDB()
    session = MiniSession(db)
    for uid in (R020_USER, R020_OTHER):
        db.add(User(id=uid, email=f"{uid}@example.test", username=f"user-{uid[-2:]}"))

    def course(code: str, owner: str) -> Course:
        row = Course(id=f"{owner[:-4]}c{len(db.rows['courses']):03d}", user_id=owner, code=code)
        db.add(row)
        return row

    with isolated_storage() as root:
        storage = get_storage()
        live = course("LIVE101", R020_USER)
        deleted = course("GONE201", R020_USER)
        source = course("SRC301", R020_USER)
        target = course("TGT401", R020_USER)
        other = course("LIVE101", R020_OTHER)

        mine: set[str] = set()
        theirs: set[str] = set()
        for c in (live, deleted, source):
            for _ in range(2):  # summarize, then re-summarize: v1 is retained
                mine.add(await _r020_summarize(session, storage, c, 2))
        mine.add(await _r020_summarize(session, storage, target, 1))
        for _ in range(2):
            theirs.add(await _r020_summarize(session, storage, other, 2))

        assert _markers_on_disk(root) == mine | theirs, "control: the summarize writes did not land"
        assert len(db.rows["summary_versions"]) == 4, "control: re-summarize retained no version"

        # Week 2 is summarized only in the source, so merge moves it and
        # re-homes its retained v1 to the target. Then the archived source and
        # an unrelated course are deleted the sanctioned way (ADR 0004 #1).
        merged = await course_service.merge_courses(session, R020_USER, "SRC301", "TGT401")
        assert merged["moved_summaries"] == 1, f"control: merge moved nothing: {merged}"
        await course_service.delete_course(session, R020_USER, "SRC301")
        await course_service.delete_course(session, R020_USER, "GONE201")
        assert not [c for c in db.rows["courses"] if c.id in (source.id, deleted.id)], (
            "control: the course deletes did not run"
        )
        # Everything merge carried to the target is still the user's live
        # data: deleting the emptied source must not take its bytes along.
        still_live = {m for m in mine if "-GONE201-" not in m}
        lost = sorted(still_live - _markers_on_disk(root))
        assert not lost, (
            "Floor 4: deleting a course destroyed summary blobs that still belong to a live "
            f"course (re-homed by merge, or another course's): {lost}"
        )

        await account_service.delete_user_account(session, R020_USER, storage)

        assert not [u for u in db.rows["users"] if u.id == R020_USER], (
            "control: the account was not deleted"
        )
        left = _markers_on_disk(root)
        assert theirs <= left, (
            "Floor 4: deleting one account destroyed another user's summaries: "
            f"{sorted(theirs - left)}"
        )
        survivors = sorted(left & mine)
        assert not survivors, (
            "Right to erasure (R-020): after account deletion these summary blobs of the "
            "deleted user remain:\n  "
            + "\n  ".join(survivors)
            + "\nThe purge builds summaries/<course_id> prefixes only from courses still in "
            "the DB, so a course deleted earlier (ADR 0004 #1 keeps its blobs) and the "
            "versions merge re-homed from it are never reached."
        )


# ── the deleted-course ledger is the purge's input: it must stay one user's ─
#
# BACKEND-005 closed R-020 with a ledger (decisions.md 2026-10-08 C5):
# ``delete_course`` writes a zero-byte ``ledger/deleted-courses/<user_id>/<course_id>``
# and the account purge turns every listed key's last segment into a
# ``summaries/<course_id>`` sweep. The pin above proves the deleted user's
# blobs go. These two prove nobody else's do: the ledger a purge reads is the
# purged user's alone, and a listing entry that names no course widens no sweep.


async def _ledger_scenario(storage, session, db):
    """Two users, each with a live and a deleted course carrying summaries."""
    from app.core.utils import generate_id
    from app.models.course import Course
    from app.models.user import User
    from app.services import course_service

    for uid in (R020_USER, R020_OTHER):
        db.add(User(id=uid, email=f"{uid}@example.test", username=f"user-{uid[-2:]}"))
    written: dict[str, set[str]] = {R020_USER: set(), R020_OTHER: set()}
    for owner in (R020_USER, R020_OTHER):
        for code in ("KEEP101", "GONE201"):
            # The real id generator: a deleted row's id is never handed out again.
            row = Course(id=generate_id(), user_id=owner, code=code)
            db.add(row)
            for _ in range(2):  # v1 retained as a version, v2 current
                written[owner].add(await _r020_summarize(session, storage, row, 3))
        await course_service.delete_course(session, owner, "GONE201")
    return written


@pytest.mark.asyncio
async def test_floor4_account_purge_spares_other_users_deleted_course_blobs():
    """Purging one account leaves another user's deleted-course summaries in place.

    Both users delete a course, so both have ledger markers. The other user's
    deleted-course blobs are retained by ADR 0004 #1 until *their* account is
    deleted; a ledger read across users (an unkeyed ``ledger/deleted-courses``
    prefix, or a listing that is not the purged user's own) sweeps them early.
    The R-020 pin cannot see this: its other user never deletes a course.
    """
    from app.core.storage import get_storage
    from app.services import account_service
    from tests.safety._minidb import MiniDB, MiniSession

    db = MiniDB()
    session = MiniSession(db)
    with isolated_storage() as root:
        storage = get_storage()
        written = await _ledger_scenario(storage, session, db)
        assert _markers_on_disk(root) == written[R020_USER] | written[R020_OTHER], (
            "control: the summarize writes did not land, or delete_course removed blobs"
        )

        await account_service.delete_user_account(session, R020_USER, storage)

        left = _markers_on_disk(root)
        assert not left & written[R020_USER], (
            f"control: the purge did not erase the deleted user's blobs: {sorted(left)}"
        )
        lost = sorted(written[R020_OTHER] - left)
        assert not lost, (
            "Floor 4: deleting one account destroyed another user's summaries, including "
            f"blobs of a course that user deleted (retained by ADR 0004 #1): {lost}. "
            "The purge must read only the purged user's deleted-course ledger."
        )


@pytest.mark.asyncio
async def test_floor4_account_purge_ignores_ledger_entries_that_name_no_course():
    """A ledger listing entry with no course id in it never widens the summary sweep.

    The purge takes the last ``/`` segment of every key ``list_keys`` returns
    under the user's ledger prefix and sweeps ``summaries/<segment>``. On S3,
    ``list_objects_v2`` also returns zero-byte "folder" objects whose key ends
    in ``/`` (the console's *Create folder*, s3fs, rclone and some sync tools
    write them). Such a key's last segment is empty, the sweep becomes
    ``summaries/`` and every user's summaries go. The storage listing is input
    the purge does not control, so the purge must refuse an entry that does not
    end in a course id, not trust it.

    Simulated over a local root by appending what S3 would list for such
    placeholders; the real markers are listed as before. Fixes that skip an
    empty segment, or accept only id-shaped segments, both go green.
    """
    from app.core.storage import LocalStorageBackend
    from app.services import account_service
    from tests.safety._minidb import MiniDB, MiniSession

    class S3ShapedListing(LocalStorageBackend):
        async def list_keys(self, prefix: str) -> list[str]:
            real = await super().list_keys(prefix)
            base = prefix.rstrip("/")
            return [*real, f"{base}/", f"{base}/imported/"]

    db = MiniDB()
    session = MiniSession(db)
    with isolated_storage() as root:
        storage = S3ShapedListing(base_dir=root)
        written = await _ledger_scenario(storage, session, db)
        assert _markers_on_disk(root) == written[R020_USER] | written[R020_OTHER], (
            "control: the summarize writes did not land"
        )

        await account_service.delete_user_account(session, R020_USER, storage)

        left = _markers_on_disk(root)
        assert not left & written[R020_USER], (
            f"control: the purge did not erase the deleted user's blobs: {sorted(left)}"
        )
        lost = sorted(written[R020_OTHER] - left)
        assert not lost, (
            "Floor 4: a ledger listing entry with an empty last segment (an S3 folder "
            "placeholder such as 'ledger/deleted-courses/<user_id>/') turned the purge's "
            "summaries/<course_id> sweep into summaries/ and destroyed another user's "
            f"summaries: {lost}. Skip any ledger key whose last segment is not a course id."
        )
