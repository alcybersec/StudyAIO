# Frontend Rework — Stream Progress

Integration branch: `frontend-rework`. Streams merge here in dependency order; `main` gets one final merge after Stream F.

| Stream | Branch | Status | Merged | Notes |
|---|---|---|---|---|
| A — Design system, tokens, vitest | `fr/design-system` | 🟡 in progress | — | critical path |
| B — Error layer | `fr/error-layer` | ⬜ pending A | — | |
| C — Shell, IA, ⌘K, Ask merge | `fr/shell-ia` | ⬜ pending A | — | includes backend QA-history migration (TDD) |
| D1–D11 — Screen redesigns | `fr/screens-*` | ⬜ pending A+B+C | — | D2←E3, D3←E6, D4←E7, D8←E5 |
| E — Backend features (TDD) | `fr/features-backend` | 🟡 in progress | — | E1–E7 |
| F — Hardening, E2E, final merge | `fr/hardening` | ⬜ pending all | — | |

## Log

- 2026-07-04: Phases 0–3 gated and approved (recon → brief → prototypes → plan). Integration branch created; Streams A and E dispatched in parallel worktrees.
