# StudyAIO Frontend Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Backend tasks additionally REQUIRE superpowers:test-driven-development (RED → GREEN → REFACTOR — no backend code without a failing test first).

**Goal:** Implement the approved rework (see `01-design-brief.md`, prototypes in `design/prototypes/`) — dark-anchored Nordic Calm design system, new IA + ⌘K, systemic error handling, redesigned screens, 7 new features — with the suite green at every merge.

**Architecture:** Six work-streams, each in its own git worktree/branch, integrating into a long-lived `frontend-rework` integration branch via PRs in dependency order; `main` receives one final reviewed merge after E2E. The approved prototype code (`design/prototypes/src/`) is the visual/code reference — primitives and screens are *ported* into `services/ui` and wired to the real typed API client, not reinvented.

**Tech Stack:** Existing stack (React 19, TS, Vite 7, Tailwind v4, Radix, Motion, React Query, RHF+zod) + `lucide-react` (only new runtime dep) + dev-only: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`.

---

## 0. Ground rules (apply to every stream)

- **Branching:** integration branch `frontend-rework` created from `main`. Each stream: worktree + branch `fr/<stream>` off `frontend-rework`. PRs target `frontend-rework`, never `main`. No commit mentions Claude/AI tooling; no Co-Authored-By.
- **Backend changes:** strict TDD in `services/app` — write failing pytest first, run it, watch it fail, implement minimally, pass, refactor. Run `pytest tests/unit -x` per change; full backend suite before the stream's PR.
- **Frontend tests:** every new primitive/hook/state component gets vitest tests in the same PR. `npm run test` (vitest) + `npm run lint` + `npm run build` must pass before every merge.
- **Color discipline:** after Stream A lands, CI greps forbid raw palette classes in `services/ui/src` (see A9). Migrated files must use tokens only.
- **Reference paths:** prototype sources under `design/prototypes/src/` — `styles/tokens.css`, `ui/index.tsx`, `screens/*.tsx`. Port, adapt to real data, keep the look.

### Dependency graph & merge order

```
A (design system, tokens, vitest)        ← first, blocks everything
├── B (error layer)                       ← needs A's ErrorState/Skeleton
├── C (shell, IA, ⌘K, Ask merge)          ← needs A; B merges before C only if both touch AppLayout (C rebases)
├── E-backend (all new endpoints, TDD)    ← independent of A; can start day 1 in parallel
D1..D11 (screens)                         ← need A+B+C merged; parallel per screen group
E-frontend (palette search, inbox, etc.)  ← need C + matching E-backend endpoint
F (E2E, CI budgets, final hardening)      ← last, on integration branch
```

**Merge order into `frontend-rework`:** A → B → C → (D groups and E in any order as ready) → F → single PR `frontend-rework` → `main`.

### Worktree setup (per stream)

```bash
git worktree add ../studyaio-fr-<stream> -b fr/<stream> frontend-rework
# work, commit, push, PR → frontend-rework
git worktree remove ../studyaio-fr-<stream>   # after merge
```

---

## Stream A — Design system, tokens, test infrastructure

**Worktree:** `fr/design-system` · **Blocks:** everything · **Est:** the largest single stream, fully sequential-safe

**Files:**
- Create: `services/ui/vitest.config.ts`, `services/ui/src/test/setup.ts`
- Create: `services/ui/src/components/ui/{Button,Input,Textarea,Select,Switch,Tooltip,Dropdown,Modal,Table,ErrorState,Kbd}.tsx` (+ `.test.tsx` each)
- Modify: `services/ui/src/index.css` (token layer), `services/ui/index.html` (theme key bug), `services/ui/src/hooks/useTheme.ts` (leak), `services/ui/src/components/pwa/PWAUpdateNotify.tsx` (leak), `services/ui/src/components/ui/{Skeleton,EmptyState,Badge,Card}.tsx` (tokenize), `services/ui/src/components/ui/index.ts` (exports), `services/ui/package.json`
- Modify: `.github/workflows/*` frontend job (add vitest + color-guard step)

### Task A1: vitest infrastructure
- [ ] Add dev deps: `npm i -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom`
- [ ] Create `vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', globals: true, include: ['src/**/*.test.{ts,tsx}'] },
})
```
- [ ] Create `src/test/setup.ts` with `import '@testing-library/jest-dom'`
- [ ] Add script `"test": "vitest run"`, smoke test `src/test/smoke.test.ts` (`expect(1+1).toBe(2)`), run `npm run test` → PASS, commit `test: add vitest infrastructure`

### Task A2: token layer
- [ ] Port `design/prototypes/src/styles/tokens.css` into `services/ui/src/index.css`: replace the current `@theme`/`--theme-*` block with the new `@theme inline` + `--t-*` sets (dark anchor + light twin), keep `@plugin "@tailwindcss/typography"`, keep existing custom classes (flip animation, safe-area, grid overrides)
- [ ] **Compatibility shim** so unmigrated files keep rendering during D-streams: map legacy names to new tokens in the same `@theme` block:
```css
  --color-primary: var(--t-peri);
  --color-primary-dark: var(--t-peri);
  --color-primary-light: var(--t-peri-soft);
  --color-success: var(--t-sage);
  --color-warning: var(--t-amber);
  --color-danger: var(--t-red);
  --color-surface: var(--t-surface-1);
  --color-surface-alt: var(--t-surface-0);
  --color-border: var(--t-border);
  --color-text: var(--t-text);
  --color-text-muted: var(--t-text-muted);
