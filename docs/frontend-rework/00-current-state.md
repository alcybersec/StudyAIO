# Frontend Rework — Phase 0: Current State Report

> Recon date: 2026-07-04. Read-only audit of `services/ui/` (React 19, TypeScript, Vite 7, Tailwind v4, React Query, React Router 7, Radix UI, Motion). No code was modified.

---

## 1. Architecture Overview

### Routing & pages

- **21 pages, all lazy-loaded** via `React.lazy()` + `Suspense` in `src/router.tsx` (119 lines). Clean guard structure: `PublicOnlyRoute` (4 auth pages) and `ProtectedRoute` (17 app pages) wrapped in `AppLayout`.
- **Provider tree:** `QueryClientProvider` → `RouterProvider` → `RootLayout` (`AuthProvider` → `QuotaProvider`) → route guards → layouts.
- **Deep-linking** via query params is used widely but inconsistently: `?tab=`/`?exam=` (StudyHub), `?session=` (Chat), `?artifact=`/`?page=` (WeekView), `?token=` (reset), `?error=` (OAuth). Each page reimplements its own `useSearchParams` sync logic — no shared hook, no param validation (`?page=abc` is unhandled).
- **Legacy redirects** still in the router: `/timed-study`, `/exams`, `/exams/:examId` (+ an `ExamRedirect` indirection component).
- **Page size outliers:** `SettingsPage.tsx` (456 lines — appearance, 4 AI backends, pipeline tuning, billing, notifications, calendar all in one file), `AdminUserDetailPage.tsx` (278), `WeekViewPage.tsx` (240, ~9 state variables for the split-panel viewer).

### Navigation shell

- **Desktop:** `Sidebar` (17 KB) — Main (Dashboard/Upload/Study/Chat), Tools (Q&A/Knowledge/Analytics/Review+badge), collapsible Courses section, footer (Admin/Settings/theme/user).
- **Mobile:** `MobileNav` — 5 bottom tabs (Home/Study/Upload/Chat/More) + "More" sheet (Knowledge, Q&A, Review, Analytics, Settings, Profile, Admin).
- **Gaps:** courses are not browsable on mobile (only via Dashboard cards or direct URL); `/courses/:code/ops` and `/admin/users/:id` are reachable only through in-page buttons; the `/chat` full-bleed layout is a hard-coded pathname check in `AppLayout.tsx:19`; sidebar collapse state is not persisted.

### Data layer

- **API client** (`src/api/client.ts`) is well-designed: typed `ApiError`, 401 auto-refresh with dedup, global 402 (quota) and 403 (demo) handlers, upload helpers. **Missing:** timeout/network-error handling, and no differentiation of 400/404/429/500 for user-facing messaging.
- **Endpoint coverage:** ~92 typed endpoints across 7 api modules vs ~111 backend endpoints (~83%). Zero `any` in the api layer; ~150 interfaces in `src/types/index.ts` (some loose `Record<string, unknown>` payloads).
- **React Query:** 50+ hooks in `useApi.ts`, hierarchical query keys, minimal global config (`staleTime: 30s, retry: 1`), no global error handling, no offline/reconnect integration, one optimistic update (settings).

---

## 2. Findings by Area

### 2.1 Error handling — the weakest layer ⚠️

This is the single biggest systemic gap and the direct target of the rework mandate.

