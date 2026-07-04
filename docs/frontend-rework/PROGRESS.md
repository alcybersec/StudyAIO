# Frontend Rework — Stream Progress

Integration branch: `frontend-rework`. Streams merge here in dependency order; `main` gets one final merge after Stream F.

| Stream | Branch | Status | Merged | Notes |
|---|---|---|---|---|
| A — Design system, tokens, vitest | `fr/design-system` | 🟡 in progress | — | critical path |
| B — Error layer | `fr/error-layer` | ⬜ pending A | — | |
| C — Shell, IA, ⌘K, Ask merge | `fr/shell-ia` | 🟡 in progress | — | QA-history migration N/A (see log) |
| D1–D11 — Screen redesigns | `fr/screens-*` | ⬜ pending A+B+C | — | D2←E3, D3←E6, D4←E7, D8←E5 |
| E — Backend features (TDD) | `fr/features-backend` | 🟡 in progress | — | E1–E7 |
| F — Hardening, E2E, final merge | `fr/hardening` | ⬜ pending all | — | |

## Log

- 2026-07-04: Phases 0–3 gated and approved (recon → brief → prototypes → plan). Integration branch created; Streams A and E dispatched in parallel worktrees.
- 2026-07-04 (Stream C, task C5): **QA-history migration is not applicable.** Investigated `services/app` for a server-side QA history store: none exists. `POST /api/qa/ask` (`app/api/qa.py`) is stateless — it persists nothing but a best-effort UsageRecord, and no model in `app/models/` stores QA exchanges. The QA page's "history" is transient React component state (`useState<QAExchange[]>` in `QAPage.tsx`/`ScopedQA.tsx`, not even localStorage), so there is no data to migrate into chat sessions. `/ask` runs entirely on the existing `chat_sessions`/`chat_messages` tables — no Alembic data migration needed. The planned `migrate_qa_history_to_sessions` service + data migration were skipped for this reason.
