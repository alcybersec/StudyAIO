# M34-S2-SEC-008 and M34-S3-BACKEND-012: safety review of the held build

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** `hold/m34-sec008-backend` at `9487c9a`, cherry-picked onto `kit/retrofit` @ `1766c17` (SEC-006 option F
already in the base). The eight commits applied cleanly, with no conflicts:

| Held | On this branch | Commit |
|---|---|---|
| `2eec528` | `b5a422c` | test(red): contract tests for SEC-005, SEC-008, BACKEND-012 |
| `3d03893` | `e222661` | test(red): secrets-at-rest MFA seed rules; ai_feedback back to v1 |
| `645b3e2` | `f2053cc` | test(red): M34 safety changes in the secrets, stripe and onboarding contracts |
| `41e2d1f` | `3315e7d` | `stripe_webhook_events`, `users.onboarding_checklist`, migration `a1c2d3e4f5a6` |
| `14de472` | `ec6e026` | Stripe webhook dedupe and ordering in Postgres |
| `5803460` | `aa2eac5` | `LOGIN_THROTTLE_UNAVAILABLE{action}` |
| `0aa6ac5` | `52a59e3` | case-insensitive course lookup on card and quiz add |
| `9487c9a` | `475243b` | `GET`/`PATCH /api/onboarding` |

Reviewed against floors 1, 2 and 4, `docs/gates/M34/contracts-safety.md` R2 and R4, and the contract entries
`models.stripe-webhook-events v1`, `api.onboarding v1`, `core.login-throttle-metrics v1`, `api.study-items v2`.

## Verdict: **APPROVE**

All four floors hold on the code as written, R2 and R4 are implemented as recommended, and the floor tier is
green with the pins below. No finding blocks. Section 4 lists residuals for `backend`.

## 1. Floor tier on the build before this change

`tests/safety` on the cherry-picked tree: **6 failed, 684 passed, 1 skipped**. Exactly the six expected:

| Red | Cause | Fix in this change |
|---|---|---|
| `test_floor1_tenant_isolation.py::test_floor1_every_table_is_classified` | New table with no `user_id` and no FK to an owned table. | `stripe_webhook_events` added to `_tenant.UNOWNED_TABLES`, with the reason (no `user_id` by contract, no route reads it, deletion unlinks). |
| `test_floor1_worker_jobs.py::test_floor1_webhook_mutates_only_the_named_customers_row` ×2, `…::test_floor1_webhook_replayed_or_stale_event_mutates_nothing` | The pins patched `app.core.redis.redis_client`; the service no longer uses Redis, and the old fake session answered the claim `INSERT … RETURNING` with `None`, which the service reads as a replay. | Rewritten against the Postgres claim (section 2). |
| `test_floor2_metrics_labels.py::test_floor2_metric_label_names_are_the_allowed_enums`, `…::test_floor2_metric_label_values_are_never_identifiers_or_messages` | New label `action`. | `ENUM_LABELS = {"action": {read, record, clear, limit}}`: the name is allowed, and every value must be a literal from that set. |

## 2. Pins added or rewritten

All in `services/app/tests/safety/`, mapped in `FLOORS.md`, commit `2d9c426`.

**Stripe webhook** (`test_floor1_worker_jobs.py`). `_WebhookDb` now models the contract: the
`stripe_webhook_events` rows live in a `MiniDB`, so the watermark read is answered by evaluating its real WHERE
clause; the claim honours the unique index (`ON CONFLICT (stripe_event_id) DO NOTHING` is asserted); `rollback`
restores the rows as of the last `commit`.