| Finding | Evidence |
|---|---|
| Only **~15% of query-using components** (4/26) render an error state; 54% of pages do | e.g. `HistoryTab.tsx:5-8`, `StudySetup.tsx:14-20`, `ChatWindow.tsx` (messages query), `QuizTab.tsx`, `DeadlineTimeline.tsx` — all render nothing/stale on error |
| **Silent data loss in study flows** | `FlashcardsStudyTab.tsx:77`, `TimedStudyTab.tsx:122,140,176` — `recordSession`/`recordReview`/`quizAttempt` wrapped in `.catch(() => {})`; a finished study session can vanish with no feedback |
| **AnalyticsPage & CourseOpsPage have effectively no error handling** | `AnalyticsPage.tsx:7-23` delegates to 4 chart components with undefined failure behavior; `CourseOpsPage.tsx:26-56` children fail silently |
| One global `ErrorBoundary` only | Catches render crashes app-wide; no route-level boundaries, so a failed lazy chunk load nukes the whole shell (`router.tsx:35-40`) |
| Toasts (sonner) configured but **not used for errors** | Only PWA update notifications use toasts; error UX is a mix of `ErrorBanner`, `EmptyState`, inline red text, or nothing |
| SSE weaknesses | `usePipelineEvents.ts:31` — EventSource error just sets `connected=false`, no reconnect, no user notification; `useStreamingChat` has no reconnection for dropped streams |
| No HTTP status differentiation | 400 validation vs 404 vs 429 rate-limit vs 500 all surface as generic `ApiError` |

### 2.2 Design system & theming

- **Token architecture is good** — Tailwind v4 `@theme` bound to `--theme-*` CSS custom properties in `index.css`, light/dark palettes (indigo primary), Inter type. Confirmed no `tailwind.config.js`.
- **But it's undermined by ~200+ hardcoded color violations** (`bg-gray-*`, `text-gray-*`, raw red/green/amber/blue) that break dark-mode parity. Worst offenders: `QuizTab.tsx` (14+), `FlashcardsTab.tsx` (13), `FileViewer.tsx`/`FileViewerToolbar.tsx` (light-mode only), `RatingButtons.tsx` (hardcoded red/orange/green/blue), `ScopedQA.tsx`, `WeekRow.tsx`, `MFASetup.tsx`, even core primitives (`Skeleton.tsx:15`, `Sheet.tsx:55`, `ErrorBanner.tsx`, `Badge.tsx` variants).
- **🐛 Confirmed dark-mode persistence bug:** the no-flash script in `index.html:18-26` reads `localStorage.getItem('theme')` but `useTheme.ts:5` stores under `'studyaio-theme'` → the stored preference is never applied pre-hydration; users with a non-system preference get a theme flash on every load.
- **Missing primitives:** no `Button` (~50+ repeated ad-hoc class strings, drifting variants), no `Input`, no `Select`, no `Table`, no `Tooltip`, no `Switch`, no `Dropdown` component. What exists: Card, Badge, Skeleton, EmptyState, ErrorBanner, LoadingSpinner, PageHeader, PageTransition, Sheet, StatusBadge, ThemeToggle, Toaster, AnimatedCard, Offline/ConnectionBanner.
- **Radix underused:** `react-dropdown-menu`, `react-switch`, `react-tooltip` are installed but never imported; only Dialog (5 files) and Tabs (2 pages) are used.
- **Motion:** used in only 4 places (AnimatedCard, PageTransition, Sheet, AppLayout) with per-component ad-hoc timing — no central animation vocabulary.
- **Icons:** all inline SVG, no library — duplicated markup, inconsistent sizing conventions.
- Spacing/radius/shadow conventions are actually fairly consistent (Tailwind scale, `rounded-lg/xl`, `shadow-sm`).

### 2.3 UX state coverage (loading / empty / error / offline)

Per-page audit summary (full table in recon; representative):

| Good coverage | Weak/missing |
|---|---|
| Dashboard, CoursePage, WeekView, ReviewInbox, Admin, AdminUserDetail, Achievements, QA | **Analytics** (no loading, no error), **CourseOps** (children silent-fail), Profile (ad-hoc), Login/Register (ad-hoc), ForgotPassword (silent errors) |

- **Skeletons exist but are barely used** — `Skeleton`/`SkeletonText`/`SkeletonCard` are defined, yet nearly every page shows a full-page `LoadingSpinner` or blank flash instead (Dashboard `:54`, WeekView `:86`, study tabs). Only AdminPage hand-rolls a pulse skeleton.
- **Offline/PWA:** the machinery is genuinely good (Workbox SW with NetworkFirst/SWR/CacheFirst tiers, IndexedDB mutation queue for reviews/quiz attempts, auto-replay on reconnect, `useOnlineStatus`, `usePendingSync`, `OfflineBanner`) — but the **UX is invisible**: no indication on forms that an action was queued, no replay progress, no success toast after sync, `ConnectionBanner` only on UploadPage, and React Query does not refetch on reconnect.

