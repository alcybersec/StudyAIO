# M34: floor review of the S2/S3 contracts, before build

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Tree:** `kit/retrofit` @ `a2accb0`, which carries the architect's amendments. I first reviewed the entries at
`110f84b`, then re-checked them against the final text. The red contract tests were read at `3be437a`; they are now
on `hold/m34-contract-red` at `5d542b1` + `1437546`.
**Scope:** `models.secrets-at-rest v1` (M34-S2-SEC-005, first recorded as `models.third-party-tokens v1`), `models.stripe-webhook-events v1` (M34-S2-SEC-008), and,
for floors 1 and 2 only, `api.onboarding v1`, `api.ai_feedback v2`, `core.login-throttle-metrics v1` and
`api.study-items v2`.

Applied user rulings (2026-10-16), which replace the matching parts of the entries as written at `110f84b`:

1. `qa_answers` and the `qa_answer` feedback type are dropped from `api.ai_feedback v2`. Study cards are rated with
   the existing `flashcard` and `quiz_question` types.
2. `users.mfa_secret` (the TOTP seed) joins SEC-005. It uses the same `EncryptedText` type and the same migration.
3. `stripe_webhook_events` rows are kept indefinitely, with no pruning.

This review changes no `app/` code. It adds one floor-2 pin, `services/app/tests/safety/test_floor2_tokens_at_rest.py`.
The pin is red until SEC-005 lands, so it sits on its own commit and is held off trunk.

## Verdict: **APPROVE-WITH-CHANGES**

The designs hold all four floors once the changes in section 1 are made. None of them changes the shape of a
contract. Without C1 and C2, SEC-005 would be vetoed when it is built:

- **C1.** If rotation goes through the ORM attribute, it silently does nothing. Once the old key is dropped, every
  token and every TOTP seed then reads as `None`.
- **C2.** The entry does not yet say what an unreadable TOTP seed means at login.

### Status against the final entries (`a2accb0`)

| Change | Status | What is still needed |
|---|---|---|
| C1 raw-value rotation and migration | **Adopted.** The no-ORM-write-back rule, and "drop the old key only once `unreadable: 0`". | Nothing blocking. A non-zero exit code when the unreadable count is above 0 is recommended, so a script can gate on it. |
| C2 unreadable TOTP seed | **Adopted.** Rules 1-5 match or exceed this section: wrong-code `403` plus throttle, `mfa_secret_unavailable` with `user_id` only, backup codes unaffected, `disable_mfa` refuses and changes nothing, admin reset or restoring the old key. | Nothing. |
| C3 log names the column | **Partly adopted.** The event is now neutral (`secret_at_rest_undecryptable`), and the MFA case has its own route-level `mfa_secret_unavailable` with `user_id`. | Recommended, not blocking: a `column` field on the type-level event, so a broken calendar token can be told apart from a broken seed. |
| C4 upgrade on multi-user without a key aborts | **Open, required.** The entry still says only "Without a key (single-user) it leaves the values". | Add: on a multi-user instance with no key, `upgrade` aborts. |
| C5 downgrade conditions | **Open, required (wording).** The abort on an undecryptable value is in the entry. | Add: decrypt and narrow in one transaction; abort when no key is set or a decrypted value exceeds the narrowed width; the revision docstring and `docs/security/` state that the downgrade removes at-rest protection. |
| C6 `hide_parameters=True` | **Open, required.** Not in the entry. | Add it to SEC-005's provider list (`backend`, `app/core/database.py`). It is pinned red. |
| C7 "reconnect needed" path | **Open, required.** The entry still cites an "existing" path that does not exist. | Name the behaviour (refresh if possible, else `CalendarSyncError`), skip revoke on `None`, and send the token with `data=`. |

`models.stripe-webhook-events v1` at `a2accb0` (rows kept indefinitely, no `user_id`, listed as belonging to nobody)
and `api.ai_feedback` back at v1 (no `qa_answers`) are **accepted as written**. The verdict stays
**APPROVE-WITH-CHANGES**. SEC-005 may start once C4-C7 are recorded in the entry. It is gated, not vetoed: none of the
open items needs a redesign.

