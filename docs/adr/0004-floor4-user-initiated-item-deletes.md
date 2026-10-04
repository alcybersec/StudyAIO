# ADR 0004 — Floor 4 admits explicit user-initiated deletes of the user's own items

**Status** Proposed · **Date** 2026-10-04 · **Kit version** 1.10.3

**Ruling implemented:** `docs/decisions.md` § Rulings, 2026-10-04, "R-007 single-item deletes:
**amend floor 4**" (by: user). The ruling settles the substance. This ADR adds the exact wording
and the allowlist, and stays Proposed until the user accepts that text. The status changes to
Accepted only on the user's word.

## Context

Floor 4 (`docs/strategy.md` §6) reads:

> user data is never lost: nothing deletes uploads or generated content under data/ except explicit
> account deletion, and dedup/re-summarize never destroys prior versions

The M31 floor tier (`services/app/tests/safety/test_floor4_user_data_never_lost.py`) inventories
every blob delete and every content-row delete under `services/app/app/`. Seven sites did not fit
the floor's only exception, account deletion. They sit in `BLOB_PENDING_RULING` and
`DB_PENDING_RULING` behind the strict xfail `test_floor4_no_delete_site_awaits_a_ruling`
(`docs/gates/M31/floors.md` § Floor 4, R-007). Those seven sites fall into three groups:

- **Single-item deletes the user asks for.** These are course, course document, deadline, chat
  session, and the losing side of a course merge. The PRD ships each one, and each sits behind its
  own route.
- **Re-summarize.** It overwrites `summaries.content_md` and the `Week<N>.md` blob in place.
- **Asset regeneration.** It deletes flashcards and quiz questions, and the deletes cascade through
  `flashcard_reviews` and `quiz_attempts`.

Read literally, the floor forbids a user from deleting their own chat session. That makes no sense
as a product rule, and it also does not protect anything: the floor exists so the *system* never
loses a user's data, not to stop the user from getting rid of it. The other two groups are
different. In those, the system destroys history the user never asked to lose. The user ruled
differently on each group:

| Group | Ruling | Effect on the floor |
|---|---|---|
| Single-item user deletes, merge-discard | amend floor 4 | this ADR |
| Re-summarize | fix the code | none; floor stands |
| Asset regeneration | fix the code | none; floor stands |

## Decision

**1. Floor 4 is reworded** to:

> user data is never lost: nothing deletes uploads or generated content under data/ except explicit
> account deletion and the explicit user-initiated deletes of the user's own items enumerated in
> ADR 0004, and dedup/re-summarize/asset regeneration never destroys prior versions or study history

Two clauses change. The exception now covers the enumerated item deletes. The trailing clause names
asset regeneration explicitly, because the user ruled that it must keep study history, and the old
text covered regeneration only by implication.

**2. What qualifies.** A delete counts as an "explicit user-initiated delete of the user's own item"
only when all four of the following hold:

1. **Explicit.** It is reached only from one named HTTP route that exists to delete that item, or to
   settle a merge conflict the user chose to resolve. No Celery task, beat schedule, startup hook,
   other service function or other route reaches it.
2. **Own item.** The lookup is owner-scoped on the caller's `user_id`. Floor 1 already requires
   this. Here it is also a precondition of the exemption: an unscoped delete is not exempt, even on
   a listed route.
3. **Bounded.** It removes the named item and the rows that depend on it, as listed below, and
   nothing wider.
4. **Listed.** Its `(module, function)` appears in the allowlist below. A new user-initiated delete
   needs this ADR amended first, with the user's agreement.

**3. The allowlist is exact.** It is keyed on the enclosing function, not the line number, using the
same keys as the floor-4 inventories. Every pair was re-derived on 2026-10-04 at `f1fc455` with
`grep -rn` over `services/app/app/`:

| # | Item | Route (handler, `services/app/`) | Delete site (`services/app/`) | What goes |
|---|---|---|---|---|
| 1 | Course | `DELETE /api/courses/{course_code}`, `app/api/courses.py:delete_course`. Requires `X-Confirm: <course_code>`, otherwise 428. | `app/services/course_service.py:delete_course` (DB) | The course and every DB child: artifacts, extractions, chunks, summaries, flashcards plus reviews, quiz questions plus attempts, concepts plus relations, exams, study sessions, review items, pipeline runs, course documents, assessments, deadlines. **No blob is deleted.** The account purge sweeps the user's prefix later. |
| 2 | Course document or assessment attachment | `DELETE /api/courseops/documents/{document_id}`, `app/api/courseops.py:delete_document` | `app/services/courseops_service.py:delete_course_document` (DB), then `app/services/courseops_service.py:_delete_blob_if_unreferenced` (`store.delete`, blob) | The `course_documents` row. The blob goes only when no other row of the same user references the key, and only under that user's own `courseops/<user_id>/` prefix. |
| 3 | Deadline | `DELETE /api/courseops/deadlines/{deadline_id}`, `app/api/courseops.py:delete_deadline` | `app/services/courseops_service.py:delete_deadline` (DB) | One `deadlines` row, whether AI-extracted or manual. |
| 4 | Chat session | `DELETE /api/chat/sessions/{session_id}`, `app/api/chat.py:delete_session` | `app/services/chat_service.py:delete_session` (DB) | One `chat_sessions` row and its `chat_messages`, by ORM `delete-orphan` cascade and FK `ON DELETE CASCADE`. |
| 5 | Merge-discard | `POST /api/courses/{course_code}/merge`, `app/api/courses.py:merge_course` → `app/services/course_service.py:merge_courses` | `app/services/course_service.py:_discard_summary` (DB `session.delete` and blob `storage.delete`) | For each week summarized in both courses, the source course's summary row and its markdown blob. This applies under every `on_conflict` policy (`keep_target`, `keep_source`, `regenerate`), because each one ends in `_discard_summary`. |