### 2.4 Accessibility

- **19 total `aria-*` attributes in the whole codebase.** No `aria-live` regions (errors/toasts/streaming text are not announced), no `aria-describedby` linking validation errors to inputs, breadcrumbs lack `aria-label="breadcrumb"`.
- **Focus visibility risk:** `focus:outline-none` appears ~45 times paired with `focus:ring-*`, but **zero** `focus-visible:` usage — keyboard focus can be invisible (worst: `StudyCard.tsx:15`).
- Radix components give free focus-trapping where used (dialogs OK), but the onboarding tour overlay is a raw clickable div with no keyboard path.
- D3 knowledge graph and dashboard drag-and-drop have **no keyboard alternative** at all.
- Form labels are actually good (57 `htmlFor` associations); touch targets meet 44px (56 `min-h-[44px]` uses); avatar `alt=""` questionable in 4 spots.
- Contrast risk: 274 uses of `text-text-muted` plus scattered `text-gray-400/500` — unverified against AA.
- `safe-area-pb` custom class on MobileNav (`:150`) — needs verification on notched iOS devices.

### 2.5 Forms

- Only **3 forms** use react-hook-form + zod (`DeadlineEditModal`, `CustomResolutionForm`, `ExamCreateForm`). Login, Register, Profile, Settings, Chat are hand-rolled `useState` forms with manual error strings, no field-level binding, no consistent validation display.

### 2.6 Performance

- **Build/bundle: solid.** All 21 pages lazy; smart `manualChunks` (vendor-react 92 KB, vendor-query 44 KB, vendor-ui 164 KB, vendor-viz 436 KB, vendor-pdf 416 KB, vendor-forms 88 KB; ~2.2 MB total dist). D3/Recharts/pdfjs correctly isolated; pdfjs worker bundled locally. nginx caching + SSE proxy config is correct.
- **Runtime: fair, with hot spots:**
  - `useStreamingChat.ts:59-60` — every SSE token triggers a state update that re-renders the **entire message list** (`ChatWindow.tsx:45-51`); **zero `React.memo` in the whole codebase**; no virtualization for long chats.
  - `ConceptGraph.tsx:193` — D3 force simulation fully rebuilds on any prop change including node selection (frame drops at 100+ nodes). Cleanup is correct.
  - `DashboardPage.tsx:61-86` — `widgetContent` object rebuilt every render; all 8 widgets re-render on any change; layout re-compaction not memoized.
  - `usePipelineEvents.ts:26` — event array grows unbounded during long uploads.
  - `RetentionCurve.tsx` — chart data not memoized (Heatmap/Mastery do it right).
- **Two small leaks:** `useTheme.ts:45` adds a module-level `matchMedia` listener with no removal; `PWAUpdateNotify.tsx:15-17` creates an uncleared `setInterval` (one per registration event).

### 2.7 Testing

- **Zero unit/component tests.** No vitest, no @testing-library. The only frontend safety net is **9 Playwright specs** (auth, dashboard-shallow, chat-shallow, study, upload, course, search-qa, navigation, settings), Chromium-only.
- **Zero E2E coverage for:** Analytics, Knowledge Graph, Admin, offline queue/replay, PWA update flow, PDF viewer, flashcard SM-2 review flow, error states of any kind.
- TS config is maximally strict (good); ESLint is defaults-only.

---

## 3. Top Problems (ranked)