```
- [ ] Add `kbd`, `:focus-visible`, scrollbar, `::selection`, reduced-motion base rules from the prototype tokens.css
- [ ] `npm run build` passes; visually smoke both themes on / and /study; commit `feat: dark-anchored token layer with legacy shim`

### Task A3: theme bugs (the three from recon)
- [ ] `index.html` no-flash script: `localStorage.getItem('theme')` → `'studyaio-theme'`
- [ ] `useTheme.ts`: move the `matchMedia('(prefers-color-scheme: dark)')` listener into the store subscribe path with matching `removeEventListener` on unsubscribe; write `useTheme.test.ts` asserting subscribe/unsubscribe symmetry (spy on add/removeEventListener)
- [ ] `PWAUpdateNotify.tsx`: keep interval id, `clearInterval` on unmount / re-register
- [ ] Tests + lint pass; commit `fix: theme persistence key, media-listener and update-interval leaks`

### Task A4: Button + Kbd (pattern-setter for all primitives)
- [ ] Write failing `Button.test.tsx`: renders each variant/size; `loading` disables + shows spinner; keyboard focus shows focus-visible ring class; `kbd` prop renders `<kbd>`
- [ ] Port Button from `design/prototypes/src/ui/index.tsx`, plus `Kbd.tsx` (extract prototype `<kbd>` styling into component for JSX use)
- [ ] Tests pass; export from `ui/index.ts`; commit `feat: Button and Kbd primitives`

### Task A5: form primitives — Input, Textarea, Select, Switch
- [ ] Failing tests first per component. Non-negotiable assertions: label association via `htmlFor`; error sets `aria-invalid` + `aria-describedby` pointing at a `role="alert"` node; Select = Radix DropdownMenu-based listbox with keyboard nav (arrow + enter selects, test with user-event); Switch = `@radix-ui/react-switch` styled with tokens
- [ ] Implement (Input/Textarea port from prototype; Select/Switch new, same visual language)
- [ ] Commit per component: `feat: <name> primitive`

### Task A6: overlay primitives — Tooltip, Dropdown, Modal
- [ ] Tooltip: `@radix-ui/react-tooltip` wrapper, delay 300ms, token styling; test: appears on focus (a11y), not only hover
- [ ] Dropdown: `@radix-ui/react-dropdown-menu` wrapper matching the CoursePage manage-menu look (`design/prototypes/src/screens/CoursePage.tsx` ManageMenu); test keyboard nav + escape
- [ ] Modal: `@radix-ui/react-dialog` wrapper (replaces per-feature hand-rolled dialogs incrementally); test focus trap + escape + `aria-labelledby`
- [ ] Commit per component

### Task A7: Table + state components
- [ ] `Table.tsx`: thead mono-uppercase style + dense rows per prototype CoursePage table; plain composition (`Table`, `THead`, `TRow`, `TCell`), test renders + `overflow-x-auto` wrapper
- [ ] `ErrorState.tsx`: port from prototype (role="alert", Retry callback, collapsible details); test: retry fires, details toggle
- [ ] Retokenize existing `Skeleton.tsx` (drop `bg-gray-200 dark:bg-gray-700` → `bg-surface-2`) and `EmptyState`, `Badge` (variants → sage/amber/red/peri/muted tones), `Card`
- [ ] Commit `feat: Table, ErrorState; retokenize state primitives`

### Task A8: lucide-react + icon sweep of shared chrome
- [ ] `npm i lucide-react`; replace inline SVGs in `ui/` components + `PageHeader` only (layout/nav SVGs replaced in Stream C, feature files in D)
- [ ] Commit `feat: adopt lucide-react in shared primitives`

### Task A9: color-guard CI check
- [ ] Add `services/ui/scripts/check-colors.sh`:
```bash
#!/usr/bin/env bash
# Files migrated to the token system must not reintroduce raw palette classes.
PATTERN='(bg|text|border)-(gray|slate|zinc|red|green|blue|amber|orange|pink|purple|indigo|emerald|teal)-[0-9]'
ALLOWLIST='services/ui/scripts/color-allowlist.txt'   # shrinks as D-streams migrate files
violations=$(grep -rnE "$PATTERN" services/ui/src --include='*.tsx' --include='*.ts' | grep -vFf "$ALLOWLIST" || true)
if [ -n "$violations" ]; then echo "$violations"; echo 'Raw palette classes found — use tokens.'; exit 1; fi
```
- [ ] Seed `color-allowlist.txt` with `grep -rlE "$PATTERN" services/ui/src` output (every currently-violating file); wire into CI frontend job + `npm run lint` composite; commit `ci: color token guard with shrinking allowlist`

### Task A10: stream PR
- [ ] Full check: `npm run lint && npm run test && npm run build`; Playwright smoke locally (`auth.spec.ts`, `navigation.spec.ts` — old UI must still work on the shim)
- [ ] PR `fr/design-system` → `frontend-rework`

---

## Stream B — Error-handling layer

**Worktree:** `fr/error-layer` · **Needs:** A merged · **Parallel with:** C (coordinate on AppLayout — B owns banner/toast slots, C owns nav)

**Files:**
- Modify: `services/ui/src/api/client.ts` (+ `client.test.ts`)
- Create: `services/ui/src/api/errors.ts`, `services/ui/src/components/RouteErrorBoundary.tsx`, `services/ui/src/lib/writeQueue.ts` (+ tests), `services/ui/src/components/ui/{ConnectionStatus,SyncChip}.tsx`, `services/ui/src/lib/toast.ts`
- Modify: `services/ui/src/router.tsx` (errorElement per route), `services/ui/src/sw.ts` (queue on 5xx), `services/ui/src/hooks/{useStreamingChat,usePipelineEvents}.ts`, `services/ui/src/App.tsx` (onlineManager), `services/ui/src/components/layout/AppLayout.tsx` (banner slot)

### Task B1: typed error taxonomy
- [ ] Failing `client.test.ts` (msw-free — mock `fetch`): 400 with `{detail: {field: msg}}` → `ValidationError.fields`; 404 → `NotFoundError`; 429 with `Retry-After: 42` → `RateLimitError.retryAfterSeconds === 42`; 500 → `ServerError`; fetch rejection → `NetworkError`; 30s timeout via `AbortSignal.timeout` → `NetworkError`
- [ ] `errors.ts`:
```ts
export class AppApiError extends Error { constructor(msg: string, public status: number, public detail?: unknown) { super(msg) } }
export class NetworkError extends AppApiError {}
export class ValidationError extends AppApiError { fields: Record<string, string> = {} }
export class NotFoundError extends AppApiError {}
export class RateLimitError extends AppApiError { retryAfterSeconds = 30 }
export class ServerError extends AppApiError {}
export function classifyResponse(status: number, body: unknown): AppApiError { /* per tests */ }
```
- [ ] Wire into `client.ts` (existing 401-refresh / 402 / 403 handlers unchanged, classified errors thrown for the rest); tests pass; commit `feat: typed API error taxonomy`

### Task B2: route-level error boundaries
- [ ] `RouteErrorBoundary.tsx`: uses `useRouteError`; chunk-load errors (`error.name === 'ChunkLoadError' || /Loading chunk/i`) render "New version available — reload" + reload button; other errors render full-page ErrorState with retry (`navigate(0)`)
- [ ] `router.tsx`: add `errorElement: <RouteErrorBoundary />` on the layout routes and each lazy route
- [ ] Test: throwing lazy component renders boundary, shell nav still visible; commit `feat: route-level error boundaries`

### Task B3: never-lose-study-data write queue
- [ ] Failing `writeQueue.test.ts`: `enqueue(req)` persists (fake-indexeddb via simple in-memory adapter injected for tests); `flush()` retries FIFO, removes on 2xx, keeps on 5xx/network, drops with warning on 4xx (bad request won't ever succeed); `size()` reactive via subscribe
- [ ] `writeQueue.ts`: shared client-side queue reusing the SW's `studyaio-offline` DB, exponential backoff (1s→2s→4s… cap 60s), flush on `online` + on interval while non-empty
- [ ] Patch study mutation call-sites (`FlashcardsStudyTab.tsx:77`, `TimedStudyTab.tsx:122,140,176`, exam session recording): replace `.catch(() => {})` with `.catch(e => writeQueue.enqueue(...))`
- [ ] `SyncChip.tsx` (port from prototype `shared.tsx`) subscribed to `size()`, rendered in AppLayout header region + StudyHub
- [ ] `sw.ts`: extend queue predicate to also queue on response.status >= 500 for the two study POST routes
- [ ] Commit `feat: persistent retry queue for study writes`

### Task B4: connectivity + React Query wiring
- [ ] `App.tsx`: `onlineManager.setEventListener` (browser online/offline), QueryClient defaults: `retry: (count, err) => !(err instanceof ValidationError || err instanceof NotFoundError) && count < 2`, `refetchOnReconnect: 'always'`
- [ ] `ConnectionStatus.tsx` global banner (port OfflineBanner; states offline / reconnecting / flushed-toast) mounted in AppLayout above content on every page
- [ ] Commit `feat: global connectivity status + reconnect refetch`

### Task B5: toasts + SSE resilience
- [ ] `lib/toast.ts`: `toastMutationError(err, retryFn)` — maps taxonomy → message (RateLimit shows countdown), sonner action button "Retry"; unit test the mapping function
- [ ] `useStreamingChat.ts`: on stream drop → state `interrupted`, auto-retry ×3 with backoff resuming from last message id; expose `resume()`; UI per prototype Ask offline state
- [ ] `usePipelineEvents.ts`: cap events at 200 (`slice(-200)`), reconnect with backoff on error, expose `connectionState`
- [ ] Commit `feat: mutation error toasts and SSE resume`

### Task B6: stream PR
- [ ] `npm run lint && npm run test && npm run build` + backend suite untouched (`pytest` in services/app to be safe); PR → `frontend-rework`

---

## Stream C — Shell, IA, ⌘K, Ask merge

**Worktree:** `fr/shell-ia` · **Needs:** A merged (B preferred first; rebase over it)

**Files:**
- Rewrite: `services/ui/src/components/layout/{Sidebar,MobileNav,AppLayout}.tsx`
- Create: `services/ui/src/components/CommandPalette.tsx` (+test), `services/ui/src/hooks/useTabRouting.ts` (+test), `services/ui/src/hooks/useShortcuts.ts` (+test), `services/ui/src/components/ShortcutOverlay.tsx`, `services/ui/src/pages/AskPage.tsx`
- Modify: `services/ui/src/router.tsx` (groups, /ask, /qa redirect, settings sub-routes, full-bleed handle, drop legacy redirects), delete `services/ui/src/pages/QAPage.tsx` after merge
- **Backend (TDD):** QA-history → chat-sessions migration

### Task C1: `useTabRouting` hook
- [ ] Failing test: syncs `?tab=` param; invalid value falls back to default; extra params preserved; back/forward works (memory router)
```ts
export function useTabRouting<T extends string>(tabs: readonly T[], defaultTab: T, param = 'tab'): [T, (t: T) => void]
```
- [ ] Implement over `useSearchParams` with validation; commit `feat: useTabRouting hook`

### Task C2: sidebar + mobile nav (port ShellNav prototype)
- [ ] Port `design/prototypes/src/screens/ShellNav.tsx` structures into real `Sidebar.tsx` / `MobileNav.tsx`: Home / Learn(Study, Ask, Knowledge) / Library(Courses expandable, Upload, Review+badge) / Insights(Analytics, Achievements); footer Settings/Admin/theme/user; bell button (opens placeholder panel until E2); persist collapse state in localStorage; mobile Library sheet with course list
- [ ] Vitest: nav renders all groups; review badge shows count; admin item only for role=admin
- [ ] Commit `feat: activity-group navigation shell`

### Task C3: routing changes
- [ ] `router.tsx`: full-bleed via `handle: { fullBleed: true }` + `useMatches()` in AppLayout (kill pathname check); settings sub-routes `/settings/:section?`; remove `/timed-study`, `/exams`, `/exams/:examId` redirects + `ExamRedirect`; `/qa` → `/ask` redirect
- [ ] Update `e2e/navigation.spec.ts` + `study.spec.ts` expectations; commit `refactor: route table for new IA`

### Task C4: ⌘K command palette
- [ ] `CommandPalette.tsx` per prototype (custom on Radix Dialog — no cmdk dep): sections Actions (static registry) / navigation (courses from cache) / content (wired to E1 endpoint when it lands — until then, hidden section behind `searchAvailable` flag)
- [ ] `useShortcuts.ts`: global keymap (⌘K, S, U, ?, g-h/g-s sequences), input-focus guard; ShortcutOverlay per StatesGallery prototype
- [ ] Tests: opens on ⌘K, arrows navigate, enter fires action, ? opens overlay, typing in an input never triggers single-key shortcuts
- [ ] Commit `feat: command palette and global shortcuts`

### Task C5 (backend, TDD): QA history migration
- [ ] RED — `services/app/tests/unit/services/test_chat_migration.py`:
```python
async def test_migrate_qa_history_creates_sessions(db_session, make_user):
    user = await make_user()
    db_session.add(QAHistory(user_id=user.id, question="What is ASLR?", answer="...", course_code="CSIT302"))
    await db_session.flush()
    created = await migrate_qa_history_to_sessions(db_session, user.id)
    assert created == 1
    sessions = (await db_session.execute(select(ChatSession).where(ChatSession.user_id == user.id))).scalars().all()
    assert sessions[0].title == "What is ASLR?"
    msgs = (await db_session.execute(select(ChatMessage).where(ChatMessage.session_id == sessions[0].id))).scalars().all()
    assert [m.role for m in msgs] == ["user", "assistant"]