In the shape the floor-4 test uses:

```python
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
```

`_delete_blob_if_unreferenced` has a second caller, `discard_failed_upload_blob`. That caller is
sanctioned separately, as failed-upload cleanup, in the floor-4 test's
`REFERENCE_CHECKED_DELETE_CALLERS`. This ADR does not change that classification. The test keeps
pinning the helper's callers exactly. Only the `delete_course_document` edge moves from
pending-ruling to sanctioned under this ADR.

**4. What is not relaxed.** The following stay under the floor, which is unchanged for them:

- **Re-summarize.** `summary_service` must retain version N-1, both the row and the blob, when it
  writes version N. This includes the target-side re-summarize that a `regenerate` merge enqueues.
- **Asset regeneration.** `asset_service.save_flashcards` and `save_quiz_questions` must not delete
  a flashcard that has reviews or a quiz question that has attempts.
- **Dedup.** It still writes and deletes nothing.

These sites leave `*_PENDING_RULING` and become `*_VIOLATIONS`: live breaches that stay red until
the `data` and `ai` follow-up tasks land.

## Consequences

- **This weakens a floor.** It is recorded per `docs/strategy.md` §6, and it carries the user's
  ruling of 2026-10-04. Before this ADR, five shipped routes breached floor 4. After it, they are
  inside the floor, and the set can grow only by amending this ADR.
- **Merge `keep_source` also overwrites the target's summary in place**
  (`existing.content_md = summary.content_md; version + 1`). The user chose that side, so this ADR
  treats the overwritten target content as the discarded side of the merge, and it is covered by
  item 5. If the user would rather have the target's prior version retained, the re-summarize fix
  can cover this path too, since the version-retention mechanism will be the same. Raised here so
  nobody finds it later as a surprise.
- **Course delete keeps blobs, on purpose.** The route says "Uploaded files remain in storage". The
  orphaned blobs are not data loss, and they are swept by account deletion. This ADR sanctions the
  row deletes only. A future change that also deletes blobs on course delete needs this ADR amended.
- **What `safety` changes** in `services/app/tests/safety/test_floor4_user_data_never_lost.py`. This
  is `safety`'s territory, and the list is a request, not an edit:
  1. Move the five DB sites and two blob sites above into `DB_SANCTIONED`/`BLOB_SANCTIONED`, citing
     ADR 0004.
  2. Reclassify `REFERENCE_CHECKED_DELETE_CALLERS[delete_course_document]` as SANCTIONED.
  3. Move `asset_service.save_flashcards`/`save_quiz_questions` from `DB_PENDING_RULING` to
     `VIOLATIONS`. The re-summarize and regeneration xfails stay strict until the code is fixed.
  4. Pin `USER_ITEM_DELETE_CALLERS` exactly, in the same way as
     `test_floor4_account_purge_reachable_only_from_account_deletion`.
  5. Remove the `xfail` from `test_floor4_no_delete_site_awaits_a_ruling`. With both pending dicts
     empty, it passes.
  6. Update `FLOORS.md` §4.
- **Floor 1 is a precondition, not a side effect.** `delete_course_document` and `delete_deadline`
  take `user_id: str | None = None`, and only the route passes it. The floor-1 wiring tests already
  pin that the route passes it. If a future caller omits it, the delete is unscoped, and it fails
  condition 2 as well as floor 1.
- **Reversal** means restoring the old floor text and reclassifying the sites as violations. The
  routes would then need soft-delete or tombstones: a `deleted_at` column on each of the five
  tables, plus a filter on every read. That is the cost this ADR avoids.

## Alternatives considered

- **Soft-delete every user-deletable item, and keep floor 4 literal.** This lost because the user
  ruled to amend the floor, not to fix the code, for this group. It would also add a `deleted_at`
  column and a read-side filter to five tables, and every missed filter becomes a floor-1-shaped
  leak of "deleted" data. Data the user asked to delete and the system keeps anyway is also a
  privacy cost.
- **Admit "any user-initiated delete" as a category, with no list.** This lost because the floor
  test could not check it: "user-initiated" is not visible in the AST. Any delete reachable from
  any route would qualify, including regeneration, which is reachable from
  `POST /api/uploads/{id}/retry`. An exact allowlist plus pinned callers can be checked.
- **Fold re-summarize and regeneration into the same amendment.** This lost because the user ruled
  "fix the code" on both. They destroy history as a side effect of an action whose intent is to
  *add* content, which is the case floor 4 exists for.
