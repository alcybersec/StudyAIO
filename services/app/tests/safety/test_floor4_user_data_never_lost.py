"""Floor 4 — user data is never lost.

    nothing deletes uploads or generated content under data/ except explicit
    account deletion, and dedup/re-summarize never destroys prior versions

Static inventories (exact in both directions, so a new delete site fails until
someone classifies it, and a removed one fails until it is unlisted):

* every blob/file delete in ``app/**`` (``StorageBackend.delete`` /
  ``delete_prefix``, ``Path.unlink``, ``os.remove``, ``shutil.rmtree``);
* every DB delete of an uploaded or generated-content model.

Each site is one of:

* ``SANCTIONED`` — account deletion (the floor's one exception), or a
  temp file outside ``data/``, or a *move* (write the new key, then drop the
  old one) where the content survives;
* ``PENDING_RULING`` — the floor's text and a shipped, documented behaviour
  disagree; the user must rule (``test_floor4_no_delete_site_awaits_a_ruling``
  is ``xfail(strict=True)`` until they do);
* ``VIOLATIONS`` — a live breach, each with a behavioural test below that is
  red until fixed.

Plus behaviour: account purge is reachable only from account deletion; lecture
dedup writes and deletes nothing; re-summarize increments the version.
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

#: (module, function, callee) -> reason.
BLOB_SANCTIONED = {
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

#: User-initiated deletion of a single item (not of the account). The floor
#: allows only account deletion; the product lets a user delete one document or
#: discard one side of a merge. Needs the user's ruling.
BLOB_PENDING_RULING = {
    ("app/services/courseops_service.py", "_delete_blob_if_unreferenced", "store.delete"): (
        "DELETE /api/courseops/documents/{id}: user deletes one course document; "
        "blob dropped when no other row of theirs references it"
    ),
    ("app/services/course_service.py", "_discard_summary", "storage.delete"): (
        "POST /api/courses/{code}/merge with keep_target/keep_source: the losing "
        "week's summary row and blob are deleted"
    ),
}

BLOB_VIOLATIONS = {
    ("app/api/courseops.py", "upload_course_document", "storage.delete"): (
        "on CourseOpsError (incl. 'already uploaded') deletes storage_key — which, "
        "for a re-upload of the same file, is the key the EXISTING document's row "
        "points at (courseops_key is user+sha256+name). Dedup destroys the original. "
        "Behaviour: test_floor4_duplicate_course_document_upload_keeps_original_blob"
    ),
    ("app/api/courseops.py", "upload_assessment_document", "storage.delete"): (
        "on a 404 assessment deletes storage_key, the same key an existing course "
        "document of the same file already uses. "
        "Behaviour: test_floor4_failed_assessment_attach_keeps_existing_blob"
    ),
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

DB_PENDING_RULING = {
    ("app/services/course_service.py", "delete_course"): (
        "DELETE /api/courses/{code}: user deletes a course; every artifact, "
        "extraction, summary, flashcard (+reviews), quiz (+attempts), concept, "
        "exam and document row of that course is deleted (blobs are kept)"
    ),
    ("app/services/course_service.py", "_discard_summary"): (
        "merge keep_target/keep_source deletes the losing summary row"
    ),
    ("app/services/courseops_service.py", "delete_course_document"): (
        "user deletes one course document row"
    ),
    ("app/services/courseops_service.py", "delete_deadline"): (
        "user deletes one (AI-extracted or manual) deadline row"
    ),
    ("app/services/chat_service.py", "delete_session"): (
        "user deletes one chat session and its messages"
    ),
    ("app/services/asset_service.py", "save_flashcards"): (
        "regeneration deletes the artifact's flashcards; flashcard_reviews "
        "cascade, so SRS history is lost (PRD.md §'Regeneration' says replace). "
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


def _assert_exact(found: dict, *classified: dict, what: str) -> None:
    known = set().union(*classified)
    new = {k: v for k, v in found.items() if k not in known}
    stale = sorted(known - set(found))
    assert not new, (
        f"Floor 4: unclassified {what}:\n"
        + "\n".join(f"  {loc}  {key}" for key, loc in sorted(new.items()))
        + "\nA delete of user data is allowed only on account deletion. Classify it "
        "in tests/safety/test_floor4_user_data_never_lost.py with a reason, or remove it."
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
        BLOB_VIOLATIONS,
        what="blob/file delete site(s)",
    )


def test_floor4_every_content_row_delete_is_classified():
    """No DB delete of uploaded/generated content exists outside the inventory."""
    _assert_exact(
        db_content_delete_sites(), DB_SANCTIONED, DB_PENDING_RULING, what="content row delete(s)"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VETO-relevant, awaiting user ruling: floor 4 allows deletion only on "
    "account deletion; single-item user deletes, merge discards and asset "
    "regeneration delete user data (BLOB_/DB_PENDING_RULING)",
)
def test_floor4_no_delete_site_awaits_a_ruling():
    """Every delete of user data is either account deletion or ruled acceptable.

    Strict: when the user rules (behaviour changed, or floor 4 amended by ADR
    to admit user-initiated item deletion) and the dicts empty, this XPASSes
    and fails, forcing the marker off.
    """
    pending = {**BLOB_PENDING_RULING, **DB_PENDING_RULING}
    assert not pending, "\n".join(f"  {k}: {v}" for k, v in pending.items())


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


@pytest.mark.asyncio
async def test_floor4_duplicate_course_document_upload_keeps_original_blob(
    async_client, default_test_user, simple_pdf
):
    """Re-uploading a course document that already exists must not delete its file."""
    from app.core.storage import get_storage
    from app.services.courseops_service import CourseOpsError

    content = simple_pdf.read_bytes()
    key = await _seed_existing_courseops_blob(default_test_user.id, content, "outline.pdf")

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
    async_client, default_test_user, simple_pdf
):
    """A failed attach must not delete a blob another document of the user's uses."""
    from app.core.storage import get_storage

    content = simple_pdf.read_bytes()
    key = await _seed_existing_courseops_blob(default_test_user.id, content, "rubric.pdf")

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
    from tests.safety._tenant import tables_in

    from app.agents.base import FlashcardData, QuizQuestionData
    from app.services import asset_service

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
