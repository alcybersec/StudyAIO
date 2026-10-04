# Decisions

Durable decisions, newest last. Anything with a real trade-off gets an ADR in `docs/adr/`; this file
is the index plus the small rulings that do not warrant one.

## ADR index

| ADR | Title | Status |
|---|---|---|
| [0001](adr/0001-adopt-agentic-kit.md) | Adopt the agentic-kit orchestrator model | Accepted |
| [0002](adr/0002-module-boundaries.md) | Module boundaries of the modular monolith | Proposed |
| [0003](adr/0003-floor3-request-time-ai-calls.md) | Floor 3 admits an enumerated set of request-time AI calls | Accepted |

## Rulings

| Date | Ruling | By | Follow-up |
|---|---|---|---|
| 2026-10-04 | R-007 re-summarize: **fix the code** — prior summary versions (row + blob) must be retained; floor 4 stands | user | `data` + `ai` task |
| 2026-10-04 | R-007 asset regeneration: **fix the code** — regeneration must preserve flashcard reviews and quiz attempts; floor 4 stands | user | `data` + `ai` task |
| 2026-10-04 | R-007 single-item deletes: **amend floor 4** — an explicit user-initiated delete of the user's own item (course, course document, deadline, chat session, merge-discard) is permitted alongside account deletion | user | `architect` ADR 0004 |
| 2026-10-04 | R-007 leaderboard: **fix the code** — leaderboard is opt-in, hidden by default; floor 1 stands | user | `data` + `backend` + `frontend` task |
| 2026-10-04 | R-004 embeddings: **in scope of floor 3** — `EmbeddingProvider` is a second sanctioned gateway with its own enumerated allowlist | user | `architect` amends ADR 0003; `safety` pins |