- `…_mutates_only_the_named_customers_row[updated|deleted]`: as before (only the named customer's row and that
  row's own user), plus the claim records that customer and claim and effect commit exactly once.
- `…_replayed_or_stale_event_mutates_nothing`: a replay and a stale event never touch `subscriptions` or `users`;
  the replay adds no row; the stale event is committed as `stale`, and its own replay is a no-op.
- `…_ordering_is_per_customer` (new, R2): another customer's newer event does not suppress this one; the advisory
  lock is the named customer's and is taken before the watermark read.
- `test_floor4_webhook_failed_effect_releases_the_claim` (new): a failing effect leaves no claim, and the retry
  applies.
- `test_floor1_floor4_account_deletion_nulls_stripe_customer_with_update_never_delete` (new, R4): over MiniDB with
  two users, `_unlink_stripe_events` nulls only the deleted user's customer, every row survives, and every
  statement on the table is an `UPDATE`, never a `DELETE`.
- `test_floor4_account_deletion_unlinks_stripe_events_before_deleting_subscriptions` (new): the unlink runs before
  the per-table delete loop (it reads customer ids from `subscriptions`), and the table stays in `GLOBAL_TABLES`.

**Onboarding** (`test_floor1_onboarding.py`, new). The real routes over MiniDB, the caller beside a user who has
done every step:

- a caller with no rows is `new` and reads their own checklist preference;
- each of the five facts (artifact, summary, `summary_viewed`, flashcard review, quiz attempt) from the other user
  leaves the caller's status alone, and the same fact for the caller moves it (positive control);
- every statement `GET` runs binds the caller's id and never the other's; the `quiz_attempts` statement is scoped
  by `courses.user_id`;
- `PATCH` is one `UPDATE users … WHERE users.id = <caller>`, changes no other row, and a body naming a user
  (`user_id`, `id`) is a 422 that runs no statement.

**Metrics** (`test_floor2_metrics_labels.py`): `ENUM_LABELS`, five detector cases (`action='read'` accepted;
an unknown literal, a local, `email` and an f-string refused), and
`test_floor2_enum_label_values_are_all_in_use` (the set equals the values used under `app/**`).

### Mutation check

24 mutations, applied one at a time to a scratch copy of `services/app/` outside the worktree, each running only
the pins above: **24/24 killed**, baseline 60 passed.

- Onboarding: the quiz branch without `courses.user_id`; the quiz branch without its joins and filter; the
  artifact, summary-target, `summary_viewed`, flashcard-review and checklist reads unscoped; `PATCH` unkeyed;
  `PATCH` keyed on `users.id != caller`.
- Stripe: the watermark read without the customer filter; the advisory lock removed (two variants); replay not
  detected; the stale decision not committed; a stale event applied; `commit` in place of `rollback` on failure.
- R4: unlink by `DELETE`; unlink without the customer filter; customer ids read from every user's
  subscriptions; unlink moved after the delete loop; `stripe_webhook_events` removed from `GLOBAL_TABLES`.
- Metrics: `action=email`; `action="login"`; a second label name `email`.

## 3. Review of the implementation

### SEC-008 (`ec6e026`, `3315e7d`)

- **Floor 1.** The mutation is still keyed on the customer id from the signed event, and the user lookup on that
  row's own `user_id`. The new table has no route; nothing request-side reads it.
- **Floor 2.** The table stores Stripe's event id, type, customer id, `created` and `applied`/`stale`. No payload,
  email or user id. The new log lines (`webhook_replay_ignored`, `webhook_stale_ignored`) carry the event id, type
  and `created` only. The advisory-lock key carries the customer id as a bound parameter, kept out of error text by
  the request engine's `hide_parameters=True` (`app/core/database.py`).
- **Floor 4.** Rows are kept indefinitely (ruling 3); no code path deletes them. Moving the state out of Redis
  removes the old way to lose the dedupe mark (a Redis flush).
- **R2: adopted.** `pg_advisory_xact_lock(hashtextextended('stripe:customer:<id>', 0))` before the watermark read.
  Under READ COMMITTED the read after the lock sees the other transaction's committed row, so the older of two
  concurrent events is recorded `stale`. An event with no customer skips ordering, so `IS NULL` never compares
  unrelated events.
- **Transaction shape.** The service now owns `commit`/`rollback` for the delivery. The two `_handle_*` helpers
  lost their own `commit`, so the effect and the claim are atomic. The webhook route does no other write on the
  session.

### R4, account deletion (`ec6e026`)

`_unlink_stripe_events` reads the user's customer ids from `subscriptions`, then
`UPDATE stripe_webhook_events SET stripe_customer_id = NULL WHERE stripe_customer_id IN (…)`, before the delete
loop, which skips the table through `GLOBAL_TABLES`. Adopted as recommended.

### BACKEND-012

- **Onboarding (`475243b`).** Floor 1 holds as the contract review required: each of the six reads filters on the
  caller, the quiz branch through `courses.user_id`; `PATCH` is keyed on `users.id`; `OnboardingPatch` has
  `extra="forbid"` and a `Literal` state; `set_checklist` re-validates. The status carries course ids and codes
  that are the caller's own. Migration `a1c2d3e4f5a6` adds the column with `server_default='auto'`, so existing
  users are backfilled and nothing is rewritten.
- **Course lookup (`52a59e3`).** `get_course_by_code_ci` takes `user_id` as a required keyword, filters on it,
  never creates a course, and breaks ties deterministically (exact case, then oldest). The existing
  `test_floor1_study_item_crud.py` pins stay green.
- **Throttle counter (`aa2eac5`).** One label, four literals, incremented beside the existing log lines. The
  counter is declared in `core/login_throttle.py` and imported by `core/rate_limit.py`; no identity reaches it.

### Floor 3

Not touched: no `get_agent` call site and no AI call is added. The floor-3 pins are green.

## 4. Residuals, not blocking

1. **Customer ids in existing log lines** (`billing_service`: `subscription_created`, `checkout_completed`,
   `webhook_subscription_not_found`). These predate this change. A Stripe customer id is a pseudonymous identifier,
   not a credential, so floor 2 is not engaged. Recommended for `backend`: drop it, or log a hash.
2. **An event with no `id`** is applied with no claim row, so it is neither deduped nor counted as a watermark.
   Stripe always sends an id; the route passes `event["id"]`. Noted in the threat model, B7.
3. **`subscriptions.stripe_customer_id` is not unique.** If two users ever shared a customer id (a data error), deleting
   one would unlink the other's event rows too. That weakens ordering for the other customer; it exposes and
   deletes nothing. The webhook already treats such a customer as not found (`scalar_one_or_none`).
4. **Downgrade of `a1c2d3e4f5a6`** drops `stripe_webhook_events`. That loses dedupe history, not user data under
   `data/`. It is an operator rollback, and the old code would use Redis again.

## 5. Evidence

```
$ .venv/bin/python -m pytest tests/safety -q --cov=tests/safety --cov-fail-under=95
TOTAL                                                    7720    175    98%
Required test coverage of 95% reached. Total coverage: 97.73%
713 passed, 1 skipped, 34 warnings in 485.74s (0:08:05)

$ .venv/bin/python -m pytest tests/unit tests/contracts -q --no-cov
10 failed, 3841 passed, 273 warnings, 13 errors in 447.79s (0:07:27)
```

All 23 reds are in `tests/contracts/test_secrets_at_rest_contract.py` (SEC-005, not built yet, expected). Nothing
else is red.
