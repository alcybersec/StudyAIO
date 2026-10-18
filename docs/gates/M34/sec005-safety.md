# M34-S2-SEC-005: safety review of the held build (secrets at rest)

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** `hold/m34-sec005`, cherry-picked onto `kit/retrofit` @ `26f9ab5`. The three commits applied cleanly:

| Held | On the review branch | Commit |
|---|---|---|
| `3614d72` | `ee0873e` | test(red): secrets-at-rest contract and the floor-2 pin `test_floor2_tokens_at_rest.py` |
| `4daef70` | `1ec9703` | backend: `EncryptedText` in `app/core/secret_box.py`, rotation on raw columns in `cli.py`, MFA unreadable-seed rules in `api/auth.py` and `user_service`, gcal C7 |
| `9ecd47a` | `29c3c72` | data: five columns on `EncryptedText`, `alembic/env.py` `hide_parameters`, revision `b2d4f6a8c0e1` |

Reviewed against floors 2 and 4, the contract entry `models.secrets-at-rest v1` (`docs/CONTRACTS.md`) and my
conditions C1-C7 in `docs/gates/M34/contracts-safety.md`.

## Verdict: **APPROVE**

Floors 2 and 4 hold on the code as written, and C1-C7 are all met. I exercised every migration abort path on a
live Postgres, and every key pin was red under mutation. The one contract test that was red,
`test_downgrade_is_documented_as_removing_protection`, is green with the `docs/security/` text in this change.
No finding blocks. Section 5 lists the residuals.

## 1. Conditions C1-C7

| | Condition | Status | Evidence |
|---|---|---|---|
| C1 | Rotation and both migration directions work on stored strings. An unreadable value is left as stored and counted, and the exit code is non-zero while any are | **Met** | `cli._rekey_raw_columns` and the revision both use `sa.table(...)` over plain `Text` columns, never the mapped attribute. The `UPDATE` is by primary key and is issued only for values that change. On live Postgres: plaintext and old-key values were re-keyed under the first key, a value under a foreign key stayed byte-identical, and the command exited `2`. Pinned on real SQL (SQLite) |
| C2 | An unreadable seed never disables or bypasses MFA | **Met** | `_totp_matches` refuses a `None` seed with the wrong-code `403`, and the throttle counts it, on the password and the OAuth path. `mfa_enabled` remains the only gate. Backup codes are unaffected. `disable_mfa` refuses with a distinct message pointing to admin recovery, and changes nothing. `mfa_secret_unavailable` carries `user_id` only |
| C3 | The undecryptable log names the column | **Met** (the recommended form) | `EncryptedText(column="users.mfa_secret")` and the others. `secret_at_rest_undecryptable` carries `column=` and no value. Checked through the real logging chain |
| C4 | Upgrade without a key aborts on multi-user | **Met** | `secret_box.check_startup()` is the first statement of `upgrade()`. Live: `RuntimeError`, exit 1, `alembic_version` still `a1c2d3e4f5a6`, columns still `varchar(1000)`/`varchar(64)`, values unchanged |
| C5 | Downgrade decrypts and narrows in one transaction, and aborts on no key, undecryptable or too long. The docstring and `docs/security/` say it removes protection | **Met** | Live: each of the three aborts left every value byte-identical and every column `text`. The clean downgrade restored plaintext and narrowed the columns. The docstring states it. `docs/security/threat-model.md` §5 SEC-005 item 6 (this change) says when an operator would ever run it |
| C6 | `hide_parameters=True` | **Met** | `app/core/database.py` (already on trunk) and `alembic/env.py` (this build) |
| C7 | Unreadable calendar tokens: refresh if possible, else `CalendarSyncError("reconnect required")`; skip revoke on `None`; revoke via `data=` | **Met** | `_build_gcal_service` raises before any Google call when both are `None`. `_refresh_if_needed` refreshes a `None` access token from a readable refresh token. `disconnect_calendar` skips the revoke on `None` and posts the token in the form body |

## 2. Floor 2: no plaintext in the database or the logs

- **At rest.** All five columns bind as `enc:v1:` ciphertext. On live Postgres after the upgrade, no value of the
  four seeded secrets contained its plaintext. A plaintext write would need a bypass of the type, such as raw
  SQL into these columns. The only raw writers are the CLI and the revision, and both encrypt.