## 1. Required changes

### C1. Rotation and both migration directions work on stored strings, never through `EncryptedText` (floor 2, and account lockout)

`EncryptedText` decrypts on load. If rotation is written the obvious way (load the row, assign the value back, flush),
three things go wrong:

- **`needs_rotation` cannot be evaluated.** The ciphertext never reaches the code.
- **Re-assigning the same plaintext issues no `UPDATE`.** The flush compares old and new Python values and skips
  unchanged columns. The command reports success and re-keys nothing.
- **An unreadable value loads as `None`.** Writing it back destroys the token or seed. This contradicts the entry's
  promise that it is "counted and left as is".

The second failure is the dangerous one. The operator then drops the old key as the runbook says, and every OAuth
token, calendar token and TOTP seed reads as `None` at once. Calendars disconnect. Every MFA user can still sign in
only with a backup code, and otherwise needs an admin reset.

The entry must say:

- `encrypt-user-secrets` and the Alembic revision read and write the five columns as raw stored strings. That means a
  Core `select` over the table, or `sa.table(...)`/`type_coerce(col, Text)` in the revision. They never use the
  mapped attribute. The decision is made on the stored string (`is_encrypted`, `needs_rotation`), and an `UPDATE` by
  primary key is issued only for values that change.
- A value that cannot be decrypted under any configured key is counted, reported with its table, column and row id
  (no value), and left byte-for-byte as it is.
- The command exits non-zero when the unreadable count is above 0. The rotation runbook says not to drop the old key
  until a dry run reports `re-keyed: 0` and `unreadable: 0`.
- The `user_settings` path keeps its current behaviour. It already works on the raw JSON.

Test required (`backend` unit, `qa` integration on Postgres): one row each of plaintext, current-key, old-key and
undecryptable values. After `--apply`:

- the plaintext and old-key values are under the first key;
- the current-key value is unchanged;
- the undecryptable value is the identical stored string, not NULL;
- the exit code is non-zero.

### C2. `users.mfa_secret`: an unreadable seed never disables or bypasses MFA

Add the column to the entry's table: `users | mfa_secret | EncryptedText | yes | was String(64)`. Fernet output for a
32-character base32 seed is about 140 characters, so the column becomes `Text`, and downgrade narrows it back to
`String(64)`. The rotation command, the migration and the "never logged, never returned" clause all cover it.
`EXPORT_EXCLUDED_COLUMNS` already excludes it.

An unreadable seed reads as `None`, exactly like an absent one. The entry must require the following. Most of it
already holds in the code; the point is to write it down so no one "simplifies" it later.

