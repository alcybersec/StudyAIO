# ADR 0004 — Floor 4 admits explicit user-initiated deletes of the user's own items

**Status** Accepted (2026-10-04, by the user, with one amendment; see § Amendment 2026-10-04; clarified 2026-10-08, see § Clarification 2026-10-08) ·
**Date** 2026-10-04 · **Kit version** 1.10.3

**Ruling implemented:** `docs/decisions.md` § Rulings, 2026-10-04, "R-007 single-item deletes:
**amend floor 4**" (by: user). The ruling settles the substance. This ADR adds the exact wording
and the allowlist. The user accepted the text on 2026-10-04 with one amendment: merge
`on_conflict=keep_source` keeps the overwritten target summary as a version (Rulings,
2026-10-04, "Merge `keep_source`: **keep as a version**").

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
| 1 | Course | `DELETE /api/courses/{course_code}`, `app/api/courses.py:delete_course`. Requires `X-Confirm: <course_code>`, otherwise 428. | `app/services/course_service.py:delete_course` (DB) | The course and every DB child: artifacts, extractions, chunks, summaries, `summary_versions` (the retained prior versions of that course's own summaries; § Clarification 2026-10-08), flashcards plus reviews, quiz questions plus attempts, concepts plus relations, exams, study sessions, review items, pipeline runs, course documents, assessments, deadlines. **No blob is deleted.** The account purge sweeps the user's prefix later. |
| 2 | Course document or assessment attachment | `DELETE /api/courseops/documents/{document_id}`, `app/api/courseops.py:delete_document` | `app/services/courseops_service.py:delete_course_document` (DB), then `app/services/courseops_service.py:_delete_blob_if_unreferenced` (`store.delete`, blob) | The `course_documents` row. The blob goes only when no other row of the same user references the key, and only under that user's own `courseops/<user_id>/` prefix. |
| 3 | Deadline | `DELETE /api/courseops/deadlines/{deadline_id}`, `app/api/courseops.py:delete_deadline` | `app/services/courseops_service.py:delete_deadline` (DB) | One `deadlines` row, whether AI-extracted or manual. |
| 4 | Chat session | `DELETE /api/chat/sessions/{session_id}`, `app/api/chat.py:delete_session` | `app/services/chat_service.py:delete_session` (DB) | One `chat_sessions` row and its `chat_messages`, by ORM `delete-orphan` cascade and FK `ON DELETE CASCADE`. |
| 5 | Merge-discard | `POST /api/courses/{course_code}/merge`, `app/api/courses.py:merge_course` → `app/services/course_service.py:merge_courses` | `app/services/course_service.py:_discard_summary` (DB `session.delete` and blob `storage.delete`) | For each week summarized in both courses, the source course's summary row and its markdown blob. The call site is reached under every `on_conflict` policy (`keep_target`, `keep_source`, `regenerate`), because each one ends in `_discard_summary`. The exemption covers **only the source-side summary**. The target summary that `keep_source` overwrites is not merge-discard; it is under the version-retention rule (§ 4 and § Amendment 2026-10-04). |

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
- **Merge `keep_source` overwrite of the target.** `merge_courses` must snapshot the target
  summary into `summary_versions` before it overwrites `content_md` and bumps `version`. This is
  the same version-retention rule as re-summarize, not merge-discard (§ Amendment 2026-10-04).
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
  (`existing.content_md = summary.content_md; version + 1`). The proposed text treated the
  overwritten target as the discarded side of the merge, under item 5. The user rejected that on
  acceptance: the prior target version is retained (§ Amendment 2026-10-04).
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

## Amendment 2026-10-04 (on acceptance)

The user accepted this ADR on 2026-10-04 with one change, recorded here rather than in a new ADR
because it was part of the acceptance itself. Ruling: `docs/decisions.md` § Rulings, 2026-10-04,
"Merge `keep_source`: **keep as a version**" (by: user).

- **Merge `on_conflict=keep_source` is not merge-discard.** Before it overwrites the target
  summary's `content_md` and bumps `version`, `merge_courses` must snapshot the target's prior
  content into `summary_versions`, which is the same mechanism the re-summarize fix uses. The
  overwritten target content is covered by floor 4's "re-summarize never destroys prior
  versions" clause, not by the item-5 exemption. Until that snapshot lands
  (`M31-S2-BACKEND-019`), the in-place overwrite is a floor-4 violation, not a sanctioned site.
- **Item 5 is narrowed** to the source-side summary that `_discard_summary` removes. Under
  `keep_source` the source content survives as the target's new version, and under `keep_target`
  and `regenerate` the user chose to drop it. This is the only content the exemption covers.
- **The allowlist is unchanged.** `_discard_summary` still deletes exactly the source summary row
  and blob, and its only caller is still `merge_courses`. The snapshot adds a write, not a
  delete, so no `(module, function)` key moves. If the backend implementation routes the
  overwrite through a helper that deletes anything, or gives `_discard_summary` a second caller
  or a target-side use, this ADR must be amended before that lands.
- **What `safety` changes:** the floor-4 test should pin that the `keep_source` branch writes a
  `summary_versions` row before it overwrites the target. That is the same retention check as
  re-summarize, and it stays red until `M31-S2-BACKEND-019` lands.

## Clarification 2026-10-08 (`summary_versions` on course delete and merge)

This note clarifies the accepted decision. It does not change a rule, so it is a dated note
here, not a new ADR. Requested by `safety` in SAFETY-025.

- **Row #1 names `summary_versions`.** `M31-S2-BACKEND-019` added the `summary_versions` table
  for re-summarize retention, and `course_service.delete_course` now also runs
  `delete(SummaryVersion).where(SummaryVersion.course_id == course.id)`. These rows are the
  retained prior versions of *that course's own* summaries. They were already inside "the course
  and every DB child". Row #1 now names them verbatim so the list matches the code exactly.
  `safety` pins this in `COURSE_DELETE_MODELS` in
  `services/app/tests/safety/test_floor4_user_data_never_lost.py`. Floor 4's version-retention
  clause covers dedup, re-summarize and asset regeneration. It does not cover an explicit course
  delete, and the user asked for that delete.
- **`merge_courses` must re-home a moved summary's versions.** When a source summary moves to
  the target (`summary.course_id = target.id`), its `summary_versions` rows must move with it to
  `target.id` in the same transaction. Versions carry no summary FK. They are keyed on
  `(course_id, week, version)`, so "its versions" means the rows with `course_id == source.id` and
  the moved summary's `week`. If they stay keyed on the source course, a later
  `DELETE /api/courses/{source}` would delete the versions of a summary that now lives in the
  target course. That fails condition 3 (Bounded) for row #1, and it is the destruction of prior
  versions that floor 4 forbids. Owner: `M31-S2-BACKEND-026`. Until it lands, the moved
  summary's stranded versions are a floor-4 violation, not a sanctioned delete.
- **Unchanged.** The allowlist, `USER_ITEM_DELETE_CALLERS` and item 5 are unchanged. Re-homing
  is an update, not a delete, so no `(module, function)` key moves. `_discard_summary` removes
  only the source-side summary row and blob. The discarded source summary's own
  `summary_versions` rows stay on the source course, which `merge_courses` archives and does not
  delete. They go only through a later explicit delete of that course, under row #1. If
  `M31-S2-BACKEND-026` deletes them during the merge, or `_discard_summary` gains any further
  delete, this ADR must be amended with the user first.

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
