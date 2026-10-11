# Decisions

Durable decisions, newest last. Anything with a real trade-off gets an ADR in `docs/adr/`; this file
is the index plus the small rulings that do not warrant one.

## ADR index

| ADR | Title | Status |
|---|---|---|
| [0001](adr/0001-adopt-agentic-kit.md) | Adopt the agentic-kit orchestrator model | Accepted |
| [0002](adr/0002-module-boundaries.md) | Module boundaries of the modular monolith | Accepted |
| [0003](adr/0003-floor3-request-time-ai-calls.md) | Floor 3 admits an enumerated set of request-time AI calls | Accepted |
| [0004](adr/0004-floor4-user-initiated-item-deletes.md) | Floor 4 admits explicit user-initiated deletes of the user's own items | Accepted |
| [0005](adr/0005-floor3-embedding-gateway.md) | Floor 3 covers embeddings through a second gateway, `get_embedding_provider` (amends 0003) | Accepted |
| [0006](adr/0006-clock-policy.md) | Clock policy: user-local "today" for the study surface, UTC for quota and money | Accepted |

## Rulings

| Date | Ruling | By | Follow-up |
|---|---|---|---|
| 2026-10-04 | R-007 re-summarize: **fix the code** — prior summary versions (row + blob) must be retained; floor 4 stands | user | `data` + `ai` task |
| 2026-10-04 | R-007 asset regeneration: **fix the code** — regeneration must preserve flashcard reviews and quiz attempts; floor 4 stands | user | `data` + `ai` task |
| 2026-10-04 | R-007 single-item deletes: **amend floor 4** — an explicit user-initiated delete of the user's own item (course, course document, deadline, chat session, merge-discard) is permitted alongside account deletion | user | `architect` ADR 0004 |
| 2026-10-04 | R-007 leaderboard: **fix the code** — leaderboard is opt-in, hidden by default; floor 1 stands | user | `data` + `backend` + `frontend` task |
| 2026-10-04 | R-004 embeddings: **in scope of floor 3** — `EmbeddingProvider` is a second sanctioned gateway with its own enumerated allowlist | user | `architect` amends ADR 0003; `safety` pins |
| 2026-10-04 | Merge `keep_source`: **keep as a version** — the overwritten target summary is snapshotted into `summary_versions`; it is not merge-discard (ADR 0004 amended on acceptance) | user | `backend` M31-S2-BACKEND-019; `safety` pins |
| 2026-10-08 | C5 / R-020 purge design: **deleted-course ledger** — `delete_course` writes a zero-byte marker `ledger/deleted-courses/<user_id>/<course_id>`; account purge sweeps `summaries/<course_id>` for live and marked courses, then the ledger. No blob delete outside account deletion; no layout migration. (User first chose a per-user key prefix, then kept the ledger once it existed and passed the C5 pin.) Courses deleted before the fix stay unattributable | user | `architect` fills ADR 0004 § Correction; `safety` reviews |
| 2026-10-08 | C6 / R-021 scope: **services required, pipeline classified** — `user_id` required and the filter unconditional in `app/services/**`; the 11 pipeline-stage functions are classified by `safety` with reasons (owner comes from the artifact row) | user | `backend` M32-S1-BACKEND-006; `safety` classifies |
| 2026-10-09 | GL#10 part 3, chat "create a test" intent: **link to the quiz generator** — chat detects the intent and returns an action that opens Study Hub's quiz/exam builder with course + week preselected; no quiz is generated in chat, no new AI call site | user | `backend` M32-S1-BACKEND-019; `frontend` renders the button |
| 2026-10-09 | ADR 0002 (module boundaries) **accepted** as revised in M32-S1-ARCH-007; entry points assigned (R-003 closed); R-002 exceptions scheduled as fixes | user | `architect` flips Status; `backend` + `ai` R-002 tasks |
| 2026-10-09 | R-023 clock policy: **per-user time zone** for user-facing "today" (streaks, study history, daily challenge, due-today, exam countdown, per-user analytics, reminder/digest send time at user's 08:00); **UTC** for daily AI quota, billing, admin/platform stats; stored timestamps stay UTC. Zone stored in `user_settings.timezone` (IANA, default `UTC`), auto-detected from the browser, user-editable | user | `architect` ADR 0006 + contract test; `data`, `backend`, `frontend`, `ai`; `safety` review |
| 2026-10-10 | GL#8 / R-025: the worker's Claude CLI login comes from a **dedicated service-login directory** on the host (holds only that login), mounted read-only — never the operator's personal `~/.claude` | user | `devops` compose + runbook; user does the one-time `claude login` on the server |
| 2026-10-10 | R-026: the worker's Claude service login uses a **long-lived token** (`claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`) stored as a 0600 file in the dedicated login dir, passed only to the CLI subprocess — no OAuth refresh needed. MR to main: **send everything together** after the prod login dir is set up | user | `ai` adapter, `devops` setup/docs, `safety` review |
| 2026-10-10 | Prod runs `AGENT_BACKEND=zai`, so the instance needs **no Claude service token**: `/opt/studyaio/claude-login` holds only `{}` placeholders. The long-lived-token path (R-026) stays available if prod ever switches to `claude_code` | user | none |
| 2026-10-10 | **M32 direction = the founder audit** (`docs/audits/2026-10-10-product-audit.md`): S1 + quick wins first (wave 1), then remaining S2, then debt; new-feature work paused until wave 1 closes. Open user decisions: PROD-08 free-tier limits (blocks QUOTA-01 enforcement); which §5 strategic bet to pursue | user | Orchestrator dispatches wave 1 |
| 2026-10-10 | **Audit split across milestones:** M32 "Safe to grow" = all S1 + S2 in security/money/data integrity + cheap S2/S3 quick wins (wave 1 + wave 2, §11); M33 "Trust and retention" = AI quality, usage/onboarding, compliance, debt, plus one strategic bet chosen at the M32 gate. Gate criteria per milestone in §11 | user | Orchestrator dispatches M32 wave 1 |
| 2026-10-10 | PROD-08: **beta users get Pro** (existing invited users granted Pro); free-tier limits then enforced for new signups by QUOTA-01 | user | `backend` M32-S4-BACKEND-009 |
| 2026-10-10 | PROD-03 backfill: **existing users who never changed their notification preferences** get the new opt-out defaults (email reminders, deadline, weekly digest, day-2 nudge); anyone who changed a preference is left as is | user | `data` migration |
| 2026-10-10 | Prod `/opt/studyaio/data` set to `750` (`chmod o-rwx`) so the Claude CLI's uid 10001 can't read tenants' files; app uid 999 and root unaffected (verified) | user | none |
| 2026-10-11 | M32 gate **CONDITIONAL accepted**; G1–G3 closed after the gate (MR !37), G4 (first scheduled backup) carried into M33 as M33-S1-OPS-004 | user | none |
| 2026-10-11 | Leak sweep of tracked files: deployment-specific details removed from comments and docs; the public mirror stays public; the push mirror is paused until the user re-enables it; **no git-history rewrite** (history holds no live secret, and mirror PR refs and clones would keep it anyway) | user | none |
| 2026-10-11 | Unused unrestricted CI deploy key removed from the prod host's `authorized_keys` (backup kept); only the command-restricted deploy key remains; verified by a successful redeploy. Deleting the old CI secrets on the mirror host is a user action | user | none |
| 2026-10-11 | M33 strategic bet: **weak-spot engine** (audit §5, MKT-03) on top of the AI-trust baseline; shared course spaces deferred (tenancy redesign) | user | `architect` M33-S2-ARCH-018 |
| 2026-10-11 | **History rewritten** (supersedes "no rewrite" above): deployment-specific details removed from all history and commit messages, author emails normalised, two rollout runbooks and old course summaries dropped; GitLab force-pushed (all branches, protection restored); the public mirror updated in place (stale branches deleted, PR descriptions edited) — no repo deletion. Every commit SHA changed: SHAs quoted in earlier plan/gate entries refer to the old history. Remaining: a GitHub Support purge request for three old PR diffs | user | none |
