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
| `SETTINGS_ENCRYPTION_KEY`, `JWT_SECRET_KEY`, DB password | env from the secret manager → `/opt/studyaio/.env` | Losing the key means losing every stored credential. Leaking the JWT key means session forgery (floor 1) |
| OAuth and calendar tokens | `oauth_accounts`, `calendar_syncs`, **plaintext** | R-017 residual. They are not AI credentials, so outside floor 2's literal text |
| Database dumps | `/opt/studyaio/backups` (predeploy + nightly), mode 2770 `alex`, ACL u:999 | They hold everything above except the env secrets. AI credentials in them are ciphertext |

## 2. Actors

- **Anonymous internet caller.** Reaches Caddy, then `ui` and `api`. On prod, registration is invite-only.
- **Authenticated user (tenant).** Can be malicious toward other tenants (floor 1) or toward the operator's budget.
- **Uploaded content.** This is attacker-controlled text that reaches the AI (prompt injection) and the parsers
  (PDF, DOCX and PPTX parsing in the root worker).
- **AI provider.** Its error text can echo credentials back (R-012). Its output is untrusted (citations, JSON).
- **Operator.** Trusted. Holds the env and the VM.
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
| B8 | Cost | Per-user quota, global daily ceilings and metering on upload, batch, retry, reclassify, merge, review-resolve, CourseOps, chat, Q&A and concepts (QUOTA-01/COST-01) | **`POST /api/settings/test-ai` spends instance AI with no quota, no ceiling, no metering and no rate limit** (M32 gate finding) |
| B9 | CI/CD → prod | Images by SHA from GHCR. `deploy.sh` refuses without the encryption key (exit 68) or without a good pre-migration dump (exit 67), and migrates in a one-off container before start (R-028). `dependency-audit` CI job (pip-audit on the lock, npm audit high/critical; allowlist empty) | The key check tests presence, not validity: a malformed or test key passes the guard, then crash-loops after migrating. `pip-audit` is installed unpinned in CI. The VM's `deploy.sh` is a manually installed copy and can drift from the repo |

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
7. **`deploy.sh` guards.** Both refusals fired on the first wave-2 deploy (jobs 4785 and 4793) and left the old
   stack untouched, then job 4794 deployed. Residuals are in B9.
