# StudyAIO threat model

**Owner:** `safety` · **First written:** 2026-10-11 (M32 gate) · **Last delta:** 2026-10-16 (M34-S2, SEC-015 Telegram webhook authenticity)

This is a living document. Every gate's Floors file links to it and adds a dated delta (§5).
The floors are quoted in `docs/strategy.md` §6. The floor-to-test map is
`services/app/tests/safety/FLOORS.md`. Risks are tracked in `docs/risk-register.md` (R-nnn).

## 1. Assets

| Asset | Where | Why it matters |
|---|---|---|
| Users' uploads and generated content (summaries, versions, flashcards, quizzes, study history) | `data/` (blob), Postgres | Floor 4. The product's value; some of it cannot be regenerated (study history) |
| Per-user AI credentials (API keys, Claude CLI OAuth JSON) | `user_settings.settings_json`, `enc:v1:` Fernet ciphertext since SEC-06 | Floor 2. They spend the user's money and identify them to a provider |
| Instance AI credentials (`ZAI_API_KEY` and others, Claude service login) | env from the secret manager; `/run/claude-host` read-only mount | Floor 2 and cost. Prod runs metered `zai` |
| `SETTINGS_ENCRYPTION_KEY`, `JWT_SECRET_KEY`, DB password | env from the secret manager → the deploy directory's `.env` | Losing the key means losing every stored credential. Leaking the JWT key means session forgery (floor 1) |
| Calendar tokens, TOTP seed | `calendar_syncs`, `users.mfa_secret`; `enc:v1:` ciphertext under the same key since SEC-005 | Floor 2. The calendar tokens reach the user's Google Calendar; the seed is their second factor |
| OAuth sign-in tokens (Google, GitHub) | Not stored since SEC-013: used once inside the callback to fetch the userinfo, then discarded. `oauth_accounts.access_token`/`refresh_token` stay one release, always NULL, `EncryptedText` (dropped by `models.secrets-at-rest v3`) | Floor 2. Already-issued tokens stay valid at the provider until expiry or revocation (sign-in scopes only); the copies in pre-SEC-013 dumps are ciphertext |
| Telegram pairing code | `telegram_links.link_token`, SHA-256 digest since SEC-014; the plaintext exists only in the `POST /api/notifications/telegram/link` response to its own user | Whoever holds a pending code can pair their own chat with the account and receive its notifications. Codes never expire (R-048, open) |
| AI-processing consent record (SEC-08, GL#38) | `users.ai_processing_consent_at` / `_version` | Evidence that the user agreed to the disclosure in force before their content left the instance. Only `ai_consent_required` is exposed by the API; the raw record is not |
| AI feedback votes and comments (GL#36) | `ai_feedback` | Owned by the voter. The comment is free text and may hold personal data; it is shown to admins in the aggregate, never logged and never copied into usage events |
| Usage events (GL#37) | `usage_events` | Owned by the actor. Event name from a fixed list, scalar properties under an allowlist, no content; read cross-user only as admin aggregates with no user id |
| Weak-spot state (ADR 0007) | `study_plans`, `targeted_generations`, item provenance on `flashcards`/`quiz_questions` | Owned by the learner; derived from their study history. A generation row names the course and week it targets, so a cross-user read would leak what someone is struggling with |
| User-authored and edited study items (GL#48) | `flashcards`/`quiz_questions` with `origin="user"`; originals kept with `archived_at` | Floor 4: an edit or delete must never destroy the generated original or its review and attempt history |
| Telegram bot token, webhook secret | env (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, both `SecretStr`). The token is in every Bot API URL (`/bot<token>/…`); the secret is registered with `setWebhook` by `python -m app.cli register-telegram-webhook` | The token is full control of the bot: read its updates and message every paired chat as StudyAIO. The secret is what tells Telegram's webhook calls from anyone else's (SEC-015) |
| Outgoing mail | SMTP, never stored | Reset, verification and invite links are bearer tokens. Since GL#53 each one appears in both the HTML and the plain-text part |
| Database dumps | the deploy directory's `backups/` (predeploy + nightly), readable only by the deploy user and the DB container | They hold everything above except the env secrets. AI credentials in them are ciphertext |

## 2. Actors

- **Anonymous internet caller.** Reaches the reverse proxy, then `ui` and `api`. On prod, registration is invite-only.
- **Authenticated user (tenant).** Can be malicious toward other tenants (floor 1) or toward the operator's budget.
- **Uploaded content.** This is attacker-controlled text that reaches the AI (prompt injection) and the parsers
  (PDF, DOCX and PPTX parsing in the worker pools, non-root uid 999 since SEC-006).
- **AI provider.** Its error text can echo credentials back (R-012). Its output is untrusted (citations, JSON).
- **Operator.** Trusted. Holds the env and the host.
- **Supply chain.** Python and npm dependencies, base images, and GitLab CI.

## 3. Trust boundaries and controls

| # | Boundary | Controls (pinned in `tests/safety` unless noted) | Residual |
|---|---|---|---|
| B1 | Internet → API | JWT cookie auth on every user route (unit `test_endpoint_authn_guard.py`). Since SEC-05, `SELF_HOSTED` is authenticated, and anonymous-as-admin needs `SINGLE_USER_MODE` (`test_floor1_anonymous_caller.py`). Startup refuses the committed JWT key whenever login is on (`test_floor2_jwt_default_secret.py`). Redis-backed rate limits fail closed on `/api/auth/*` (SEC-10) | Rate limits key on `request.client.host` and depend on `FORWARDED_ALLOW_IPS` (issue #39; startup warns only). `BIND_HOST` is declared by the operator, not observed, so a mis-declared loopback bind with a published port passes the single-user guard |
| B2 | Tenant → tenant | Floor-1 route sweep (115 method+path pairs, 99 reaching owned tables at M32), function-level unscoped-query and optional-caller detectors (C6), owner-routed SSE events, worker-job pins (recovery, nudges, webhook) | R-010: `review_items` and `quiz_attempts` have no `user_id` and are scoped by join. Opted-in leaderboard rows are visible by the user's own choice |
| B3 | API/worker → AI provider | Floor 3: `get_agent` and `get_embedding_provider` only at the ADR 0003 and ADR 0005 sites. Adapter-boundary redaction with `from None`. Global `AgentError` handler withholds the text (C4). User base URLs are public-only, re-checked at use, with no redirects (SEC-03) | DNS rebinding is narrowed (checked when the config is built and again before connecting), not closed by pinning |
| B4 | Worker → `claude -p` child | `--tools ""`, `--strict-mcp-config`, an allowlisted env, a fresh empty cwd per call, operator-only binary and model (SEC-01), a fixed system prompt, and the host-login copy redacted and removed. Since SEC-006 (option F) every worker pool runs as uid 999, so no pool can drop the child to 10001; instead the adapter **refuses** the CLI before reading any login or spawning (`ClaudeCliUnavailableError`, counted on `studyaio_claude_cli_spawn_refusals_total`) on a non-root multi-user worker, unless the operator sets `CLAUDE_CLI_SHARED_UID_ACCEPTED` or runs `SINGLE_USER_MODE`. `CLAUDE_CLI_UID` on a non-root worker is refused outright. A root worker keeps the AGENT-01 drop to `CLAUDE_CLI_UID` with `extra_groups=[]`. The CLI's `HOME` is a uid-999 `0700` tmpfs (`test_floor2_cli_shared_uid_refusal.py`, `test_floor2_worker_pools_nonroot.py`) | With the opt-in (or single-user) the child runs **at the worker's uid**: it can read `/proc/<worker>/environ` (JWT key, DB URL, `SETTINGS_ENCRYPTION_KEY`), the login mount and every tenant's `data/`. Its only containment then is `--tools ""` and the env allowlist. Prod users who chose `claude_code` lose it until the CLI sidecar (option B) lands. The refusal is a runtime error, not a startup one: the API still offers `claude_code` in settings (backend owes an availability surface) |
| B5 | App → storage (`data/`, DB) | Floor 4: every blob delete is classified against ADR 0004. Re-summarize and regeneration keep versions and history. The account purge sweeps every summary blob, including deleted courses' (C5 ledger, id-shaped segments only) | Courses deleted before `a3ab6ce` are unattributable (R-020 residual) |
| B6 | Credentials at rest | SEC-06: `enc:v1:` MultiFernet. A multi-user start refuses with no key and refuses the all-zero test key outside pytest. Ciphertext-shaped input is never stored verbatim. Export never returns credentials | Since SEC-005 the calendar tokens and the TOTP seed are ciphertext too (`EncryptedText`); since SEC-013 the OAuth sign-in tokens are not stored at all, and since SEC-014 the Telegram pairing code is a SHA-256 digest; a value that cannot be decrypted reads as `None` and is never written back. Rotation is manual (`encrypt-user-secrets`, which exits 2 while any value is unreadable). The key lives in the same `.env` as every other secret, so it does not protect against a host compromise, only against a leaked dump or backup. The migration's downgrade removes at-rest protection (§5, SEC-005) |
| B7 | Billing webhook | Stripe signature, dedupe by event id (unique claim in `stripe_webhook_events`, same transaction as the effect), per-customer ordering under a per-customer advisory lock, customer-scoped mutation (BILL-01, SEC-008, floor-1 pins) | Since M34-S2-SEC-008 the state is in Postgres and kept indefinitely, so a Redis flush no longer reopens replay or reordering. Events in the same second are not ordered. An event with no `id` is applied without a claim row, so it is neither deduped nor a watermark (Stripe always sends one) |
| B8 | Cost | Per-user quota, global daily ceilings and metering on upload, batch, retry, reclassify, merge, review-resolve, CourseOps, chat, Q&A, concepts and, since `421dfa9`, the instance-provider path of `POST /api/settings/test-ai` (QUOTA-01/COST-01, M32 G1). Every ADR 0003 request-time site's route checks the caller's quota before the spend and records against the caller (`test_floor3_request_time_ai_quota.py`) | Own-credential test-ai is rate limited (5/min) but not quota-checked, by design: it spends the user's money. Concepts records only a successful call; a failed provider call there is not metered |
| B9 | CI/CD → prod | Images by SHA from GHCR. `deploy.sh` refuses without the encryption key (exit 68) or without a good pre-migration dump (exit 67), and migrates in a one-off container before start (R-028). `dependency-audit` CI job (pip-audit on the lock, npm audit high/critical; allowlist empty) | The key check tests presence, not validity: a malformed or test key passes the guard, then crash-loops after migrating. `pip-audit` is installed unpinned in CI. The host's `deploy.sh` is a manually installed copy and can drift from the repo |
| B10 | Telegram → bot webhook | Since SEC-015, `X-Telegram-Bot-Api-Secret-Token` is checked with `hmac.compare_digest` against `TELEGRAM_WEBHOOK_SECRET` before anything runs. Unset on a multi-user instance means every call is refused. An authentic update can only pair its chat with the row whose digest matches a `/start` code (SEC-014). Pinned in `test_floor2_telegram_webhook_secret.py` | Single-user with no secret accepts (ruled acceptable, SEC-015 §3). httpx logs the bot-token URL at INFO, unreachable while only the WARNING-level CLI calls `setWebhook` (F1, strict `xfail`, owed by `backend`). The secret's strength is not validated. Pairing codes never expire (R-048) |

## 4. Out of scope or accepted

- Prompt injection that changes *the injector's own* summary is accepted. The CLI has no tools and the API backends
  have no tool use, so injected text cannot reach another tenant's data or any secret.
- `SINGLE_USER_MODE` on loopback, or with `I_UNDERSTAND_NO_AUTH`, is the operator's choice.

## 5. Deltas

### 2026-10-11, M32 gate

New surfaces and their judgement. Detail is in `docs/gates/M32/floors.md`.

1. **Per-user encrypted credentials and key handling (SEC-06).** Closed for floor 2 and mutation-checked. New risk:
   the key is a single point of loss. There is no key escrow outside the secret manager. Backups are useless for credentials
   without the key.
2. **Single-user mode (SEC-05).** Opt-in only. Startup refuses a non-loopback declared bind. A floor-1 pin was added
   at this gate (B1).
3. **Redis rate limiter, fail-closed on auth (SEC-10).** Brute-force protection survives a Redis outage, at the cost
   of auth availability. While Redis is down, the rate-limited auth routes return 503: register, login,
   forgot/reset password, resend verification, OAuth MFA completion, demo login and account delete. `/refresh` has no
   limit, so existing sessions continue. The per-account login throttle still fails open, but login is refused
   before it runs.
4. **CLI sandbox at uid 10001 (AGENT-01).** Closed and mutation-checked. Residuals are in B4.
5. **Re-embed, recovery and backup worker jobs.** Re-embed embeds before it deletes, in one transaction, per user.
   Recovery is worker-only, resumes as the row owner and never deletes (pinned). Backup scrubs the DB password from
   output, and its retention prunes only backup copies, outside `data/`.
6. **Dependency audit in CI (SEC-07).** Green, with an empty allowlist. A lift of a security-relevant framework
   silently disabled the floor-1 sweep once (R-040). Any dependency lift now re-runs the floor tier and compares
   sweep counts. At this gate the counts after the pytest 9.1.1 lift are 149 `/api` routes, 115 swept pairs and
   99 owned-reaching, against 149, 115 and 98 before it.
7. **`deploy.sh` guards.** Both refusals fired on the first wave-2 deploy (two refused runs) and left the old
   stack untouched, then the third run deployed. Residuals are in B9.

### 2026-10-11, G1 follow-up (M33-S1-SAFETY-005)

1. **`POST /api/settings/test-ai` is no longer an open cost surface.** Backend `421dfa9` checks
   `check_ai_quota(session, user.id, user.tier)` (per-user quota and global ceilings) before `get_agent` when the
   caller is on the instance provider, records `record_ai_call` against the caller on success and on provider
   failure, and rate limits every path to 5/minute. The own-credential path is unmetered, and it cannot reach the
   operator's key: the factory refuses an own-provider config with no credential (`ProviderCredentialError`).
   Refusals are the generic 402/429 bodies and name no credential. Provider errors stay redacted
   (`test_floor2_provider_error_never_echoes_a_stored_credential[POST /api/settings/test-ai]`). The ADR 0003 site count is
   unchanged at five. M32 N-1 is **resolved**; `docs/gates/M32/floors.md` is left as the gate record.
2. **Pinned structurally.** Every ADR 0003 request-time `get_agent` site is mapped to the routes that reach it,
   and each route must check the caller's quota before the spend (unconditionally, or behind only "the caller's
   config is None") and record against the caller. A sixth site cannot be added to the ADR without a route entry
   here (`services/app/tests/safety/FLOORS.md`, floor 3).
3. **Worker and api metrics (G3).** Labels are `stage`, `outcome` and
   `error_class` only. `error_class` is `type(exc).__name__`, a class name fixed by code, so it cannot carry a
   message. The api's Instrumentator labels by route template (`/api/courses/{code}`) and groups unmatched paths
   as `none`, so no id, course code or email reaches a scrape. Pinned in `test_floor2_metrics_labels.py`. The
   multiprocess tmpfs holds only sample files (metric name, labels, value), not secrets. Residual: it is mounted
   `mode=1777`, so the uid-10001 CLI child could write into it if it ever had tools. It has none (`--tools ""`,
   B4), but `0700` would be enough because the worker runs as root (devops). Both `/metrics` endpoints are
   unauthenticated and the api's is reachable on the private network at `:8000`. That exposes route-level traffic volume and
   latency, which identify no one.

### 2026-10-11, M33 S1 (M33-S1-SAFETY-033)

1. **AI-processing consent (SEC-08, GL#38).** A 403 `ai_consent_required` now precedes every AI spend and every
   enqueue of AI pipeline work. The gated route set is derived from code, not listed: any route whose handler
   reaches `check_ai_quota`, `get_agent`, `run_pipeline`, `resume_pipeline`, `.apply_async` or `.delay` must
   depend on `require_ai_consent` (13 routes). The dependency runs before the handler, so nothing is spent or
   queued for an unconsented caller. Single-user mode is the only bypass; role, tier and `SELF_HOSTED` are not.
   A consent to older wording counts as none. Extends B3 and B8.
2. **Email addresses out of logs.** Call sites log `user_id`, not addresses (floor-tier AST sweep, wider than
   the unit one). The structlog `redact_emails` processor and the stdlib `EmailRedactingFilter` are a backstop
   with two holes, recorded as strict `xfail`s: (F1) `log.exception(...)` makes stdlib append a second,
   unredacted traceback; (F2) the Celery worker never calls `configure_logging`, so worker logs (notifications,
   email delivery, pipeline) are not redacted at all. Neither is a floor breach: the call-site rule holds, and an
   address only reaches a log through exception text. Both are closed (see M33-S1-SAFETY-040 below). Still
   unfiltered: handlers that loggers such as `uvicorn.access` attach for themselves, and any handler added after
   `configure_logging`.
3. **AI feedback and usage events (GL#36, GL#37).** New user-owned tables, both deleted with the account. Votes
   land only on the caller's own targets; a foreign and a missing target return the same 404. Usage events are
   always keyed on the caller, and a client may report only two view events, for its own course. The two admin
   aggregates are cross-user by design and return no user id. Residual: `recent_negative` hands admins
   free-text comments with the target's `course_id`, which an admin can trace to an owner. That is acceptable
   for triage, but the response is an untyped `list[dict]`, so only the floor test stops a user id being added.
4. **Retrieval floor and follow-ups (GL#35).** Search is always keyed on the caller. A follow-up query folds in
   only the caller's previous message from the caller's own session. A below-floor turn returns a fixed reply,
   builds no agent and is not metered. The quota check still runs before it, so a fixed reply cannot be used to
   skip quota on a real call. No new AI or embedding call site.
5. **Disclosure accuracy (frontend `ConsentDialog`, reviewed against the prompts).** The code backs "only your
   own content": every prompt input is read from the caller's own rows. Three claims need tighter wording.
   (a) The account email and username are never put into a prompt, but anything inside an uploaded file or a
   file name is sent verbatim. (b) "What is sent" leaves out file names, course codes and week numbers, the
   recent chat history sent with each chat turn, course documents (outlines, syllabi) sent for deadline
   extraction, and AI-generated summaries sent back to generate flashcards and quizzes. (c) With a remote
   embedding backend, lecture text and questions also go to the embedding provider, which can differ from the
   chat provider.

### 2026-10-12, M33 S1 (M33-S1-SAFETY-040)

1. **F1 and F2 closed (SEC-08, GL#38).** `EmailRedactingFilter` now renders `exc_text` before the stdlib
   Formatter does and scrubs it and `stack_info`, so `log.exception(...)` emits no address (`06c4fcb`). The
   worker connects `configure_logging` to Celery's `setup_logging` signal, which also stops Celery from
   replacing the root logger; worker and beat both fire it, and prefork children inherit the configured
   handlers (`344ce7e`). Both pins are plain floor-tier tests now, plus a runtime test that fires the signal.
   Limit unchanged: the filter covers only handlers that carry it, so a handler attached after
   `configure_logging` (or one a library attaches to its own logger) must add the filter itself.

### 2026-10-12, M33 S1 (M33-S1-SAFETY-050)

1. **Rate limits count with a moving window (SEC-10, `b1e20d9`).** A fixed window forgets every hit when it
   closes, so a caller could spend the login budget at the end of one window and again just after it: ten
   guesses in 0.2 s against a 5/minute limit. CI hit the accidental version of this (a sixth login allowed).
   Every limit is now moving-window, through the one factory (`build_limiter`), on both the `memory://` and the
   Redis store. No limit was loosened and the outage policy is unchanged: `/api/auth/*` fails closed (503),
   everything else fails open. All three are pinned in the floor tier (`services/app/tests/safety/FLOORS.md`,
   "SEC-10") with a controlled limiter clock, and mutation-checked. Cost: one stored timestamp per allowed hit,
   negligible at these budgets.
2. **The per-account login throttle was off in the whole unit tier.** The unit Redis fake had no `incr`, so
   `record_failure` raised, logged `login_throttle_unavailable` and returned 0 in every unit test, and nothing
   failed. Production was not affected (real Redis has `incr`), but no unit test exercised the throttle while
   the gap existed. The fake now implements `incr`/`expire`/`ttl`, and the floor tier fails if the throttle calls
   a Redis method the fake lacks, or if the throttle does not count and engage under the fake.
3. **Asymmetric outage policy: accepted, no owner decision needed.** On a Redis outage the per-address auth
   limiter fails closed and the per-account login throttle fails open (documented in `login_throttle.py`). With
   the default configuration both use the same Redis, so when the throttle is down the limiter is too, and login
   is already a 503 before the throttle runs (M32 delta 3). The throttle fails open while login still works only
   on a partial outage, or when `RATE_LIMIT_STORAGE_URI` points the limiter at a different store. The
   per-address 5/minute limit then still holds; only the per-account brake against guesses spread over many
   addresses is lost. Failing the throttle closed would add a second way for a cache fault to lock every user
   out of login, for a short-lived gain. Residual, for `backend`: `login_throttle_unavailable` is a log line
   only, with no counter, so a sustained fail-open is visible only to someone reading logs. A counter is
   recommended, not required. B1 is unchanged.

### 2026-10-15, M33 S2 (M33-S2-SAFETY-024, GL#45)

Weak-spot engine (ADR 0007 Decision 8): two new tables (`targeted_generations`, `study_plans`), six
routes under `/api/weak-spots` and `/api/study-plan`, `GET /api/study/items`, and one new worker task
with a beat recovery job. Verdict: PASS with notes, after the floor-4 defect in item 5 was
fixed in M33-S2-AI-053. Pins in `services/app/tests/safety/FLOORS.md`, "Weak-spot engine".

1. **The worker acts as the row's owner.** The task receives only the `targeted_generations` id. `_claim`
   loads that row by id (classified, worker-only); every later read, the adapter's credentials, usage
   metering and every insert act as `row.user_id`, and the source lookups are owner-scoped, so a row
   naming another user's course fails `no_source` without an AI call. Recovery (`_recover_stuck`) is a
   cross-user beat UPDATE to `failed`/`timeout`; `_persist` re-checks `status = 'running'` under a row
   lock (refreshed since item 5), so a recovered row gets nothing inserted later.
2. **Delimited, not escaped (accepted).** The targeted prompts mark the topic, missed-question and
   already-have blocks as untrusted data, but the block delimiters are not escaped. A slide title or
   stem containing `</missed_questions>` can close its block early. Every span comes from the owner's
   own uploads and items and is spent on the owner's own credentials, so the reach is self-only.
   Escaping is recommended to `ai`, not required.
3. **`error_code` is returned, and that is safe.** `GET /api/weak-spots/targeted/{id}` returns
   `error_code`, although the response model's docstring says it is "stored, not returned". Every value
   is a literal from a fixed set (`no_source`, `empty_output`, `superseded`, `timeout`, `ai_unavailable`,
   `ai_error`, `internal_error`, `enqueue_failed`), and provider text reaches neither the row, the logs
   (`error_class` is a type name) nor the metrics. The docstring is worth correcting (`backend`).
4. **Daily cap is count-then-insert (accepted).** Two concurrent requests for different units can both
   pass a count of 5 and make 7 rows that day. The in-flight unique index stops duplicates for one unit,
   and the tier's AI quota still bounds spend, so the excess is one generation at most per race.
5. **Floor 4 was red: the re-check read a stale object (fixed).** Sessions do not expire on commit
   (`expire_on_commit=False`), so `_persist`'s `SELECT … FOR UPDATE` returned the identity-map copy
   `_claim` loaded, still `running`, and a row the recovery job failed mid-generation got items
   inserted and was flipped back to `completed`. Found by `qa`; fixed in M33-S2-AI-053
   (`.execution_options(populate_existing=True)` on the `_persist` and `_claim` re-selects). The floor
   pin runs on an identity-map session; it fails with `populate_existing` removed from `_persist`.

### 2026-10-15, M33 gate

Roll-up of every M33 surface since the M32 gate, with the S3 tail (AI-067, GL#53, FRONTEND-063,
QA-064) reviewed for the first time. Detail and the mutation table are in `docs/gates/M33/floors.md`.

1. **Consent, feedback, usage events (S1).** Unchanged since the S1 deltas above. Re-mutated at the
   gate: dropping `require_ai_consent` from the targeted route, and dropping the caller's ownership
   from the feedback target lookup, each turn floor pins red.
2. **Weak-spot API and targeted queue (S2).** No request-time AI site was added (ADR 0007 Decision 5,
   ADR 0003 unchanged at five). The worker acts as the row owner. Re-mutated at the gate: an
   unscoped `get_targeted` and a missing `populate_existing` are each red.
3. **Study-item CRUD and upload placement (S3).** Owner-scoped, soft delete only, no existence oracle
   (SAFETY-059). Re-mutated at the gate: unscoped `_owned_item`, code-only `get_or_create_course`
   and a hard delete in `archive_flashcard` are each red.
4. **Three worker pools and the credential split (GL#51).** `worker` and `worker-ondemand` hold the
   Claude login; `worker-maintenance` holds none and, since `1815812`, runs as the image user, not
   root. It still receives `.env` (instance AI keys, `SETTINGS_ENCRYPTION_KEY`) because re-embed may
   need the embedding key. The static routing pins assume the broker delivers each message only to
   its routed queue. Before AI-067 (`2bed33a`, R-044) every queue was a bare `Queue(name)` sharing one
   exchange and routing key. Celery's own publish uses the anonymous exchange keyed on the queue name,
   so tasks still reached one queue and the fault stayed latent. A publisher that addressed an AI
   queue's declared exchange, though, would also have delivered to `maintenance`, whose pool has no
   login. That would have meant a failed task, or a call on instance keys through the adapter. No
   floor would have been crossed, but the split's floor-2 premise would not have held. A delivery
   pin now publishes every AI task both ways (as `send_task` and to the declared address) on an
   in-memory broker. It fails if the task lands anywhere but its routed queue.
5. **Outgoing mail (GL#53).** `Date`, `Message-ID` (sender domain only) and a `text/plain` part
   derived from the HTML body. The plain part repeats each link as a visible URL, so a reset,
   verification or invite token now appears twice per message. Logging is unchanged: `email_sent`
   and `email_send_failed` carry the subject only, and subjects carry no address or token. A runtime
   pin sends each token-bearing mail through the real logging configuration at DEBUG, on success and
   on SMTP failures that name the recipient, and finds neither the address, the token nor the body
   in the stream. Residual (pre-M33): the pipeline-complete and exam-reminder subjects carry a file
   name, course code or exam title, which reach the `email_sent` line.
6. **Russian locale on demand (FRONTEND-063).** The loader is a fixed map from a supported tag to a
   bundled chunk. No URL, user input or credential is involved. No floor surface.
7. **e2e session minting (QA-064).** `services/ui/e2e/seed_e2e.py session` writes a consented
   user (resetting the password of an existing one with that address) and prints access and refresh
   tokens signed with whatever `JWT_SECRET_KEY` it is given. It is test-only by location: neither
   image contains it (the UI runtime stage copies only `dist/` and `nginx.conf`; the API build context
   is `services/app`), and only Playwright fixtures call it, in the CI `e2e-tests` job against its
   own throwaway Postgres. Against production config it gives nothing an operator lacks: minting a
   valid token needs the production signing key and a DB connection, which is already full control.
   Without that key it signs with the committed default, which production refuses at startup, so its
   tokens are rejected. Residual: the script has no guard of its own. Pointed at a real database, it
   would reset the named user's password. Recommendation (`qa`): refuse unless an explicit e2e marker
   is set, or the target database is not the configured production one.
8. **Floor-1 sweep growth.** 169 `/api` routes, 133 swept pairs and 111 owned-reaching, against
   149, 115 and 99 at M32. The only violation is still the ruled opt-in leaderboard. No dependency
   moved in M33, so the R-040 lift rule did not apply.

### 2026-10-16, M34 S2 (M34-S2-SEC-005, secrets at rest)

Third-party tokens and the TOTP seed are encrypted at rest (`models.secrets-at-rest v1`). Review:
`docs/gates/M34/sec005-safety.md`. Verdict: APPROVE.

1. **Scope.** `oauth_accounts.access_token`/`refresh_token`, `calendar_syncs.access_token`/`refresh_token`
   and `users.mfa_secret` are `secret_box.EncryptedText`: `enc:v1:` MultiFernet ciphertext under
   `SETTINGS_ENCRYPTION_KEY`, the SEC-06 scheme. A database dump or a `backups/` file no longer hands over
   anyone's Google or GitHub access or their second factor. `calendar_syncs.sync_token` and
   `telegram_links.link_token` are reviewed and stay plaintext (`test_floor2_tokens_at_rest.py`).
2. **Unreadable reads as `None`, and fails closed.** A value written under a key that is no longer configured,
   or tampered with, loads as `None` and logs `secret_at_rest_undecryptable` with the column name only. For
   the seed, `mfa_enabled` alone decides whether a second factor is required: a TOTP code against a `None`
   seed is refused exactly like a wrong code and counted by the login throttle, on the password and the OAuth
   path. Backup codes still sign in. `disable_mfa` refuses and changes nothing; recovery is the admin
   `clear_mfa`.
3. **Rotation works on stored strings.** `encrypt-user-secrets` reads and writes the five columns through
   Core over plain `Text` columns, never the mapped attribute, so an unreadable value is left byte-for-byte
   as stored and is counted. The command exits 2 while the count is above 0. **Do not drop an old key until a
   dry run reports `re-keyed: 0` and exits 0.**
4. **Error text.** Both engines (`app/core/database.py`, `alembic/env.py`) set `hide_parameters=True`, and the
   logging backstop redacts any `[parameters: ...]` section. Before this change a failed flush in the OAuth
   callback logged the plaintext provider tokens.
5. **Upgrade.** Revision `b2d4f6a8c0e1` calls `secret_box.check_startup()` first. A multi-user instance with no
   key aborts before any column is touched. A single-user instance with no key keeps its values and prints
   how many remain plaintext and the `encrypt-user-secrets --apply` command. It never prints a value.
6. **Downgrade.** The downgrade removes at-rest protection: it decrypts every value of the five columns and
   writes it back as plaintext, then narrows the OAuth columns to `String(1000)` and `mfa_secret` to
   `String(64)`. It runs in the single migration transaction and aborts, changing nothing, when ciphertext
   exists and no key is set, when any value cannot be decrypted, or when a decrypted value is longer than the
   narrowed width. An operator runs it only to roll the application back to a release older than SEC-005,
   because that code cannot read ciphertext: it would send `enc:v1:...` to Google as a bearer token and
   compare TOTP codes against ciphertext. It is an explicit operator act, never a step in a routine redeploy.
   After it, every token and seed is plaintext in the database and in every later dump; re-run the upgrade as
   soon as the rollback is over, and treat dumps taken in between as holding live credentials.
7. **Residual.** The key sits in the same `.env` as the database password, so this protects dumps and backups,
   not a compromised host. Nothing in `app/` reads `oauth_accounts` tokens after login; not storing them at
   all (contracts-safety R1) remains the stronger follow-up for `backend`.

### 2026-10-16, M34 S2 (M34-S2-SEC-006, option F)

The AI pools run non-root; the CLI's lost uid drop becomes a refusal. Review and options:
`docs/gates/M34/sec006-safety.md`. Code: devops `fef057f` (cherry of `b27fc19`), ai `36ebc83`.
Verdict: APPROVE (option F, with the §5 pins in this change).

1. **Parsing is no longer root.** `worker`, `worker-ondemand` and `worker-maintenance` (and `api`, `beat`
   through the image's `USER studyaio`) run as uid 999 in every stack: base, `prod`, `production`,
   `selfhosted` and `selfhosted`+`production`, merged with `!reset`/`!override` honoured. A parser RCE on an
   upload still reads every tenant's data and the worker env (it did at root too) but no longer gets root's
   persistence in `/usr/local`/`/app`, root-owned writes into bind mounts, or the default capability set.
   M32 N-3 is met.
2. **The CLI is refused, not contained.** A uid-999 process cannot `setuid`/`chown`, so the AGENT-01 drop to
   10001 (R-030) is impossible on these pools. `ensure_claude_cli_spawnable()` is the first statement of
   `ClaudeCodeAdapter._run_once`: non-root + multi-user + no opt-in raises `ClaudeCliUnavailableError`
   (a plain, non-retryable `AgentError`) before the setup token, the host login or the user's credentials
   are opened, before any temp dir, chown or spawn. The stage fails once, and its `pipeline_runs` row names
   the remedy and no credential. This holds for the instance login and per-user `claude_code` alike,
   directly, through `get_agent` and through `classify`. Mutation-checked in a scratch copy: deleting the
   guard call turns 30 pins red, and so do a guard that allows non-root and a guard that checks the
   opt-in before `CLAUDE_CLI_UID`.
3. **R-030 under F.** The control R-030 closed (child at 10001, denied on `/app/data` and
   `/run/claude-host`, verified on the prod host 2026-10-10) no longer exists on the AI pools. What replaces
   it: on prod, multi-user and without the opt-in, the CLI never runs, so there is no child to contain. If an
   operator sets `CLAUDE_CLI_SHARED_UID_ACCEPTED=true`, the child runs at 999 and R-030's isolation is gone
   by that operator's explicit choice. Compose and `.env.example` must never default the opt-in on (pinned).
   R-030 should be annotated "superseded by SEC-006 F: refused, not isolated; re-closed by option B".
4. **The 2026-10-10 `data/` `750` decision.** `750` with owner 999 kept uid 10001 out of tenants' files. Under
   F it protects **nothing** against the CLI: a spawned child is uid 999, the owner. It still protects
   against other host and container uids, so keep it. Against the CLI, the protection is the refusal: only
   while the opt-in is off. Under option B the sidecar has no `data/` mount and the point is moot.
5. **HOME and the login dir.** The CLI's `HOME` on each AI pool is `/tmp/claude-home`, a tmpfs with
   `uid=999` and `mode=0700`, never `/`, `/root`, `/app`, `data/` or the login mount. The host login dir is
   owned by 999 at `0700`/`0600`; the preflight and setup scripts never suggest a wider `chmod` (pinned).
   Residual: the single-file mounts at `/root/.claude/*` are now unreachable (uid 999 cannot enter `/root`),
   so the host-login fallback reads `CLAUDE_HOST_CREDENTIALS_FILE` under `/run/claude-host` only. That is an
   availability point, not a floor one.
6. **Pins assume uid 999 for `studyaio`.** The Dockerfile allocates it with `useradd -r` (first system
   account on python:3.12-slim, observed 999). A pin holds that it stays the first system account; pinning
   `-u 999 -g 999` explicitly is recommended (`devops`).
7. **Metrics.** `studyaio_claude_cli_spawn_refusals_total{stage,outcome,error_class}` carries only literals and
   a class name; it is the one reviewed `error_class=<local>` site in `test_floor2_metrics_labels.py`.
8. **Floor-tier repair.** Twenty-seven spawn pins and ten more (37 in all) hit the guard on a non-root
   developer run, and the Sentry pin passed *vacuously* (a refusal is an `AgentError` too). Each now names
   the deployment it is about: `cli_shared_uid_opt_in` (non-root pool, opt-in; the path prod reaches when
   it spawns) or `cli_root_worker` (the AGENT-01 drop). Both pin `os.geteuid`, so the tier means the same as
   root (CI) and as a developer, and the Sentry pin asserts the CLI was reached.

### 2026-10-16, M34 S2/S3 (M34-S2-SEC-008, M34-S3-BACKEND-012)

Stripe dedupe and ordering in Postgres; case-insensitive course lookup on card/quiz add; the
`LOGIN_THROTTLE_UNAVAILABLE{action}` counter; `GET`/`PATCH /api/onboarding`. Review:
`docs/gates/M34/sec008-012-safety.md`. Verdict: APPROVE.

1. **B7 hardened.** Claim (insert-or-skip on the unique event id) and effect share one transaction: a failed
   effect rolls the claim back, so Stripe's retry applies, and a crash can no longer leave a dedupe mark
   without its effect. The watermark is read under `pg_advisory_xact_lock` on the customer (contracts-safety
   R2), and an event naming no customer skips ordering. A stale event is committed as `stale`, so its replay
   is a no-op.
2. **`stripe_webhook_events` belongs to nobody.** It holds Stripe's event id, type, customer id, `created` and
   our decision: no `user_id`, payload or email. No route reads it. It is in `GLOBAL_TABLES` (the account
   delete loop skips it) and `_tenant.UNOWNED_TABLES` (the floor-1 sweep classifies it).
3. **Account deletion unlinks, never deletes (R4).** `_unlink_stripe_events` nulls `stripe_customer_id` with an
   `UPDATE` on the deleted user's customers, read from `subscriptions` before that table's rows go. The event
   rows and their dedupe survive (ruling 3, floor 4); the pseudonymous link to the person does not.
4. **Onboarding (floor 1).** Every statement binds the caller. `quiz_attempts` has no `user_id`, so its branch
   joins `quiz_questions` to `courses` and filters on `courses.user_id`. `PATCH` updates `users` keyed on
   `users.id == caller`; the body forbids extra fields, so it cannot name a target.
5. **`LOGIN_THROTTLE_UNAVAILABLE{action}` (floor 2).** One label, values `read`, `record`, `clear`, `limit`,
   all literals. Closes the M33-S1-SAFETY-050 residual (a sustained fail-open is now visible on a scrape).
   `ENUM_LABELS` in `test_floor2_metrics_labels.py` holds the closed set.
6. **Residual (pre-existing, not floor 2).** `billing_service` logs Stripe customer ids
   (`subscription_created`, `checkout_completed`, `webhook_subscription_not_found`). A customer id is a
   pseudonymous identifier, not a credential; recommended for `backend`: drop it from those lines, or log a
   hash. The advisory-lock key is a bound parameter carrying the customer id; the request
   engine's `hide_parameters=True` (C6, `app/core/database.py`) keeps it out of error text.

### 2026-10-16, M34 S2 (M34-S2-SEC-013, M34-S2-SEC-014)

OAuth sign-in tokens are no longer stored (`models.secrets-at-rest v2`); Telegram pairing codes are stored as
SHA-256 digests (`models.telegram-pairing-code v1`). Revision `c3e5a7b9d1f2`. Review:
`docs/gates/M34/sec013-014-safety.md`. Verdict: APPROVE.

1. **OAuth tokens (contracts-safety R1).** The callback uses the provider's token once, to fetch the userinfo,
   and discards it. `create_or_link_oauth` takes no token; the link branch stores none; the known-identity
   branch writes `None`, which sweeps a value the previous release wrote during the deploy window. Google is
   no longer asked for `access_type=offline`. The upgrade nulls both columns on every row with one Core
   `UPDATE`; no row is deleted and the identity link (`user_id`, `provider`, `provider_user_id`) is unchanged,
   so sign-in works as before.
2. **Columns kept one release.** `deploy.sh` migrates while the old api still serves and relies on migrations
   being backwards-compatible for one release; the old api's ORM `SELECT` on `oauth_accounts` would fail on a
   dropped column. So the columns stay, always NULL and still `EncryptedText` (a straggler write is
   ciphertext), and stay in `MUST_ENCRYPT` and `RAW_SECRET_COLUMNS`. `models.secrets-at-rest v3` drops them.
3. **Downgrade (OAuth).** It changes nothing: the nulled tokens **cannot be restored**. Nothing in `app/` ever
   read them after login, so no older release needs them. The last copies are ciphertext in the pre-deploy dump.
4. **Pairing code.** `generate_link_token` stores only `hash_magic_link_token(code)` and returns the plaintext
   once to its own user. `verify_link` looks up by digest in SQL; presenting the stored digest is a miss, so a
   database dump no longer lets anyone pair a chat with an account. Neither the code nor its digest is logged.
   The upgrade nulls every pending code (unused codes stop working, per the user's 2026-10-16 decision) and
   keeps every linked chat.
5. **Downgrade (Telegram).** It nulls every digest too: the older code compares plaintext, so a stored digest
   presented as a code would match. Pending codes are lost on rollback; users click "Link Telegram" again.
6. **Floor 4.** Provider tokens and pending pairing codes are credentials, not uploads or generated content;
   the revision deletes no row in either table.
7. **Residual, accepted.** (a) Already-issued provider tokens stay valid at Google/GitHub until expiry or
   revocation; their scopes are sign-in only, and nothing revokes them at deploy. (b) Deploy window: the old
   api may still write ciphertext tokens (swept on that user's next sign-in, or by v3) and plaintext pairing
   codes (never matched by the new lookup, so inert; the downgrade nulls them); a digest written by the new
   api could be presented to the old api's plaintext comparison by someone reading the database in that
   window. (c) Pairing codes still never expire (R-048, open). (d) Pre-existing, outside this change (not floor
   2 now that a forged `/start` needs the plaintext code): the Telegram webhook's "secret" header is compared
   against `telegram_webhook_url` itself, a URL derivable from the public host, with `!=` rather than
   `hmac.compare_digest`. Recommended for `backend`: a random `TELEGRAM_WEBHOOK_SECRET` registered with
   `setWebhook(secret_token=...)` and compared in constant time. Done in SEC-015, next delta.

### 2026-10-16, M34 S2 (M34-S2-SEC-015, R-052)

The Telegram webhook is authenticated by a dedicated secret (new boundary B10). Review:
`docs/gates/M34/sec015-safety.md`. Verdict: APPROVE.

1. **Check.** `TELEGRAM_WEBHOOK_SECRET` (`SecretStr`) is compared with `hmac.compare_digest` against the header,
   before the body is parsed or the handler runs. A wrong or missing header gets the same 403 as before. The
   webhook URL is no longer the secret: it was derivable from the public host, and the link endpoint returns
   its last segment to every user.
2. **Fail closed.** On a multi-user instance (`SELF_HOSTED` included), an unset secret means every call is
   refused, with one valueless warning per process. Telegram pairing stops until the operator sets the secret
   and runs `python -m app.cli register-telegram-webhook`.
3. **Single-user ruling.** With no secret, single-user mode accepts. That instance has one tenant, and anyone
   who reaches it is already its admin (`check_single_user_mode`). A set secret is still enforced there.
4. **What an authentic update can do (floor 1).** Only `/start <code>`, which pairs the sending chat with the one
   row whose digest matches. A forged update carrying a valid code is now refused before any statement.
5. **Secrets out of output (floor 2).** The secret and the bot token are read only at reviewed sites, never
   returned, never logged by app code. The CLI prints only an httpx error's type name, never its text (which
   can name the bot-token URL). Pinned in a fresh process across success, connect error, timeout, rejection
   and non-JSON reply. The send path's `exc_info` on a refused connection carries no token.
6. **Finding F1, not blocking.** httpx's own INFO line prints the `setWebhook` URL, bot token included.
   It is unreachable: the only caller is the CLI, which logs at WARNING, and both facts are pinned. It is a
   strict `xfail` until `backend` caps the `httpx`/`httpcore` loggers in `configure_logging`.
7. **Residual.** `bot_username` is derived from the webhook URL (functional bug, not a floor). The secret's
   strength is not validated (Telegram enforces 1-256 `[A-Za-z0-9_-]` at registration only). A secret rotation
   refuses updates until re-registration. Pairing codes never expire (R-048).