1. **`mfa_enabled` is the only gate.** It alone decides whether a second factor is required, on the password path
   (`POST /auth/login`) and on the OAuth path (`POST /auth/oauth/mfa` and the callback's pending-MFA redirect). The
   presence of a seed never decides it. No code may read `mfa_secret is None` as "MFA is off".
2. **A `None` seed with `mfa_enabled` set fails closed.** A TOTP code is refused with the same `403 "Invalid MFA
   code"` as a wrong code (no oracle), and the failure is counted by the login throttle. `verify_totp` is never called
   with `None`. No cookies are set.
3. **Backup codes keep working.** They are stored as hashes, independently of the seed, so a user with an unreadable
   seed can still sign in with one.
4. **Nothing self-heals.** Reading an unreadable seed never clears `mfa_enabled` or `backup_codes`, and never stamps
   `tokens_valid_from`. `enable_mfa` keeps refusing while `mfa_enabled` is set, so no one can enrol over a broken
   seed. Recovery is the existing admin `clear_mfa`, which needs a human decision.
5. **`disable_mfa` with `mfa_enabled` set and a `None` seed fails closed.** It refuses, as today. It must not say "MFA
   is not enabled", which is false and would send the user and support the wrong way. It returns a distinct error
   that points to admin recovery, and logs `mfa_secret_unreadable` with `user_id` only.
6. **The setup flow is unchanged.** `POST /auth/mfa/setup` returns a new seed only to its own caller, before
   enrolment. That is not a "return" under floor 2.

The new pin covers point 2 on the password path. The OAuth-path equivalent belongs in `backend`'s unit tests for
SEC-005.

### C3. The undecryptable log line names the column

Once a TOTP seed is in scope, `third_party_token_undecryptable` with no context cannot tell an operator whether a
calendar is broken or a user is locked out of MFA. The type hook has no row, but it can know its column. Two
acceptable designs:

- `EncryptedText(column="users.mfa_secret")`, logged as `column=...`;
- a neutral event name `encrypted_column_undecryptable` with the same field.

The line still carries no value. The architect amends the entry and `test_tampered_ciphertext_reads_as_none_and_logs_no_value`
to match.

### C4. Upgrade without a key: abort on multi-user, leave values only on single-user

The entry only covers single-user ("Without a key (single-user) it leaves the values as they are"). On a multi-user
instance with no key, the upgrade must **abort**, matching `secret_box.check_startup` and `secret_box.encrypt`, which
both refuse in that case. Otherwise a migration that runs before the app container would report success and leave
every token in plaintext. On single-user with no key, it prints the number of plaintext values left and the
`encrypt-user-secrets --apply` instruction. It never prints a value.

### C5. Downgrade to plaintext: acceptable under floor 2, with these conditions

**Ruling: a decrypt-down downgrade is acceptable.** Floor 2 forbids credentials in the tree and AI credentials in logs
and API responses. Encrypting third-party tokens and the TOTP seed at rest is the protection SEC-005 adds. A downgrade
is a deliberate operator rollback to the schema that the previous code reads. The alternative is leaving ciphertext
under the old code. The old code would then send `enc:v1:...` to Google as a bearer token, break every calendar
silently, show the TOTP check an unreadable seed, and keep writing new plaintext anyway. Decrypting is the only
rollback that works and loses nothing. Conditions:

- Decrypting and narrowing happen in one transaction. Any abort leaves every value exactly as it was, still encrypted.
- The downgrade aborts, and narrows nothing, if:
  - no key is configured;
  - any `enc:v1:` value of the five columns cannot be decrypted;
  - any decrypted value is longer than the narrowed width (`String(1000)` for the OAuth columns, `String(64)` for
    `mfa_secret`).
- It prints counts only, never a value.
- The revision's docstring and `docs/security/` say the downgrade removes at-rest protection, and that it is an
  explicit operator act, not a step in a routine redeploy.

### C6. The engine hides bound parameters (`backend`, `app/core/database.py`, part of SEC-005)

`auth.oauth_callback` logs any failure with `logger.exception("oauth_callback_failed")`. A flush that fails inside
`create_or_link_oauth` (a duplicate link, a value longer than 1000 characters) raises a `DBAPIError`, and its text
renders every bound parameter as `[parameters: (...)]`. **Today that is the plaintext OAuth access and refresh token
in the log.** After `EncryptedText` it is ciphertext, but the same text still carries emails and every other bound
value, on every logged database error in the app. Add `hide_parameters=True` to `create_async_engine`.

Pinned: `test_floor2_engine_hides_bound_parameters_from_error_text`.

### C7. The "reconnect needed" path the entry cites does not exist

The entry says a `None` calendar access token "takes the existing 'reconnect needed' path in `gcal_service`". There
is no such path. `_build_gcal_service` builds `Credentials(token=None, ...)`, and google-auth then refreshes on the
first request, or raises a `RefreshError` that `sync_all_calendars` logs per sync. The entry must name the behaviour,
and `backend` must build it:

- With an access token of `None` and a readable refresh token, refresh and persist the new access token.
- With both `None`, raise `CalendarSyncError("reconnect required")`, logged with `sync_id` only. The other syncs keep
  running.
- `disconnect_calendar` skips the revoke call when the token is `None`.
- It sends the token in the form body (`data=`), not the query string (`params=`). A URL lands in httpx error text
  and in proxy logs.

## 2. Findings that need no contract change

### SEC-005: legacy plaintext read-back, and `None` on failure

- **Legacy read-back is accepted.** Once the upgrade has run, a plaintext value can only exist on a single-user
  instance with no key, which is the SEC-06 stance. Anyone who can plant a plaintext row already has write access to
  the database.
- **`None` on read failure, rather than raising, is accepted.** One bad value must not stop a user from loading,
  linking an account or deleting it. C2 makes the `mfa_secret` case fail closed. `calendar_syncs.access_token` is
  `NOT NULL`, so a `None` that was loaded and then assigned back would fail the flush rather than store NULL. With C1
  nothing assigns it back.

### SEC-005: is the column set complete?

I scanned every column in the metadata whose name ends in `token`, `secret`, `password` or `api_key`:

| Column | Decision |
|---|---|
| `oauth_accounts.access_token`, `.refresh_token` | In scope. Note: nothing in `app/` reads them after the login writes them (see R1). |
| `calendar_syncs.access_token`, `.refresh_token` | In scope. |
| `users.mfa_secret` | In scope (user ruling 2026-10-16; C2). |
| `calendar_syncs.sync_token` | Out. Google's sync cursor, which authorises nothing without the access token. |
| `telegram_links.link_token` | Out of SEC-005. It is our own one-time pairing code, stored in plaintext; see R3. |
| `magic_links.token_hash`, `invite_codes.token_hash`, `users.hashed_password`, `users.backup_codes` | Already hashes. |
| `push_subscriptions.p256dh`, `.auth` | Out. The push sender needs them in the clear. |
| `user_settings.settings_json` secrets | Already encrypted (SEC-06). |

The pin enforces this table. Any new credential-named column must either encrypt or be classified there with a
reason.

### SEC-008: Stripe webhook events (floors 1, 2 and 4)

- **No `user_id`, kept indefinitely: accepted** (user ruling 3).
  - Floor 1: no route reads the table. It holds only Stripe's ids and our decision, and the webhook already mutates
    only the named customer's row (`test_floor1_webhook_mutates_only_the_named_customers_row`).
  - Floor 2: no payload, email or user id is stored.
  - Floor 4: keeping the rows is the safe side.
- **One transaction for claim and apply: accepted.**
  - Dedupe that rolls back with a failed effect is strictly better than the Redis version. That version released the
    mark in an `except` that a crash skipped, and lost the mark on a Redis flush.
  - Moving the ordering watermark into Postgres closes the "flush Redis, replay an old `updated`, downgrade a paying
    user" path.
- **Account deletion:** listing the table among those that belong to nobody (`GLOBAL_TABLES`) is correct. `safety`
  must add `stripe_webhook_events` to `tests/safety/_tenant.py::UNOWNED_TABLES` in the same change, or
  `test_floor1_every_table_is_classified` goes red. That is a `safety` task tied to SEC-008 (section 4).

### Onboarding, AI feedback v2, throttle metrics, study-items v2 (floors 1 and 2)

- **`api.onboarding v1`** holds floor 1 as designed. `quiz_attempts` has no `user_id` column, so the `check_in_done`
  quiz branch must join `quiz_questions` to `courses` and filter on `courses.user_id == caller`. An unscoped `EXISTS`
  on `quiz_attempts` would light one user's checklist from another user's activity. `PATCH` writes the caller's
  `users` row. `users` is unowned to the route sweep, so the update must be keyed on `users.id == caller`, and
  `backend`'s unit test must assert that key, not just the status code. `safety` adds the floor pin when it lands
  (section 4).
- **`api.ai_feedback v2`**, after ruling 1, adds no new target type and no table, so it adds no floor surface. The
  amended entry must remove `qa_answer` from `AI_FEEDBACK_TARGET_TYPES` and `answer_id` from `QAResponse`. The v1
  owner-scoped getters and `test_floor1_ai_feedback_usage.py` still cover the two study types.
- **`core.login-throttle-metrics v1`** holds floor 2. The `action` label is a closed set of four constants, with no
  email, key or path. `test_floor2_metrics_labels.py` already rejects identity-bearing labels.
- **`api.study-items v2`** holds floor 1. `get_course_by_code_ci` takes `user_id` as a required keyword, filters on
  it, never creates a course, and the tie-break is deterministic. `test_floor1_study_item_crud.py` covers the routes.

## 3. Recommended, not blocking

- **R1. Stop storing OAuth login tokens.** `oauth_accounts.access_token` and `.refresh_token` are written by
  `create_or_link_oauth` and read nowhere in `app/`. Not storing them is stronger than encrypting them. Floor 4
  covers uploads and generated content, not provider tokens, so nulling them is not data loss. This is a follow-up
  for `backend`, not part of SEC-005.
- **R2. Stripe ordering under concurrency.** Two *different* events for one customer, delivered at once, can both
  read the watermark before either commits, and the older one can commit last. The Redis version had the same race.
  Two fixes:
  - take `SELECT ... FOR UPDATE` on the customer's `subscriptions` row, or `pg_advisory_xact_lock` on the customer
    id, before reading the watermark;
  - skip the ordering step when the event has no customer. The ORM renders `== None` as `IS NULL`, which would
    compare the event with every other customer-less row.
- **R3. Hash `telegram_links.link_token`**, as magic-link and invite tokens already are.
- **R4. On account deletion, null `stripe_customer_id`** on that customer's `stripe_webhook_events` rows. The rows,
  the dedupe and ruling 3 all stay intact. Only the pseudonymous link to the deleted person is removed.

## 4. `safety` follow-ups this creates

- When SEC-005 lands, move `test_floor2_tokens_at_rest.py` to trunk and add it to `FLOORS.md` §2.
- When SEC-008 lands, in the same window:
  - rewrite the three Stripe pins in `test_floor1_worker_jobs.py`, which patch `app.core.redis.redis_client` and go
    red once `billing_service` stops using Redis, against the Postgres claim;
  - add `stripe_webhook_events` to `UNOWNED_TABLES`.
- When onboarding lands, add a floor-1 pin: `GET` and `PATCH /api/onboarding` read and write only the caller's rows,
  and the quiz branch is scoped through `courses.user_id`.

## 5. The floor-2 pin

`services/app/tests/safety/test_floor2_tokens_at_rest.py`. On `a2accb0`: 11 failed, 4 passed.

| Test | Fails when |
|---|---|
| `test_floor2_credential_column_scan_is_not_vacuous` | The name scan stops finding the five columns, or a reviewed exclusion has gone stale. |
| `test_floor2_every_credential_column_is_encrypted_or_reviewed` | A column named `*token`/`*secret`/`*password`/`*api_key` is neither encrypted nor classified with a reason. |
| `test_floor2_credential_reaches_the_driver_as_ciphertext[5]` | Binding a sentinel through the column type for Postgres yields anything but `enc:v1:` ciphertext without the sentinel, or the value does not read back. **RED until SEC-005.** |
| `test_floor2_failed_insert_error_text_carries_no_plaintext[5]` | The text of a failed INSERT's `DBAPIError`, as `logger.exception` would render it, contains the sentinel. **RED until SEC-005.** |
| `test_floor2_engine_hides_bound_parameters_from_error_text` | `hide_parameters` is off (C6). **RED until SEC-005.** |
| `test_floor2_unreadable_totp_seed_never_bypasses_mfa[2]` | With `mfa_enabled` and a `None` seed, a password login with or without a TOTP code gets anything but `403` and no session cookies, or `verify_totp` is handed `None` (C2). Green today. |

**Green-path check:** I replaced the five column types with a minimal `EncryptedText` over `secret_box` and set
`hide_parameters`, in a throwaway test file that I then deleted. All 15 tests passed, so the pin goes green on a
correct implementation.

**Mutation check not done:** I did not run a mutation check of the MFA pin (switching `auth.py`'s gate from
`mfa_enabled` to the seed). The environment refused a temporary edit to `app/api/auth.py`, which belongs to
`backend`. Until someone runs it in a scratch copy, that pin has not been seen to fail.
