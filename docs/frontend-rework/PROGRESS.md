# Frontend Rework — Stream Progress

Integration branch: `frontend-rework`. Streams merge here in dependency order; `main` gets one final merge after Stream F.

| Stream | Branch | Status | Merged | Notes |
|---|---|---|---|---|
| A — Design system, tokens, vitest | `fr/design-system` | ✅ done | be70598 | 14 commits, 52 vitest tests, color guard live |
| B — Error layer | `fr/error-layer` | ✅ done | merged | 53 tests (105 total); silent study-write drops eliminated |
| C — Shell, IA, ⌘K, Ask merge | `fr/shell-ia` | ✅ done | merged | new nav, ⌘K, /ask; no server-side QA history existed (migration N/A) |
| D1–D11 — Screen redesigns | `fr/screens-*` + `fr/features-frontend` | ✅ done | merged | all 5 screen branches + E-frontend merged; 380 frontend tests |
| E — Backend features (TDD) | `fr/features-backend` | ✅ done | b860a85 | +96 tests (1130 local), 7 endpoint groups, 4 migrations; container suite run pending |
| F — Hardening, E2E, final merge | `fr/hardening` | ✅ done | — | allowlist emptied + deleted, 10 new e2e specs (64 total: 59 pass / 5 data-skips), axe gate green both themes, bundle budget in CI, dark-theme cascade bug fixed, docs updated |

## Log

- 2026-07-04: Phases 0–3 gated and approved (recon → brief → prototypes → plan). Integration branch created; Streams A and E dispatched in parallel worktrees.
- 2026-07-05: Stream F complete. Token sweep finished (last 20 files migrated; color guard now fails on any raw palette class, allowlist deleted). New Playwright specs: analytics, knowledge, admin, palette, notifications, pipeline-console, errors, offline, course-management + axe a11y gate (6 pages × 2 themes, serious/critical = fail). Real bugs found and fixed by the gates: `.dark` token block lost the cascade to `:root` (dark mode never applied colors), WCAG AA contrast corrections (light muted/faint, sage/amber both themes, light red, dark peri), Ask session rail nested-interactive, sonner rich-colors palette. Bundle budget script wired into CI (pdf.js worker excluded, documented inline). Backend 1136 green in container; vitest 380; e2e 59 passed / 5 data-dependent skips.