- **Error text.** Both engines hide bound parameters, and the backstop regex in `app/core/logging.py` redacts
  any `[parameters: ...]` that still arrives. A failed INSERT's `DBAPIError` carries only ciphertext even
  without `hide_parameters` (pinned).
- **The structlog change.** The four new log sites (`_totp_matches`, `disable_mfa`, `EncryptedText`,
  `_build_gcal_service`) call `structlog.get_logger()` at call time instead of using a module logger. This does
  **not** bypass redaction. The proxy resolves the global configuration when it is first used, and that
  configuration is the same processor chain (`redact_emails` right before the renderer) that
  `cache_logger_on_first_use=True` caches for module loggers. The only difference is when the chain is looked
  up, not which chain runs. I checked this through the real `configure_logging`: an address and a
  `[parameters: ...]` value logged through a fresh proxy both reach the handler redacted (pinned). The four
  sites log only `user_id`, `column` or `sync_id`. The email call-site sweep (`test_floor2_no_email_in_logs`)
  already matches `structlog.get_logger().warning(...)`, because its receiver contains `log`.
- **CLI output.** `encrypt-user-secrets` prints table, column and row id for an unreadable value, never the
  value. The live output showed `oauth_accounts.access_token row o2: cannot decrypt; left as is`.
- **Migration output.** Counts only: `encrypted N`, `N remain plaintext`, `wrote N back as plaintext`.
- **Never returned.** No response model gained a token field, and export still excludes the columns (contract
  section 5, green).

## 3. Floor 4 and lockout: nothing is destroyed

Floor 4 covers uploads and generated content, not provider tokens. C1 nonetheless exists so that a rotation
cannot silently null every token and seed. Verified:

- An unreadable value is never written back: not as `NULL`, and not through the ORM. Live Postgres and the
  SQLite pin agree.
- A dry run writes nothing (live and pinned).
- `_refresh_if_needed` overwrites an unreadable access token only with a freshly refreshed one, which is the C7
  behaviour. When both tokens are `None`, nothing is written.
- `disconnect_calendar` still deletes the row on the user's request, as before. That is an explicit user act.
- The downgrade aborts before writing anything if any value would be lost (undecryptable) or truncated (too
  long).

## 4. Live migration run (throwaway `pgvector/pgvector:pg16`, container `safety-sec005-pg`, torn down after)

I migrated the database to `a1c2d3e4f5a6` and seeded plaintext: one TOTP seed, two OAuth tokens and one
calendar token. Then I ran the steps below in order.

| Step | Environment | Result |
|---|---|---|
| `upgrade head` | multi-user, no key | `RuntimeError: FATAL: SETTINGS_ENCRYPTION_KEY is not set…`, exit 1. Version, widths and values unchanged |
| `upgrade head` | single-user, no key | `encrypted 0`, `4 value(s) remain plaintext … run: python -m app.cli encrypt-user-secrets --apply`. Columns `text` |
| `downgrade a1c2…` | single-user, no key, no ciphertext | `wrote 4 value(s) back as plaintext (protection removed)`. Widths restored |
| `upgrade head` | multi-user, key K1 | `encrypted 4`. Every value `enc:v1:`, no plaintext substring |
| `downgrade` | no key, ciphertext present | `downgrade aborted: encrypted values exist and SETTINGS_ENCRYPTION_KEY is not set; nothing was changed`. Values byte-identical |
| `downgrade` | K1, plus a row under a foreign key K3 | `1 value(s) cannot be decrypted …; nothing was changed`. Unchanged |
| `encrypt-user-secrets` (dry run) | `K2,K1`, with a plaintext row and the K3 row added | `would encrypt: 1; re-keyed: 5; unreadable: 1`, exit 2. Nothing written |
| `encrypt-user-secrets --apply` | `K2,K1` | Exit 2. Decrypting each value with one key at a time: all six readable values are under K2 only, and the K3 row is byte-identical |
| `downgrade` | `K2,K1`, with a 65-character seed added | `0 … cannot be decrypted and 1 value(s) exceed the narrowed width …; nothing was changed`. Unchanged |
| `downgrade` | `K2,K1`, after the long seed was cleared | `wrote 5 value(s) back as plaintext`. Plaintext restored exactly, columns narrowed to `varchar(1000)`/`varchar(64)` |

## 5. Mutation check (scratch copy outside the worktree)

I ran sixteen mutants against `test_floor2_tokens_at_rest.py`, the contract, and backend's two unit files. The
table shows which suite killed each one.

