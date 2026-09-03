# StudyAIO Public Beta — Design

**Date:** 2026-09-03
**Status:** Approved (design), pending implementation plan
**Baseline commit:** `3bbe713` (PR #22, `feat/quota-metering-and-admin-guards`)

## Goal

Take StudyAIO off its LAN-only, Authelia-gated internal URL and run it as a
closed, invite-only public beta at `https://studyaio.aleksanlab.me` for roughly
10–30 invited testers, on a metered AI provider with a bounded bill.

Not a product launch. Billing stays off, everyone is on the free tier, and the
front door needs an invite code.

## Decisions

| Decision | Choice |
|---|---|
| Outcome | Public beta hosting (not an OSS release — the repo is already public) |
| Where it runs | Stays on homelab VM 210 (192.168.1.169), exposed via the Helsinki VPS |
| Public hostname | `studyaio.aleksanlab.me` (existing Cloudflare zone) |
| AI backend | Z.ai / GLM (`glm-5.3-flash`) with quotas and a global ceiling |
| Audience | Closed invite-only, `REGISTRATION_MODE=invite` |
| Outbound email | Resend free tier, SPF/DKIM on `aleksanlab.me` (Brevo is a drop-in substitute — both are plain SMTP to this app) |
| Approach | Fix metering and lockouts *before* exposing, not after |

## Already in place

Verified against `3bbe713`. None of this is in scope; it is recorded so the
implementation plan does not redo it.

**Quota and metering (PR #22).** `free_max_*`, `pro_max_*`,
`global_max_ai_calls_per_day` and `global_max_ai_tokens_per_day` are settings in
`config.py:124-135`, where `0` means unlimited. Pipeline stages meter their AI
calls: adapters accumulate a `TokenUsage`, `record_agent_usage()` persists it and
resets the adapter, so `usage_records.ai_tokens_input/output` are finally
written. `free_max_ai_calls_per_day` is 100, not 20, because one upload costs
roughly four pipeline calls. The global ceiling is checked at the top of
`check_upload_quota` and `check_ai_quota`, applies to `pro` accounts and in
self-hosted mode because it guards spend rather than gating a plan, and returns
429 with `Retry-After` set to the next UTC midnight. Uploads reserve the whole
pipeline run up front, so a run is never admitted that cannot finish inside the
user's quota. Today's spend and the configured ceiling appear on
`GET /api/admin/metrics`. The unused duplicate quota path in `app/core/quota.py`
was removed.

**Beta readiness (PR #20).** Invite-gated registration with `invite_codes` and
`invite_service` (`SELECT … FOR UPDATE` on redemption, identical error for
unknown/spent/expired codes, redeemed before the user is created). Account
deletion and data export, where every table must be classified as user-scoped or
global or the build fails. Sentry on API, worker and frontend, inert without a
DSN, with a `before_send` scrubber that strips credential headers, cookies and
`?token=` from URLs. Email verification with resend. Preflight errors on
unconfigured SMTP in SaaS mode.

**Admin surface (PR #21, #22).** User provisioning (`POST /api/admin/users`
returns a single-use set-password link in the response body), admin-initiated
password reset (`POST /api/admin/users/{id}/password-reset`, link also in the
response body), invite CRUD at `/api/admin/invites`, and last-admin guards so
demoting, deactivating or deleting the final admin returns 400.

**Documentation.** `docs/deployment.md` has a *Running a Closed Beta* section
covering multi-user mode, SMTP, registration gating, the bill-bounding maths and
Sentry.

## Scope

Five workstreams. The first three are code and docs in this repo; the last two
are configuration and homelab infrastructure.

They cross three trees, which the implementation plan must keep distinct because
only the first is under CI:

- **`study-helper-project`** (this repo) — §1, §2, §3. Ships through the normal
  PR and deploy pipeline.
- **`homelab-runbook`** — the PVE Caddyfile in `inventory/caddy/`, plus session
  notes and the host entry for VM 210.
- **Untracked on `finland-vpn-1`** — `/opt/caddy/Caddyfile` on the VPS is not in
  version control. Its edit must be recorded in the runbook session notes, since
  nothing else will capture it.

### 1. First-admin bootstrap (the only real code gap)

Four facts compose into a dead end:

- `require_role("admin")` depends on `get_current_user`, not
  `get_current_user_or_default` (`deps.py:169`). Admin routes need a real JWT
  even in self-hosted mode.
- `_get_or_create_default_user` creates the default admin row with no
  `password_hash` (`deps.py:108-116`), email `admin@studyaio.local`, tier `pro`.
- There is no management command and no environment bootstrap — no `cli.py` or
  `manage.py`, no `ADMIN_PASSWORD`-style setting.
- `UserUpdateRequest` carries `role`, `tier` and `is_active` only
  (`admin.py:49`), so the unroutable `admin@studyaio.local` cannot be repointed
  through the API. Login is by email (`auth.py:170`).

Consequences: today no invite code can be minted, because every route that mints
one needs a credential that cannot be obtained. And the moment `SELF_HOSTED=false`
removes the default-identity fallback, the account that owns all existing lecture
data becomes unreachable — no password, and an undeliverable address so
self-service reset cannot help.

`docs/deployment.md` step 3 already instructs the operator to use *Admin → Invite
codes* and *Admin → Users → Add user*, without saying how to authenticate.

**Design.** An idempotent management command, invoked as
`docker compose exec api python -m app.cli ensure-admin --email <addr> [--username <name>]`:

- Targets the existing `DEFAULT_ADMIN_ID` row when it exists, so current lecture
  data keeps its owner and no data migration is needed. Otherwise it creates an
  admin.
- Sets a routable email, ensures `role=admin` and `is_active=true`.
- Mints a single-use set-password link and prints it to stdout. It must not
  depend on SMTP — this command is the path used *before* mail works.
- Reuses `admin_service.create_user` and `user_service.deliver_password_reset`
  rather than reimplementing token minting, so the link is the same shape and
  hashing as every other `MagicLink`.
- Re-running it is safe: it does not reset an existing password, it issues a new
  link. Enumerable state only, no destructive branch.
- Does not print or log the password, and the link is a bearer credential, so it
  goes to stdout only — never to the structured logger, matching the SaaS-mode
  rule in `user_service.py`.

Companion change: add `email` to `UserUpdateRequest` so an operator can fix an
address through the admin UI later, with the same uniqueness validation
registration uses. This is small and closes the "unroutable address" half of the
trap permanently.

**Tier note.** The default admin row is `tier="pro"`. That is correct for the
operator, and the global ceiling covers `pro`, so no change is needed.

### 2. Preflight gaps

`scripts/preflight-check.sh` covers JWT secret, DB password, CORS, registration
mode, SMTP, `COOKIE_SECURE`, OpenAPI and the data directory. Two additions in the
same style, both specific to this beta:

- **AI provider credentials.** Nothing validates `AGENT_BACKEND` against the key
  it needs. `AGENT_BACKEND=zai` with an empty `ZAI_API_KEY` passes preflight and
  then fails every pipeline run — the failure surfaces as broken uploads, far
  from its cause. Error when the selected backend's credential is missing
  (`zai` → `ZAI_API_KEY`, `openai` → `OPENAI_API_KEY`, `anthropic_api` →
  `ANTHROPIC_API_KEY`). `claude_code` and `ollama` need no key.
- **No spend ceiling in SaaS mode.** `global_max_ai_calls_per_day` defaults to
  `0`, which means unlimited. Warn when both global ceilings are `0` and
  `SELF_HOSTED=false`, because the whole point of the ceiling is that the
  operator's bill has an upper bound that does not scale with tester count.

A warning, not an error, for the second: a deliberate unlimited beta is a valid
choice, and preflight's existing convention is that errors are for
configurations that silently break rather than ones that merely cost money.

### 3. Documentation corrections

`docs/deployment.md`, *Running a Closed Beta*:

- Step 4 says the free tier is capped in `app/services/quota_service.py` at "1
  course, 5 uploads/month and 20 AI calls/day" and to "raise the constants".
  They are settings now, and the AI-call default is 100. Rewrite against the
  `FREE_MAX_*` / `PRO_MAX_*` environment variables.
- Step 4 recommends giving testers `tier=pro`. `pro` still short-circuits every
  per-user check; with `PRO_MAX_*` available the correct advice is to raise
  limits, and to keep beta testers on `free` so per-user quotas stay meaningful.
- Step 5 frames the provider choice as `claude_code` or `anthropic_api`. Add
  Z.ai as the recommended beta backend and note that testers can supply their
  own provider credentials in Settings → AI Providers as an alternative cost
  model.
- Add the first-admin bootstrap command as the new step 0, since steps 3 and 4
  depend on an admin credential.

### 4. Configuration on VM 210

Secrets go through Infisical (project `studyaio`,
`infisical-compose-studyaio.service`), not a hand-edited `.env`.

| Setting | Value | Why |
|---|---|---|
| `SELF_HOSTED` | `false` | Real accounts; removes the shared default identity |
| `REGISTRATION_MODE` | `invite` | Closed beta |
| `APP_BASE_URL` | `https://studyaio.aleksanlab.me` | Reset and verification links are built from it |
| `CORS_ORIGINS` | `https://studyaio.aleksanlab.me` | Drop localhost |
| `OAUTH_REDIRECT_BASE_URL` | `https://studyaio.aleksanlab.me` | Google/GitHub callbacks |
| `COOKIE_SECURE` | `true` | HTTPS only |
| `OPENAPI_ENABLED` | `false` | Stop publishing the API surface |
| `JWT_SECRET_KEY` | fresh 64-byte urlsafe | The app refuses to boot on the default in SaaS mode (`main.py:127-131`) |
| `POSTGRES_PASSWORD` | non-default | Currently the literal `studyaio` |
| `AGENT_BACKEND` | `zai` | Metered, per-token cost |
| `ZAI_MODEL` | `glm-5.3-flash` | Cheapest adequate tier |
| `ZAI_API_KEY` | set | Preflight will enforce this after §2 |
| `SMTP_*` | Resend | Mandatory in SaaS mode |
| `SENTRY_DSN`, `VITE_SENTRY_DSN` | set | `VITE_*` is inlined at build time, so it is a `deploy.yml` secret, not a runtime one |
| `MAX_UPLOAD_SIZE_MB` | `50` | See below |
| `FREE_MAX_COURSES` | `10` | Defaults are paywall-shaped: 1 course |
| `FREE_MAX_UPLOADS_PER_MONTH` | `60` | Default 5 is one sitting |
| `FREE_MAX_AI_CALLS_PER_DAY` | `200` | Default 100 is ~25 uploads/day |
| `GLOBAL_MAX_AI_CALLS_PER_DAY` | `300` interim | Defaults to `0` = unlimited. Retune after Verification step 3 |
| `GLOBAL_MAX_AI_TOKENS_PER_DAY` | set after Verification step 3 | The real cost driver on a per-token provider; cannot be guessed before one run is measured |

`MAX_UPLOAD_SIZE_MB` drops from 100 to 50 because Cloudflare's free plan caps
request bodies at 100MB. At exactly 100 a large lecture PDF fails as an opaque
Cloudflare 413 that the app never sees and cannot explain; at 50 the app rejects
it with its own error message.

Per-user quota values are a starting point, tunable by environment without a
deploy — that is what PR #22 bought. The global ceilings should be set from a
measured cost per upload on GLM (see Verification step 3), not guessed.

The three per-user limits are deliberately not balanced against each other: at
~4 pipeline calls per upload, 200 calls/day would allow ~50 uploads in one day,
so the 60/month cap is what actually binds a tester's pipeline usage. The daily
call limit exists to bound *chat and Q&A*, which no upload cap touches.

**Gate:** `make preflight` exits 0 before the hostname resolves publicly.

### 5. Edge and infrastructure

**PVE Caddy** (`inventory/caddy/Caddyfile`) — a new top-level
`studyaio.{$DOMAIN}` block beside `immich` and `jellyfin`:

- `crowdsec` for brute-force cover on `/api/auth/login`, which is rate limited at
  5/minute in the app but benefits from an IP-level layer.
- **No Authelia.** The app owns its authentication, and Authelia's forward-auth
  would consume the app's own `Authorization` header — the documented cause of a
  blank SPA and a browser credential prompt.
- `flush_interval -1` on the `/api` proxy. `chat.py`, `uploads.py`,
  `courseops.py` and `exports.py` all stream, and buffering breaks chat token
  streaming and pipeline progress. Both hops need it, matching the Jellyfin
  pattern.
- Its own `log` block. The global `log` directive does not produce per-request
  access lines for a site, so without one this host is invisible in exactly the
  situation where it matters.

The existing `studyaio.home.{$DOMAIN}` block stays as-is, behind Authelia, for
LAN administration.

**VPS Caddy** (`/opt/caddy/Caddyfile` on `finland-vpn-1`, not tracked in
`homelab-runbook`) — a new site proxying to `192.168.1.200:443` over Tailscale
via the PVE subnet router, with `flush_interval -1` and
`header_down -Server -x-response-time-ms`, matching `jellyfin.aleksanlab.me`.

**Cloudflare** — proxied DNS record for `studyaio`. SPF/DKIM records for the
chosen mail provider in the same zone.

**VM 210 firewall** — no change. Public traffic still arrives from `.200`, which
is already permitted for TCP 3001 and 8000.

**Backups** — VM 210 is in `backup-all-pbs`, so the whole VM is covered, but that
is a crash-consistent snapshot of a running Postgres and PBS lives on the same
chassis as the data it protects. Add a nightly `pg_dump` inside VM 210, mirroring
`immich-pg-dump.sh`, so recovering from a corrupt database does not require a
whole-VM restore. The single-chassis limitation is a known, accepted homelab
constraint and is not addressed here.

**Monitoring** — an Uptime Kuma monitor on the public URL, and alerts on pipeline
failure rate and on daily AI spend approaching the ceiling. Alert severity
follows the existing routing split: use `critical` for anything that must not be
missed, since `warning` routes only through n8n.

## Verification

Ordered, because some steps gate others.

1. **First admin.** Run the bootstrap command on VM 210 while still
   `SELF_HOSTED=true`. Follow the printed link, set a password, log in, load
   `/api/admin/metrics`. This must pass before anything else — it is the
   credential every later step needs.
2. **Preflight.** `make preflight` exits 0 against the real beta `.env`.
   Separately confirm it *fails* with `ZAI_API_KEY` blanked, so the new check is
   proven to bite rather than assumed to.
3. **A real lecture through the full pipeline on GLM-flash.** The highest-risk
   step. The prompts were tuned for Claude, and while BR.1 made
   `tests/golden/test_summary_structure.py` derive its required section list from
   `prompts/summarize.txt`, golden tests run against a fixture, not a live model
   — a model swap can produce structurally different summaries with the whole
   suite green. Upload a real multi-week PDF, read the generated summary against
   the prompt's eight required sections, and check classification, flashcards and
   quiz output by eye. Record the metered token cost from
   `/api/admin/metrics`; that number is what sets the global ceilings in §4.
4. **Registration gate.** Sign-up without a code is rejected; with a valid code
   it succeeds; the same code a second time is rejected.
5. **Email round trip.** A verification email actually arrives at an external
   inbox, and a password reset completes end to end. "SMTP configured" is not
   evidence — delivery is, and an undeliverable reset is exactly the failure that
   locks a tester out.
6. **Streaming through both hops.** Chat tokens arrive incrementally and pipeline
   progress updates live, over `https://studyaio.aleksanlab.me`, not just
   against the container.
7. **Cookies on the real domain.** Log in, refresh, and confirm the session
   survives; then confirm a password change ends the session deliberately with
   the `session_ended` handoff rather than an unexplained 401.
8. **Ceiling behaviour.** With the ceiling temporarily set low, an upload returns
   429 with a `Retry-After`, and an already-running pipeline still finishes.

## Rollback

`REGISTRATION_MODE=closed` stops new accounts immediately without touching the
edge. Full rollback removes the two Caddy site blocks and the Cloudflare record;
the internal `studyaio.home.*` host is untouched throughout, so LAN access never
depends on any of this. Reverting `SELF_HOSTED` to `true` restores the
default-identity fallback, which is why §1 sets a password on the existing
default-admin row rather than moving data to a new account.

## Out of scope

Stripe and billing (no tester pays). Open registration and the abuse defenses it
would need. A dedicated product domain. Network isolation or a VLAN for VM 210 —
worth doing before open signup, not before 30 invited people. AWS or any move off
VM 210. An OSS release: the repo is already public, but it has no LICENSE, no
tags and no releases, and that is a separate piece of work.

## Risks

| Risk | Mitigation |
|---|---|
| GLM output breaks the summary structure the UI and golden fixture expect | Verification step 3 is a live end-to-end read-through, before any invite goes out |
| Cost overshoot from in-flight pipelines | Ceiling bounds admission, not running work; overshoot is bounded by worker concurrency (4) rather than by the cap. Set ceilings with that headroom in mind |
| Strangers' traffic now reaches a VM inside the LAN | Accepted for a closed beta of known testers. VM 210's firewall already admits only `.200` and `.161`. Revisit before open signup |
| Verification mail landing in spam locks testers out | A real provider with SPF/DKIM on the zone, plus verification step 5 against an external inbox |
| Beta users' data has one real backup, on the same chassis | Nightly `pg_dump` added; single-chassis limitation accepted and stated to testers |
