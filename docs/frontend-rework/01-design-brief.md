# Frontend Rework — Phase 1: Design Brief

> Agreed 2026-07-04 via brainstorm (one-question-at-a-time, visual companion mockups). Inputs: `00-current-state.md`. This brief is the contract for Phase 2 prototypes and the Phase 3 implementation plan.

## Decisions log

| # | Question | Decision |
|---|---|---|
| 1 | Primary audience | **Self-hosted-first** — power-tool ergonomics baseline; SaaS surfaces (billing, upgrade, demo) stay functional, polished second |
| 2 | Visual direction (12 options shown) | **J — Nordic Calm** (Notion/Things territory: warm greys, muted earth accents, airy, quiet typography) |
| 3 | Density & keyboard | **Calm chrome, dense content** + global ⌘K command palette + app-wide keyboard shortcuts |
| 4 | Information architecture (3 models shown) | **Activity groups**: Home · Learn · Library · Insights + footer |
| 5 | Chat vs Q&A | **Full merge** into one "Ask" surface; `/qa` redirects; QA history migrates to chat sessions |
| 6 | Home screen (3 hi-fi mockups shown) | **A — customizable widget grid kept** (react-grid-layout stays; fixed and polished) |
| 7 | New functionality | **7 of 8 accepted**: global search in ⌘K, notification center, live pipeline visualization, weekly planner, quick capture, shortcut overlay, readiness drill-down. Rejected: focus study mode |
| 8 | Error handling strategy | Approved as proposed (see §5) |
| 9 | Theme anchor | **Dark-anchored** — design dark first, derive light |
| 10 | Mobile priority | **Secondary but real** — touch-friendly, functional, desktop-optimized decisions, no swipe-gesture extras |
| 11 | Per-screen gripes | None — designer judgment from recon findings |
| 12 | Scope | **Everything in one mission** — all six work-streams land before the rework is done; priorities affect build order only |

---

## 1. Visual language — "Nordic Calm, dark-anchored"

- **Anchor:** dark mode is the primary design target. Warm-tinted charcoal (not blue-black): e.g. surfaces in the `#1c1b1a → #262524` family with warm grey text (`#e8e6e3` primary, `#a3a09b` muted). Light theme is the derived "paper" twin (`#f7f7f5 / #fdfdfc / #37352f` family, per the chosen mockups).
- **Accents (muted earth, both modes, contrast-checked):**
  - Sage green — primary actions, success (`#448361` light / lifted for dark)
  - Terracotta-amber — streaks, warnings (`#d9730d` / `#cb912f` family)
  - Muted red — danger, urgency (`#c4554d` family)
  - Dusty periwinkle — info, XP/level (`#6e79d6` family)
- **Typography:** Inter stays. Slightly tighter scale on data surfaces (tables, lists, inbox); comfortable scale on chrome and reading surfaces (summaries keep `prose`).
- **Density rule:** *quiet chrome, dense content* — sidebar/headers airy; tables, week lists, review inbox, admin, history compact and information-rich.
- **Motion vocabulary (shared constants, not per-component):** entry = fade + 8–12px rise, 150–300ms ease-out; sheets/dialogs = existing spring (damping 30 / stiffness 300); no decorative animation on data surfaces. Respect `prefers-reduced-motion`.
- **Token layer (Tailwind v4 `@theme` + `--theme-*`):** expand to surface levels (0/1/2), border/border-strong, text/text-muted/text-faint, 4 status colors + soft variants, accent set. **All ~200 hardcoded color usages migrate to tokens** (worst: QuizTab, FlashcardsTab, FileViewer*, RatingButtons, ScopedQA, Skeleton, Sheet, ErrorBanner, Badge).
- **Bugs fixed in this stream:** `index.html` no-flash script reads `theme` but `useTheme` stores `studyaio-theme` (key unified); `useTheme.ts:45` module-level matchMedia listener leak; `PWAUpdateNotify.tsx` uncleared `setInterval`.

## 2. Design system components

New primitives in `src/components/ui/`, built on already-installed Radix packages, dark-anchored, with vitest + Testing Library coverage from day one:

- **Button** — primary / secondary / ghost / danger × sm / md / lg; loading + disabled states; replaces ~50 ad-hoc class strings.
- **Input, Textarea, Select, Switch, Tooltip, DropdownMenu, Modal** (Radix Dialog/DropdownMenu/Switch/Tooltip finally used), **Table** (with dense variant).
- **Standardized state components:** Skeleton (used everywhere a spinner is today), EmptyState (actionable: icon, one-liner, CTA), ErrorState (plain-language message + Retry + collapsible details).
- **Forms:** react-hook-form + zod becomes the only form pattern — auth pages, profile, settings migrate; field errors linked via `aria-describedby`.
- **Icons:** adopt **lucide-react** (only new dependency; tree-shakeable) replacing hand-pasted inline SVGs; consistent sizing scale.