| Mutant | Floor tier | Elsewhere |
|---|---|---|
| Rotation through the ORM attribute (load, reassign, flush) | red | unit rekey |
| Rotation writes `NULL` over an unreadable value | red | unit rekey |
| Rotation does not count unreadable values (the exit gate lies) | red | unit rekey |
| `_totp_matches` returns `True` on a `None` seed (bypass) | red | contract |
| Login gate `mfa_enabled and mfa_secret` (the seed decides) | red | contract, unit MFA |
| `disable_mfa` clears MFA on a `None` seed (self-heal) | red | contract |
| `disable_mfa` answers "MFA is not enabled" on a `None` seed | red | contract |
| `EncryptedText` binds plaintext | red | contract |
| The undecryptable log carries the stored value | red | contract |
| Revoke via `params=` | red | contract |
| Revoke attempted with a `None` token | survives (availability, not a floor) | contract |
| `hide_parameters=False` | red | contract |
| Upgrade without `check_startup()` | red | contract (source order) |
| Downgrade does not abort on undecryptable values | red | **none before this change**: the contract checks the source text only |
| Backup code refused when the seed is unreadable | red | unit MFA |
| `mfa_secret` back to `String(64)` | red | contract |

With the pin as first written (15 cases), the floor tier missed eleven of these: the three rotation
mutants, both `disable_mfa` mutants, the log value, both revoke mutants, the upgrade, the downgrade and the
backup code. The downgrade-abort mutant survived every suite. The pins added here close ten of the eleven. The
one left is revoke-on-`None`, which is availability, not a floor.

## 6. Changes in this review (`safety` paths only)

- `docs/security/threat-model.md`: §5 delta "M34 S2 (M34-S2-SEC-005)". It records that the downgrade **removes
  at-rest protection** and the only case for running it: rolling back to a release older than SEC-005, as an
  explicit operator act, re-upgraded as soon as possible, with dumps from the gap treated as holding live
  credentials. The asset row and B6 are updated. This turns the last contract test green.
- `services/app/tests/safety/test_floor2_tokens_at_rest.py`: ten new test functions (twelve cases; 27 in the file). They cover the OAuth-path MFA,
  backup codes, `disable_mfa`, rotation on real SQL, the upgrade with and without a key, the three downgrade
  aborts, fresh-proxy redaction, the undecryptable log through the real chain, and revoke in the form body.
  The docstring now names the current contract.
- `services/app/tests/safety/FLOORS.md` §2: new subsection "Third-party tokens and the TOTP seed at rest",
  with the mutation record.

## 7. Residuals (not blocking)

1. **Logging backstop over-redacts (`backend`, observability).** `_PARAMS_RE` in `app/core/logging.py` runs to
   the end of the text. The structlog processor first turns a field into `[parameters: redacted]`. The stdlib
   `EmailRedactingFilter` then matches that again on the rendered JSON line and deletes the rest of the line,
   including `event`, `level` and `timestamp`. Nothing leaks, but the event name is lost exactly when a DB
   error is logged. This predates SEC-005. Fix: skip an already-redacted section
   (`\[parameters:(?! redacted\])`), or stop at the closing quote on rendered lines.
2. **Malformed key at worker runtime.** The worker does not call `check_startup()`. A malformed
   `SETTINGS_ENCRYPTION_KEY` there reads every secret as `None`: calendars need to reconnect, and TOTP is
   refused while backup codes still work. This fails closed and destroys nothing. It is the same behaviour as
   SEC-06 per-user credentials. The API refuses to start on such a key.
3. **The migration imports `app.core.secret_box`.** A later change to `secret_box` changes how this revision
   behaves when re-run. Acceptable while the `enc:v1:` format is frozen. A `v2` prefix must keep `v1`
   readable (`data`, `backend`).
4. **R1 still stands.** Nothing in `app/` reads the `oauth_accounts` tokens after login. Not storing them is
   stronger than encrypting them.
5. **R-017** (plaintext OAuth/calendar tokens) is mitigated by this change. Closing it in the risk register is
   the Orchestrator's call.

## 8. Verification

```
$ cd services/app && .venv/bin/python -m pytest tests/safety -q --cov=tests/safety --cov-fail-under=95
Required test coverage of 95% reached. Total coverage: 97.81%
740 passed, 1 skipped, 36 warnings in 352.90s (0:05:52)

$ cd services/app && .venv/bin/python -m pytest tests/contracts -q --no-cov
164 passed, 6 warnings in 8.22s
```
