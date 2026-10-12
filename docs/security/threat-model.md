# StudyAIO threat model

**Owner:** `safety` · **First written:** 2026-10-11 (M32 gate) · **Tree:** `94a1374`

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
| OAuth and calendar tokens | `oauth_accounts`, `calendar_syncs`, **plaintext** | R-017 residual. They are not AI credentials, so outside floor 2's literal text |
| AI-processing consent record (SEC-08, GL#38) | `users.ai_processing_consent_at` / `_version` | Evidence that the user agreed to the disclosure in force before their content left the instance. Only `ai_consent_required` is exposed by the API; the raw record is not |
| AI feedback votes and comments (GL#36) | `ai_feedback` | Owned by the voter. The comment is free text and may hold personal data; it is shown to admins in the aggregate, never logged and never copied into usage events |
| Usage events (GL#37) | `usage_events` | Owned by the actor. Event name from a fixed list, scalar properties under an allowlist, no content; read cross-user only as admin aggregates with no user id |
| Database dumps | the deploy directory's `backups/` (predeploy + nightly), readable only by the deploy user and the DB container | They hold everything above except the env secrets. AI credentials in them are ciphertext |

## 2. Actors

- **Anonymous internet caller.** Reaches the reverse proxy, then `ui` and `api`. On prod, registration is invite-only.
- **Authenticated user (tenant).** Can be malicious toward other tenants (floor 1) or toward the operator's budget.
- **Uploaded content.** This is attacker-controlled text that reaches the AI (prompt injection) and the parsers
  (PDF, DOCX and PPTX parsing in the root worker).
- **AI provider.** Its error text can echo credentials back (R-012). Its output is untrusted (citations, JSON).
- **Operator.** Trusted. Holds the env and the host.
- **Supply chain.** Python and npm dependencies, base images, and GitLab CI.

## 3. Trust boundaries and controls

| # | Boundary | Controls (pinned in `tests/safety` unless noted) | Residual |
|---|---|---|---|
| B1 | Internet → API | JWT cookie auth on every user route (unit `test_endpoint_authn_guard.py`). Since SEC-05, `SELF_HOSTED` is authenticated, and anonymous-as-admin needs `SINGLE_USER_MODE` (`test_floor1_anonymous_caller.py`). Startup refuses the committed JWT key whenever login is on (`test_floor2_jwt_default_secret.py`). Redis-backed rate limits fail closed on `/api/auth/*` (SEC-10) | Rate limits key on `request.client.host` and depend on `FORWARDED_ALLOW_IPS` (issue #39; startup warns only). `BIND_HOST` is declared by the operator, not observed, so a mis-declared loopback bind with a published port passes the single-user guard |
| B2 | Tenant → tenant | Floor-1 route sweep (115 method+path pairs, 99 reaching owned tables at M32), function-level unscoped-query and optional-caller detectors (C6), owner-routed SSE events, worker-job pins (recovery, nudges, webhook) | R-010: `review_items` and `quiz_attempts` have no `user_id` and are scoped by join. Opted-in leaderboard rows are visible by the user's own choice |
| B3 | API/worker → AI provider | Floor 3: `get_agent` and `get_embedding_provider` only at the ADR 0003 and ADR 0005 sites. Adapter-boundary redaction with `from None`. Global `AgentError` handler withholds the text (C4). User base URLs are public-only, re-checked at use, with no redirects (SEC-03) | DNS rebinding is narrowed (checked when the config is built and again before connecting), not closed by pinning |
| B4 | Worker → `claude -p` child | `--tools ""`, `--strict-mcp-config`, an allowlisted env, a fresh empty cwd per call, operator-only binary and model (SEC-01), a fixed system prompt, a uid drop to 10001 with `extra_groups=[]` (AGENT-01), and the host-login copy redacted and removed | The uid drop is configured only by `CLAUDE_CLI_UID` in compose. If it is unset, the child stays root with only a log line. The worker itself runs as root (`user: "0:0"`) and parses untrusted documents |
| B5 | App → storage (`data/`, DB) | Floor 4: every blob delete is classified against ADR 0004. Re-summarize and regeneration keep versions and history. The account purge sweeps every summary blob, including deleted courses' (C5 ledger, id-shaped segments only) | Courses deleted before `a3ab6ce` are unattributable (R-020 residual) |
| B6 | Credentials at rest | SEC-06: `enc:v1:` MultiFernet. A multi-user start refuses with no key and refuses the all-zero test key outside pytest. Ciphertext-shaped input is never stored verbatim. Export never returns credentials | OAuth and calendar tokens are plaintext (R-017). Rotation is manual (`encrypt-user-secrets`). The key lives in the same `.env` as every other secret |
| B7 | Billing webhook | Stripe signature, dedupe by event id (`SET NX`), per-customer ordering, customer-scoped mutation (BILL-01, floor-1 pins) | Dedupe and ordering state lives in Redis with a TTL. Redis is ephemeral by policy, so a flush reopens replay and reordering for old events. Events in the same second are not ordered |
| B8 | Cost | Per-user quota, global daily ceilings and metering on upload, batch, retry, reclassify, merge, review-resolve, CourseOps, chat, Q&A, concepts and, since `421dfa9`, the instance-provider path of `POST /api/settings/test-ai` (QUOTA-01/COST-01, M32 G1). Every ADR 0003 request-time site's route checks the caller's quota before the spend and records against the caller (`test_floor3_request_time_ai_quota.py`) | Own-credential test-ai is rate limited (5/min) but not quota-checked, by design: it spends the user's money. Concepts records only a successful call; a failed provider call there is not metered |
| B9 | CI/CD → prod | Images by SHA from GHCR. `deploy.sh` refuses without the encryption key (exit 68) or without a good pre-migration dump (exit 67), and migrates in a one-off container before start (R-028). `dependency-audit` CI job (pip-audit on the lock, npm audit high/critical; allowlist empty) | The key check tests presence, not validity: a malformed or test key passes the guard, then crash-loops after migrating. `pip-audit` is installed unpinned in CI. The host's `deploy.sh` is a manually installed copy and can drift from the repo |

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