async def test_migrate_qa_history_idempotent(db_session, make_user): ...  # second run creates 0
```
- [ ] GREEN — `chat_service.migrate_qa_history_to_sessions()` (marks migrated rows; idempotent), invoked from an Alembic data migration
- [ ] Full backend suite green; commit `feat: migrate QA history into chat sessions`

### Task C6: AskPage
- [ ] Port prototype `Ask.tsx` layout onto existing ChatPage logic: session rail, scope chips (course/week filter params passed to existing chat endpoint's RAG scope — extend request schema only if already supported by backend; if not supported, backend TDD task: add optional `course_code`/`week` to chat message endpoint + retrieval filter, test: scoped question retrieves only scoped chunks), streaming per B5, composer with Badge chips
- [ ] Delete QAPage + its nav entry; migrate `ScopedQA` in WeekView to point at Ask with prefilled scope
- [ ] E2E: update `search-qa.spec.ts` → `ask.spec.ts`
- [ ] Commit `feat: merged Ask surface`; stream PR → `frontend-rework`

---

## Stream D — Screen redesigns (parallel groups after A+B+C)

Each group = one worktree, one PR. Per screen: port prototype look → wire real hooks → four states (Skeleton mirror / EmptyState / ErrorState / offline) → remove file from color-allowlist → vitest for logic (state selection, memoization) → E2E touch-up.

**D1 `fr/screens-home` — Home.** Port prototype Home widget styling onto DashboardPage; extract each widget to `components/dashboard/widgets/<Name>.tsx` with `React.memo` + per-widget query state; `widgetContent` map memoized (`useMemo` on data slices); grid layout logic unchanged. Vitest: a widget with erroring query renders ErrorState while sibling renders data (mock two hooks).
**D2 `fr/screens-study` — Study Hub.** Plan tab (prototype StudyHub) consuming E3 endpoint (until merged: tab hidden behind `planAvailable` from a `HEAD /api/study/plan` probe); tokenized RatingButtons/StudyCard/QuizTab/FlashcardsTab (removes worst hardcode offenders); keyboard hints via Kbd; history as Table primitive.
**D3 `fr/screens-week` — Week view + reclassify.** Extract `FileViewerContainer` (viewer state consolidated to `{artifactId, page, zoom, open}` reducer); dark PDF chrome per prototype; ReclassifyPanel per prototype wired to E6 endpoint; tabs via `useTabRouting`.
**D4 `fr/screens-course` — Course page + management.** Port prototype CoursePage: week Table, Manage Dropdown, DeleteConfirm Modal (type-to-confirm), Archive path; wired to E7 endpoints.
**D5 `fr/screens-upload` — Pipeline console.** Port prototype PipelineConsole: per-file stage rail component `PipelineStageRail.tsx` (+vitest for status mapping), stage timings from SSE payloads, retry-stage button → existing retry task endpoint (verify exists; if not, E-backend TDD task: `POST /api/artifacts/{id}/retry-stage` re-enqueues the failed Celery stage), bounded log via B5.
**D6 `fr/screens-review` — Review inbox.** Prototype ReviewInbox: dense rows, j/k/a/e/d via `useShortcuts` scoped registry, inline edit row with Select+Input, filters as pills.
**D7 `fr/screens-knowledge` — Knowledge.** Restyle canvas dark; refactor ConceptGraph: separate simulation effect (deps: nodes/edges only) from selection effect (deps: selectedId — updates attrs via D3 select, no re-simulation); list view keyboard parity (roving tabindex). Vitest: simulation factory called once across selection changes (spy).
**D8 `fr/screens-analytics` — Analytics + readiness.** Four states for every chart card; `useMemo` all chart data; readiness drill-down per prototype wired to E5.
**D9 `fr/screens-settings` — Settings split.** Sub-route sections per prototype (nav rail + `/settings/:section`); ALL forms → RHF+zod (`lib/schemas.ts` additions); per-field save feedback; provider cards.
**D10 `fr/screens-auth` — Auth.** Prototype Auth styling; RHF+zod; taxonomy-mapped errors (ValidationError→fields, 401→"wrong email or password", RateLimitError→countdown per prototype); OAuth buttons kept.
**D11 `fr/screens-misc` — Admin, Achievements, CourseOps.** Table primitive for admin/user tables; quiet achievements restyle; CourseOps children get four states (worst recon offender).

Each D-PR: lint+vitest+build+affected Playwright specs green; allowlist shrinks; PR → `frontend-rework`.

---

## Stream E — New features (backend TDD + frontend)

**Worktree:** `fr/features-backend` (one branch; endpoints are small and share test scaffolding) + frontend pieces landing inside the D-stream or follow-up PRs listed below. **Every task here: RED first.**

### E1: global search — `GET /api/search?q=&limit=`
- [ ] RED `tests/unit/services/test_search_service.py`:
```python
async def test_search_returns_grouped_matches(db_session, make_user, sample_course):
    # seed: course CSIT302, a summary containing "forensics", a flashcard front containing "forensics", a chat session titled "forensics intro"
    results = await search_all(db_session, user.id, "forensics", limit=10)
    kinds = {r.kind for r in results}
    assert kinds == {"course_week", "flashcard", "chat_session"}
    assert all(user.id == r.user_id for r in results)          # tenant isolation
