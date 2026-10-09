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