## 3. Information architecture & shell

**Sidebar (desktop):**

```
Home
LEARN     Study · Ask · Knowledge
LIBRARY   Courses (expandable) · Upload · Review inbox [badge]
INSIGHTS  Analytics · Achievements
footer    Settings · Admin (role-gated) · theme · user card
```

- **⌘K command palette:** navigation, actions (start study session, upload, new chat, toggle theme…), and global search (see §6). Keyboard shortcuts app-wide; `?` opens the shortcut overlay.
- **Mobile:** bottom nav mirrors the groups (Home · Study · Ask · Library · More); Library/More sheets include a **browsable course list** (fixes the mobile course gap).
- **Ask merge:** ChatPage absorbs QA. Scope chips (course/week) on the composer; one-shot question = single-message session; `/qa` → `/ask` redirect; QA history migrated into sessions. Route renamed `/ask`.
- **Settings** splits into sub-sections (tabbed sub-routes): Appearance, AI Providers, Pipeline, Notifications, Calendar, Billing, Account & Security.
- **Shell mechanics:** full-bleed becomes a route `handle` (no pathname checks); shared `useTabRouting(tabs, defaultTab)` hook with param validation replaces the three hand-rolled implementations; legacy `/timed-study`, `/exams`, `/exams/:id` redirects removed; sidebar collapse state persisted.
- Orphan fixes: CourseOps reachable from course page **and** ⌘K; admin user detail breadcrumbed.

## 4. UX state standard (every screen, no exceptions)

Each screen/component that fetches data defines all four:

1. **Loading** — skeleton mirroring final layout (no full-page spinners, no blank flashes).
2. **Empty** — actionable EmptyState (what this is + how to get content into it).
3. **Error** — ErrorState with Retry, in place of the content region.
4. **Offline** — what still works (cached data marked as such), what queues, what disables.

## 5. Error handling architecture (approved as proposed)

- **Query failures:** inline ErrorState in the content region; route-level error boundaries (each lazy route wrapped) so a crash or failed chunk load never takes the shell down; global boundary remains as last resort.
- **Mutation failures:** toast with Retry action.
- **Study-progress writes are never lost:** reviews / quiz attempts / session records go through a persistent retry queue — the existing IndexedDB offline queue extended to also capture **server-error** failures (not just offline). UI shows a small "N unsaved · syncing" chip until flushed; success toast on recovery. All `.catch(() => {})` silent drops are eliminated.
- **Connectivity:** one global banner (offline / reconnecting / back online + queued count) rendered in the shell, all pages. React Query wired to `onlineManager` for refetch-on-reconnect.
- **Streaming (Ask + pipeline SSE):** interruption shows inline "connection lost — resuming…" at the stream location; auto-retry with backoff; manual resume button after retries exhausted.
- **HTTP taxonomy in the client:** 400 → zod-mapped field errors; 404 → contextual not-found (entity-aware, not generic); 429 → "try again in Xs" with countdown; 5xx → ErrorState/toast with retry; 402/403 keep existing quota/demo modals; network/timeout distinguished from server errors.
- **Tone:** plain language, never raw error strings; full detail behind a "details" expander (power-user friendly).

## 6. Screen treatments

| Screen | Treatment |
|---|---|
| **Home** | Widget grid **kept** (user choice). Per-widget skeleton/error states, memoized widget map (no grid-wide re-renders), layout persistence kept, restyled dark-Nordic. |
| **Study Hub** | Gains a **Plan** tab (weekly planner, §7) ahead of the existing four (Flashcards / Timed / Exams / History). Rating buttons + cards tokenized (currently hardcoded colors), visible keyboard hints on controls, denser history table, session summary restyled. |
| **Week view** | Split panel refactored into `FileViewerContainer` (collapses the ~9 viewer state vars); dark PDF chrome; params via `useTabRouting`; mobile keeps sheet viewer. |
| **Upload → pipeline console** | Per-file live stage graph (ingest→classify→extract→summarize→index→assets) driven by existing SSE events; per-stage timing; **retry failed stage** from UI; bounded event log (fixes unbounded array); quick-capture entry point. |
| **Review inbox** | Dense triage list; keyboard flow (j/k navigate, a approve, d dismiss, e edit); resolved/dismissed as filters, not page reloads. |
| **Ask (merged)** | Session rail + streaming window; `React.memo` on messages, buffered token flush (~30ms frames); scope chips; stream-resume UX per §5. |
| **Knowledge graph** | Dark canvas; selection updates without re-running the force simulation; list view becomes keyboard/screen-reader twin with parity of actions. |
| **Analytics** | Real loading/empty/error states; memoized chart data; **readiness drill-down**: per-topic breakdown of exam readiness with "study these now" links. |
| **Achievements** | Functionally kept, restyled quieter (Nordic, less confetti-energy). |
| **Settings** | Split per §3; all forms RHF+zod; per-field save feedback. |
| **Auth pages** | Restyled to match; RHF+zod; error mapping (wrong password vs rate-limited vs server); OAuth buttons kept. |
| **Admin** | Dense Table primitive; kept functionally; error/loading states. |