1. **Error handling is systemically absent** — 85% of query components have no error state; study flows silently discard user progress (`.catch(() => {})`); no error toasts; no route-level boundaries; no HTTP status differentiation; no SSE reconnect. *This is the "add proper error handling" mandate in one line.*
2. **The design system exists in name only** — good tokens, but no Button/Input/Select/Table primitives, ~200+ hardcoded colors breaking dark mode across Quiz/Flashcards/Viewer/QA, and a real dark-mode persistence bug (`theme` vs `studyaio-theme` key mismatch).
3. **Loading UX is spinner-or-blank** — skeletons exist but are unused; every page transition flashes.
4. **Accessibility is far from WCAG 2.1 AA** — 19 aria attributes total, zero `focus-visible`, no live regions, no keyboard path for graph/DnD, unverified contrast.
5. **Offline capability is invisible to users** — a genuinely good SW/queue implementation with no surfaced UX (no "queued", no sync progress/confirmation, banner on one page only).
6. **No component test safety net** — a full UI rework with 0 unit tests and 9 shallow E2E specs is flying blind; test infrastructure must land early.
7. **Streaming and heavy visualizations have avoidable render cost** — per-token full list re-render, zero `React.memo`, D3 re-simulation on selection, dashboard-wide widget re-renders.
8. **Oversized/duplicated page logic** — 456-line SettingsPage, 240-line WeekViewPage with ~9 viewer state vars, tab/URL-param sync reimplemented per page.
9. **Navigation gaps** — courses unreachable from mobile nav, orphaned pages (CourseOps, AdminUserDetail), hard-coded full-bleed check, legacy redirect routes.
10. **Forms are inconsistent** — RHF+zod on 3 forms, hand-rolled everywhere else including all auth forms.

## 4. Opportunities

- **Primitive layer first:** Button/Input/Select/Table/Tooltip/Switch built on the already-installed Radix packages + existing tokens would mechanically fix most visual inconsistency and much of the dark-mode drift, and gives the rework a foundation to build screens on.
- **One error-handling layer:** typed error taxonomy in the client (network/validation/not-found/rate-limit/server) → shared `QueryBoundary`/error-state component + error toasts + route-level boundaries + mutation-failure recovery (retry queue for study records). Fixes problem #1 wholesale rather than page-by-page.
- **Skeleton-per-screen pattern** as part of each redesigned page (the component already exists).
- **Surface the offline story:** queued-action chips, sync progress toast, global connection banner, React Query `onlineManager` wiring — high perceived-quality win for low effort since the SW layer already works.
- **A11y systematically:** `focus-visible` utility sweep, `aria-live` for toasts/streaming/errors, keyboard path + list-view parity for graph, labeled breadcrumbs — most of it is mechanical once patterns are set.
- **Cheap perf wins:** `React.memo` on ChatMessage/StreamingMessage, buffered token flushes (or `useDeferredValue`), memoized dashboard widget map, D3 selection updates without re-simulation, two leak fixes.
- **Test infrastructure early:** vitest + @testing-library as part of the design-system stream, so every new primitive/screen lands tested; extend Playwright to the uncovered features and to error/offline states.
- **IA cleanup as part of redesign:** settings sub-routes, shared `useTabRouting` hook, mobile course navigation, explicit layout variants (full-bleed as a route handle, not a pathname check).
- **Quick bug fixes to bank regardless of rework scope:** theme localStorage key mismatch, `useTheme` listener leak, `PWAUpdateNotify` interval leak.

---

## 5. Inputs to Phase 1 (brainstorm)

Open questions this report raises for the design brainstorm:

1. Visual identity: keep the indigo/Inter look and tighten it, or take a new direction? (Tokens make either cheap.)
2. Error UX philosophy: toasts vs inline vs boundary pages — where does each apply?
3. IA: does the Sidebar's Main/Tools split still fit a ~20-page app, or is a re-grouping (Learn / Library / Insights / System) warranted? What about mobile course browsing?
4. Which half-built surfaces deserve investment vs pruning (e.g. legacy redirects, QA page vs Chat overlap)?
5. Scope of new functionality (command palette? global search? notification center? richer pipeline visualization?) — to be surfaced as options during brainstorm.