async def test_search_escapes_like_wildcards(db_session, make_user): ...  # "%foo_" finds literal, no wildcard blowup
async def test_search_empty_query_returns_400(async_client, auth_cookies): ...
```
- [ ] GREEN: `search_service.search_all` — ILIKE over summaries.title/content-headline, flashcards.front, chat_sessions.title, courses.code/name (pg_trgm index migration: `CREATE INDEX ... USING gin (front gin_trgm_ops)` etc. — Alembic migration with manual op); router `api/search.py`; response schema `SearchResult{kind, title, snippet, href_meta}`
- [ ] Frontend: palette content section (C4 flag flips on), grouped results; E2E: palette search navigates to week

### E2: notification center — model + endpoints + emit points
- [ ] RED `tests/unit/models/test_notification.py` + `tests/unit/api/test_notifications_inbox.py`: model fields `(id, user_id, kind, title, body, href, read_at, created_at)`; `GET /api/notifications?unread=true` returns newest-first; `POST /api/notifications/mark-read {ids}` sets read_at idempotently; unread count endpoint
- [ ] RED emit tests: pipeline assets-stage completion creates `kind="pipeline"` notification (unit: mock session, assert row); review-item creation emits `kind="review"`; achievement unlock emits; deadline scan (existing beat task) emits ≤1 per deadline per day (idempotency test)
- [ ] GREEN: `models/notification.py` + migration; `notification_service.py` (`notify()` best-effort try/except like XP pattern); wire 4 emit points; `api/notifications_inbox.py`
- [ ] Frontend: bell panel per ShellNav prototype (poll unread count 60s, panel list, mark-read on open); vitest for unread-badge logic

### E3: weekly planner — `GET /api/study/plan`
- [ ] RED `tests/unit/api/test_study_plan.py`: given an exam in 9 days + readiness data, response = 7 day entries, each `{day, items: [{course_code, kind: "cards"|"quiz"|"mock", target, done}]}`; course with nearer exam gets higher weekly card total (assert relative ordering); no exams → 200 with `items: []` per day
- [ ] GREEN: `study_service.build_week_plan()` wrapping the existing schedule algorithm (priority multipliers already in `exam` weak-topic logic); `done` computed from study_sessions of current week
- [ ] Frontend: D2 Plan tab consumes it

### E4: quick capture — `POST /api/uploads/capture`
- [ ] RED `tests/unit/api/test_quick_capture.py`: `{text: "...", title?: str}` → 201 creates LectureArtifact (source_type="capture") + enqueues pipeline chain from classify stage (mock celery, assert task called with artifact id); `{url: "https://..."}` → fetches (mocked httpx) and stores as text artifact; oversized text (>1MB) → 413; both text and url → 422
- [ ] GREEN: endpoint writes text via `get_storage()`, reuses ingest service dedup (sha256 of text), quota-checked like uploads
- [ ] Frontend: palette "quick capture" action → small Modal (textarea/URL) → toast with pipeline link

### E5: readiness detail — `GET /api/exams/{id}/readiness`
- [ ] RED: response `{overall: int, topics: [{topic, week, accuracy, weight, card_count}]}` matching existing weak-topics math (fixture with known quiz/flashcard rows → assert exact numbers); 404 foreign exam (tenant isolation)
- [ ] GREEN: extract existing weak-topic scoring from exam service into `readiness_service.compute_readiness_detail()`; both callers share it (regression test pins the old overall number)
- [ ] Frontend: D8 drill-down table

### E6: reclassify — `POST /api/artifacts/{id}/reclassify`
- [ ] RED `tests/unit/api/test_reclassify.py`: `{course_code, week}` moves artifact + its chunks/flashcards/quiz to target (assert FKs updated); source week summary regenerated flag set (summarize task enqueued for BOTH affected weeks — mock celery, assert 2 calls); target week with existing summary → version increments, not duplicate (idempotency rule 6); 409 if artifact still processing
- [ ] GREEN: `artifact_service.reclassify()` transactional; reuses review-resolution move logic if present (check `review_service.resolve` first — extract shared helper, don't duplicate)
- [ ] Frontend: D3 ReclassifyPanel

### E7: course management — rename / archive / delete / merge
- [ ] RED `tests/unit/api/test_course_management.py`:
```python
async def test_rename_course_updates_code_and_children(...):    # PATCH /api/courses/{code} {new_code, name} — artifacts/summaries keep FK integrity
async def test_archive_course_hides_from_lists(...):            # POST /{code}/archive — archived not in GET /courses, still in ?include_archived=1
async def test_delete_course_requires_confirmation_token(...):  # DELETE /{code} without X-Confirm: <code> header → 428; with → cascades (assert counts 0), uploads remain in storage
async def test_merge_course_moves_weeks_and_renumbers_conflicts(...) # POST /{code}/merge {into} — colliding weeks get review items, not silent overwrite
async def test_course_management_tenant_isolation(...)          # other user's course → 404
```
- [ ] GREEN: `course_service.py` additions + `archived_at` column migration; DELETE respects "never delete data/ contents" by leaving storage blobs (purge is out of scope)
- [ ] Frontend: D4 wiring (type-to-confirm sends the header)

**Stream E PR(s):** backend suite fully green (`pytest`), then PR → `frontend-rework`; frontend consumers land in their D-streams.

---

## Stream F — E2E, CI, final hardening (last, on `frontend-rework`)

**Worktree:** `fr/hardening`

- [ ] **New Playwright specs:** `analytics.spec.ts` (loads, readiness drill-down rows, error state via route abort), `knowledge.spec.ts` (graph renders, list-view keyboard nav), `admin.spec.ts`, `palette.spec.ts` (⌘K nav + search), `notifications.spec.ts`, `pipeline-console.spec.ts` (stage rail, retry button), `offline.spec.ts` (context.setOffline → review a card → chip shows → online → chip clears), `errors.spec.ts` (route.fulfill 500 → ErrorState + retry recovers), `course-management.spec.ts` (delete confirm gating)
- [ ] **A11y pass:** `@axe-core/playwright` (dev-dep) smoke on 6 key pages, both themes — fail on serious/critical
- [ ] **Perf budgets in CI:** `scripts/check-bundle.sh` — fail if any dist chunk > 500KB; verify chunks unchanged shape
- [ ] **Color guard:** allowlist must now be empty — delete allowlist mechanism, plain grep fails on any hit
- [ ] **Full verification:** `make up` + migrations + full backend suite + vitest + `npx playwright test` against compose stack; light-mode visual sweep; mobile 375px sweep
- [ ] **Docs:** update `docs/PROGRESS.md`, `docs/frontend-rework/PROGRESS.md` (stream log), `docs/api.md` (7 new endpoint groups)
- [ ] **Final PR:** `frontend-rework` → `main` with summary of streams, test counts, budget report

---

## Testing & CI-green strategy (summary)

| Layer | Tooling | Gate |
|---|---|---|
| Backend new endpoints | pytest, TDD RED→GREEN | per-commit in E/C; full suite per PR |
| Frontend units | vitest + RTL (new in A1) | every primitive/hook/state PR |
| E2E | Playwright (existing 9 + ~9 new) | affected specs per D-PR; full suite in F |
| A11y | axe smoke (F) + component-level assertions (A5) | serious/critical = fail |
| Visual/theme | manual sweep at F + color-guard grep from A9 | CI |
| Bundle | check-bundle.sh (F) | CI |

`main` stays releasable throughout: nothing merges to `main` until F. The `frontend-rework` integration branch absorbs stream PRs in dependency order; every stream PR runs the full frontend checks + backend suite. The legacy-token shim (A2) keeps unmigrated screens rendering correctly mid-flight, so the integration branch is always a working app.

## Rollout / integration order (recap)

1. `fr/design-system` (A) — app looks retokened via shim, old screens intact
2. `fr/error-layer` (B) — invisible except better failures
3. `fr/shell-ia` (C) — new nav + /ask (biggest visible change before screens)
4. `fr/features-backend` (E) — endpoints live, unused until consumers land
5. `fr/screens-*` (D1–D11) — any order; D2 after E3, D3 after E6, D4 after E7, D8 after E5
6. `fr/hardening` (F) — then `frontend-rework` → `main`

Conflicts: streams touch disjoint files except `router.tsx` (C owns it; D-streams rebase), `AppLayout.tsx` (B then C; D never touches), `ui/index.ts` (append-only exports). Resolve by rebase onto latest `frontend-rework`, never by force-merge.