## 7. New features (all in scope)

| Feature | Description | Backend work (TDD, Phase 3 flags) |
|---|---|---|
| **Global search (⌘K)** | Search courses, weeks, summaries, flashcards, chat sessions from the palette; grouped results; enter → navigate | **New**: unified search endpoint (likely `GET /api/search?q=` over pg trgm/tsvector; embedding search optional later) |
| **Notification center** | Bell in the sidebar header (desktop) / More sheet (mobile) opening an inbox panel: pipeline finished, review item created, achievement unlocked, deadline approaching; unread badge; mark-read | **New**: notification model + list/mark-read endpoints + emit points in pipeline/review/gamification/deadline services |
| **Live pipeline viz** | Part of Upload console (§6) | None (SSE events exist) |
| **Weekly planner** | "This week" view (Study Hub → Plan tab): per-course card targets, scheduled from exam dates + readiness (existing schedule algorithm) | Minor: expose schedule output as endpoint if not already |
| **Quick capture** | Paste text/URL into ⌘K → creates mini-artifact, runs pipeline | **New**: ingest-from-text/URL endpoint feeding existing pipeline |
| **Shortcut overlay** | `?` shows per-page + global shortcuts | None (frontend registry) |
| **Readiness drill-down** | Click readiness % → topic-level breakdown + study links | Possibly minor: readiness-detail endpoint (weak-topics logic exists) |

## 8. Accessibility (WCAG 2.1 AA target)

- `focus-visible:` sweep replacing bare `focus:outline-none` (visible focus everywhere, no rings on mouse click).
- `aria-live` regions: toasts, streaming answer, sync chip, form-level errors; `role="alert"` on ErrorState.
- Form errors bound with `aria-describedby`; breadcrumbs get `aria-label="breadcrumb"`; avatar alts fixed.
- Keyboard parity for every interactive surface — graph via its list twin; widget grid arrangement gets a non-drag fallback (hide/show + move controls in customizer).
- Token palette contrast-checked ≥ AA in **both** modes (automated check in CI).
- Touch targets stay ≥ 44px; `safe-area-*` verified.

## 9. Performance budgets

- No route chunk > 500 KB (current worst: vendor-viz 436 KB — stays under, monitored in CI).
- Streaming chat smooth at 100+ messages (memo + buffered flush; virtualize only if measurement demands).
- Knowledge graph interactive at 200 nodes (no re-simulation on selection).
- No unbounded client arrays (pipeline events capped/rolled).
- Dashboard: single-widget data change re-renders only that widget.
- Leak fixes from §1; PWA/nginx/code-splitting posture already good — preserved, not regressed.

## 10. Testing strategy

- **vitest + @testing-library/react** introduced with the design-system stream: every primitive tested (variants, keyboard, aria), every state component (loading/empty/error), error-layer units (taxonomy mapping, retry queue), hooks (`useTabRouting`, streaming buffer).
- **Playwright** expands: Analytics, Knowledge graph, Admin, notification center, ⌘K palette/global search, pipeline console, and **error/offline scenarios** (route-level API failure → ErrorState + retry; offline study → queue chip → replay).
- **Backend TDD** for §7 endpoints: RED → GREEN → REFACTOR, per mission rules.
- Suite stays green throughout; CI unchanged in shape (lint, backend, integration, frontend) with frontend job gaining `vitest run`.

## 11. Work-streams (for Phase 3 planning)

1. **Design system & tokens** (incl. theme bug + leak fixes) — foundation, blocks everything.
2. **Error-handling layer** (taxonomy, boundaries, retry queue, connectivity) — depends on 1 (ErrorState).
3. **Nav shell & IA** (sidebar, ⌘K, mobile, routes, Ask merge) — depends on 1.
4. **Screen redesigns** (per §6) — depend on 1–3; parallelizable per screen group.
5. **New features** (per §7) — backend TDD + frontend; parallelizable.
6. **Test infrastructure** — starts with 1, runs throughout.

Scope decision: all six land before the rework is called done; ordering above is dependency order, not priority triage.

## Out of scope

- Focus/zen study mode (explicitly rejected).
- Framework/stack changes beyond lucide-react.
- Backend refactors not required by §7.
- Marketing-grade polish of SaaS surfaces (billing/upgrade/demo stay functional, restyled with the token pass only).
- Swipe gestures / mobile-specific interaction extras.
