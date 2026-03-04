# StudyAIO v2 — Product Requirements Document

> **Version:** 2.0 | **Date:** 2026-03-03
> **Predecessor:** `docs/PRD.md` (v1, Milestones 1-12, 551 tests, COMPLETE)

---

## 1. Executive Summary

StudyAIO v2 transforms the application from a single-user local-first study workspace into a **hybrid SaaS + self-hosted multi-user platform** with accounts, billing, multi-AI provider support, notifications, gamification, and a polished PWA interface. The v1 foundation (6-stage pipeline, Q&A, spaced repetition, exam mode, CourseOps) remains intact; v2 adds the infrastructure and features needed for a production SaaS product.

### What Changes from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Users | Single tenant, no auth | Multi-user with roles (demo/user/admin) |
| Deployment | Local Docker Compose only | Hybrid: cloud SaaS + self-hosted |
| AI Providers | Claude Code CLI + Anthropic API | + OpenAI SDK + Ollama (4 total) |
| Billing | None | Stripe (Free + Pro tiers) |
| Notifications | None | Email + Telegram with quick actions |
| UI | 13 pages, light mode only | ~8 pages, dark mode, PWA, animations |
| Study Features | Flashcards, quizzes, exams | + Persistent AI chat, analytics, gamification, knowledge graphs |
| Calendar | One-way .ics export | Bidirectional Google Calendar sync |
| Settings | Global JSON file | Per-user DB-backed, dashboard customization |

---

## 2. Approved Feature Set

### 2.1 Core v2 Features

1. **UI Overhaul** — Consolidate 13 pages to ~8, merge Study/TimedStudy/Exams into "Study Hub", add Motion animations, page transitions, skeleton loading, Radix UI components, Sonner toasts
2. **User Account System** — Three roles:
   - **Demo**: Guided tour + free browsing with sample data, all mutations blocked
   - **User**: Full functionality, per-user data isolation
   - **Admin**: All user features + user management, metrics dashboard, system controls
3. **Multi-AI Provider** — OpenAI (GPT-4o, GPT-4o-mini) + Ollama (Llama 3.2, Mistral, etc.) added alongside existing Claude Code CLI + Anthropic API
4. **Plans & Billing** — Free + Pro (2 tiers), Stripe Checkout + subscription management + webhooks
5. **Notifications** — Email (fastapi-mail) + Telegram bot (aiogram) with inline keyboard quick actions
6. **Enhanced Settings** — Dark/light/system theme, dashboard widget toggle + reorder, AI provider selection, notification preferences

### 2.2 Additional Features

7. **AI Study Companion** — Persistent conversational chat with course material context, streaming responses, multi-turn sessions
8. **Learning Analytics & Insights** — Retention curves, study time heatmaps, exam readiness prediction, per-topic mastery tracking
9. **Gamification** — XP points, levels, achievements/badges, daily challenges
10. **Google Calendar Bidirectional Sync** — Push deadlines/exams to Google Calendar, import class schedules
11. **Knowledge Graph & Mind Maps** — AI-extracted concept maps with interactive D3 visualization, knowledge gap highlighting

---

## 3. Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deployment model | Hybrid (cloud SaaS + self-hosted) | Reach users who prefer hosted, retain privacy-first users |
| Authentication | Email/password + Google/GitHub OAuth + Magic link + TOTP MFA | Full suite for maximum flexibility |
| JWT storage | HttpOnly cookies (access 15min + refresh 7d) | XSS-safe, no localStorage tokens |
| Password hashing | Argon2id (`argon2-cffi`) | OWASP recommendation, memory-hard, no 72-char limit |
| OAuth library | Authlib v1.6+ | First-class FastAPI/Starlette integration |
| MFA | pyotp (TOTP) + backup codes | Standard authenticator app compatibility |
| Plans | Free + Pro (2 tiers) | Simple, Stripe integration |
| Billing | Stripe Checkout + subscriptions + webhooks | Industry standard, well-documented |
| AI hosted credits | Pro plan includes AI credits; BYOK option for all | Revenue model + flexibility |
| Telegram bot | aiogram v3 (async, webhook mode) | Native async, FastAPI-compatible |
| Email | fastapi-mail (SMTP) | Simple, self-hosted friendly, async |
| Animation | Motion v12 (fka Framer Motion) | React 19 native, hybrid engine, 8M+ npm downloads |
| Dark mode | Tailwind v4 CSS custom properties + `@custom-variant` | Zero-JS theming, no flash on load |
| Dashboard DnD | react-grid-layout | Purpose-built for widget dashboards with resize |
| UI components | Radix UI primitives + Sonner toasts | Headless, accessible, Tailwind-friendly |
| Forms | react-hook-form + Zod | Minimal re-renders, type-safe validation |
| Onboarding tour | OnboardJS (headless) or react-joyride | Persistent progress, Tailwind-styled |
| Charts | Recharts | Lightweight React charting, composable |
| Knowledge graph | D3 force-directed / @visx/network | Interactive, customizable |
| PWA | vite-plugin-pwa v1.2+ | Auto service worker, Workbox strategies |
| Cloud storage | S3 (cloud) / local volumes (self-hosted) | StorageBackend ABC pattern |
| Cloud hosting | AWS (ECS/Fargate + RDS + ElastiCache + S3 + CloudFront) | Scalable, well-documented |

---

## 4. New Dependencies

### 4.1 Backend (requirements.txt additions)

| Package | Version | Purpose |
|---------|---------|---------|
| `PyJWT[crypto]` | >=2.11,<3.0 | JWT encode/decode (replaces abandoned python-jose) |
| `argon2-cffi` | >=25.0,<26.0 | Argon2id password hashing |
| `authlib` | >=1.6,<2.0 | OAuth2 client (Google, GitHub) |
| `pyotp` | >=2.9,<3.0 | TOTP MFA |
| `qrcode[pil]` | >=8.0,<9.0 | QR code for MFA setup |
| `openai` | >=1.50,<2.0 | OpenAI API client |
| `ollama` | >=0.4,<1.0 | Ollama local LLM client |
| `tiktoken` | >=0.8,<1.0 | Token counting for OpenAI models |
| `stripe` | >=8.0,<10.0 | Stripe billing |
| `aiogram` | >=3.20,<4.0 | Telegram bot (async) |
| `fastapi-mail` | >=1.6,<2.0 | Async email via SMTP |
| `pywebpush` | >=2.0,<3.0 | Web push (VAPID) |
| `boto3` | >=1.35,<2.0 | S3 storage (cloud mode) |
| `google-api-python-client` | >=2.0,<3.0 | Google Calendar API |
| `google-auth-oauthlib` | >=1.0,<2.0 | Google OAuth for Calendar |

### 4.2 Frontend (package.json additions)

| Package | Version | Purpose |
|---------|---------|---------|
| `motion` | ^12.0 | Animations (fka framer-motion) |
| `@radix-ui/react-dialog` | latest | Accessible modals |
| `@radix-ui/react-dropdown-menu` | latest | Dropdown menus |
| `@radix-ui/react-tabs` | latest | Accessible tabs |
| `@radix-ui/react-tooltip` | latest | Tooltips |
| `@radix-ui/react-switch` | latest | Toggle switches |
| `sonner` | ^2.0 | Toast notifications |
| `react-hook-form` | ^7.0 | Form state management |
| `zod` | ^3.0 | Schema validation |
| `@hookform/resolvers` | ^4.0 | Zod ↔ react-hook-form bridge |
| `react-grid-layout` | ^1.5 | Dashboard widget DnD + resize |
| `recharts` | ^2.15 | Charts for analytics |
| `d3` | ^7.0 | Knowledge graph visualization |
| `vite-plugin-pwa` | ^1.2 | PWA service worker generation |
| `@onboardjs/react` | latest | Guided tour (headless) |

---

## 5. Data Model Changes

### 5.1 New Models (18 total)

```
User
├── id: UUID (PK, uuid7)
├── email: String (unique, indexed)
├── username: String (unique)
├── hashed_password: String
├── role: Enum (demo/user/admin)
├── tier: Enum (free/pro)
├── is_active: Boolean (default true)
├── email_verified: Boolean (default false)
├── mfa_secret: String (nullable, encrypted)
├── mfa_enabled: Boolean (default false)
├── avatar_url: String (nullable)
├── last_login_at: DateTime (nullable)
├── created_at, updated_at: DateTime

OAuthAccount
├── id: UUID (PK)
├── user_id: FK → users
├── provider: String (google/github)
├── provider_user_id: String
├── access_token: String (encrypted)
├── refresh_token: String (nullable, encrypted)
├── created_at: DateTime
├── UNIQUE(provider, provider_user_id)

MagicLink
├── id: UUID (PK)
├── user_id: FK → users
├── token: String (unique, indexed)
├── expires_at: DateTime
├── used_at: DateTime (nullable)
├── created_at: DateTime

UserSettings (replaces settings.json)
├── id: UUID (PK)
├── user_id: FK → users (unique)
├── settings_json: JSONB
├── dashboard_layout: JSONB (nullable)
├── theme: String (light/dark/system)
├── created_at, updated_at: DateTime

Subscription
├── id: UUID (PK)
├── user_id: FK → users
├── stripe_customer_id: String
├── stripe_subscription_id: String (nullable)
├── plan: Enum (free/pro)
├── status: Enum (active/canceled/past_due/trialing)
├── current_period_start: DateTime
├── current_period_end: DateTime
├── created_at, updated_at: DateTime

UsageRecord
├── id: UUID (PK)
├── user_id: FK → users
├── date: Date
├── ai_calls_count: Integer
├── ai_tokens_input: Integer
├── ai_tokens_output: Integer
├── uploads_count: Integer
├── created_at: DateTime
├── UNIQUE(user_id, date)

NotificationPreference
├── id: UUID (PK)
├── user_id: FK → users
├── channel: Enum (email/telegram/push)
├── event_type: String (pipeline_complete/cards_due/exam_reminder/...)
├── enabled: Boolean (default true)
├── created_at: DateTime
├── UNIQUE(user_id, channel, event_type)

TelegramLink
├── id: UUID (PK)
├── user_id: FK → users (unique)
├── chat_id: BigInteger
├── username: String (nullable)
├── verified: Boolean
├── created_at: DateTime

ChatSession
├── id: UUID (PK)
├── user_id: FK → users
├── course_id: FK → courses (nullable)
├── title: String
├── message_count: Integer (default 0)
├── created_at, updated_at: DateTime

ChatMessage
├── id: UUID (PK)
├── session_id: FK → chat_sessions
├── role: Enum (user/assistant/system)
├── content: Text
├── citations_json: JSONB (nullable)
├── token_count: Integer (nullable)
├── created_at: DateTime

AnalyticsSnapshot
├── id: UUID (PK)
├── user_id: FK → users
├── snapshot_date: Date
├── metrics_json: JSONB
├── created_at: DateTime
├── UNIQUE(user_id, snapshot_date)

UserXP
├── id: UUID (PK)
├── user_id: FK → users (unique)
├── total_xp: Integer (default 0)
├── level: Integer (default 1)
├── created_at, updated_at: DateTime

XPEvent
├── id: UUID (PK)
├── user_id: FK → users
├── event_type: String (card_reviewed/quiz_correct/streak_day/...)
├── xp_amount: Integer
├── metadata_json: JSONB (nullable)
├── created_at: DateTime

Achievement (seed data, not user-created)
├── id: UUID (PK)
├── code: String (unique)
├── title: String
├── description: String
├── icon: String
├── category: Enum (study/mastery/streak/milestone)
├── xp_reward: Integer
├── criteria_json: JSONB
├── created_at: DateTime

UserAchievement
├── id: UUID (PK)
├── user_id: FK → users
├── achievement_id: FK → achievements
├── earned_at: DateTime
├── notified: Boolean (default false)
├── UNIQUE(user_id, achievement_id)

DailyChallenge
├── id: UUID (PK)
├── date: Date (unique)
├── challenge_type: String
├── target_value: Integer
├── description: String
├── xp_reward: Integer
├── created_at: DateTime

UserDailyChallenge
├── id: UUID (PK)
├── user_id: FK → users
├── daily_challenge_id: FK → daily_challenges
├── progress: Integer (default 0)
├── completed_at: DateTime (nullable)
├── UNIQUE(user_id, daily_challenge_id)

Concept
├── id: UUID (PK)
├── user_id: FK → users
├── course_id: FK → courses
├── name: String
├── description: Text
├── embedding: Vector(384)
├── source_weeks: JSONB (list of week numbers)
├── created_at: DateTime

ConceptRelation
├── id: UUID (PK)
├── source_concept_id: FK → concepts
├── target_concept_id: FK → concepts
├── relation_type: Enum (prerequisite/related/part_of/contrasts)
├── strength: Float
├── source_artifact_id: FK → lecture_artifacts (nullable)
├── created_at: DateTime

CalendarSync
├── id: UUID (PK)
├── user_id: FK → users
├── google_calendar_id: String
├── sync_direction: Enum (push/pull/bidirectional)
├── last_synced_at: DateTime (nullable)
├── sync_token: String (nullable)
├── created_at: DateTime

CalendarEvent
├── id: UUID (PK)
├── user_id: FK → users
├── calendar_sync_id: FK → calendar_syncs
├── google_event_id: String
├── entity_type: String (deadline/exam/class_schedule)
├── entity_id: UUID
├── last_synced_hash: String
├── created_at: DateTime
```

### 5.2 Existing Model Modifications

Add `user_id: FK → users` to these existing tables:
- `courses` (owner)
- `lecture_artifacts` (uploader)
- `exams` (creator)
- `study_sessions` (student)
- `flashcard_reviews` (reviewer)
- `course_documents` (uploader)

Child tables inherit user scope via parent FK chains (summaries via course, chunks via artifact, etc.).

---

## 6. API Endpoints (New)

### 6.1 Authentication (~10 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/register` | Create account (email, username, password) |
| POST | `/api/auth/login` | Email/password login → JWT cookies |
| POST | `/api/auth/logout` | Clear JWT cookies |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user profile |
| PUT | `/api/auth/me` | Update profile (username, avatar) |
| POST | `/api/auth/verify-email` | Verify email with token |
| POST | `/api/auth/forgot-password` | Request password reset email |
| POST | `/api/auth/reset-password` | Reset password with token |
| GET | `/api/auth/oauth/{provider}` | Redirect to OAuth provider |
| GET | `/api/auth/oauth/{provider}/callback` | OAuth callback → JWT cookies |
| POST | `/api/auth/magic-link` | Request magic link email |
| GET | `/api/auth/magic/{token}` | Verify magic link → JWT cookies |
| POST | `/api/auth/mfa/setup` | Generate TOTP secret + QR code |
| POST | `/api/auth/mfa/verify` | Verify TOTP code, enable MFA |
| POST | `/api/auth/mfa/disable` | Disable MFA (requires current TOTP) |

### 6.2 Admin (~5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/admin/users` | List all users (paginated) |
| GET | `/api/admin/users/{id}` | User detail + usage stats |
| PATCH | `/api/admin/users/{id}` | Update user role/tier/active |
| GET | `/api/admin/metrics` | System metrics (total users, usage, errors) |
| GET | `/api/admin/health` | Detailed health (DB, Redis, worker, storage) |

### 6.3 Billing (~4 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/billing/checkout` | Create Stripe Checkout session |
| POST | `/api/billing/portal` | Create Stripe Customer Portal session |
| GET | `/api/billing/subscription` | Current subscription details |
| POST | `/api/billing/webhook` | Stripe webhook handler |

### 6.4 Notifications (~5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/notifications/preferences` | Get notification preferences |
| PUT | `/api/notifications/preferences` | Update notification preferences |
| POST | `/api/notifications/telegram/link` | Generate Telegram deep link |
| DELETE | `/api/notifications/telegram/unlink` | Unlink Telegram account |
| POST | `/api/notifications/telegram/webhook` | Telegram bot webhook |
| POST | `/api/notifications/test` | Send test notification |

### 6.5 AI Chat (~5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat/sessions` | Create chat session (optional course scope) |
| GET | `/api/chat/sessions` | List user's chat sessions |
| GET | `/api/chat/sessions/{id}/messages` | Get session messages (paginated) |
| POST | `/api/chat/sessions/{id}/messages` | Send message → SSE streaming response |
| DELETE | `/api/chat/sessions/{id}` | Delete chat session |

### 6.6 Analytics (~5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/analytics/overview` | Summary stats (total study time, mastery, streak) |
| GET | `/api/analytics/retention` | Retention curve data (per course) |
| GET | `/api/analytics/heatmap` | Study activity heatmap (90 days) |
| GET | `/api/analytics/mastery` | Per-week mastery breakdown |
| GET | `/api/analytics/readiness/{exam_id}` | Exam readiness prediction |

### 6.7 Gamification (~4 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/gamification/xp` | User XP, level, progress to next |
| GET | `/api/gamification/achievements` | All achievements + user's earned status |
| GET | `/api/gamification/challenges` | Today's daily challenges + progress |
| GET | `/api/gamification/leaderboard` | Top users by XP (optional) |

### 6.8 Knowledge Graph (~3 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/concepts/{course_code}` | List concepts for a course |
| GET | `/api/concepts/{course_code}/graph` | Graph nodes + edges for visualization |
| POST | `/api/concepts/{course_code}/rebuild` | Trigger concept re-extraction |

### 6.9 Google Calendar Sync (~5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/calendar/connect` | Connect Google Calendar (OAuth) |
| POST | `/api/calendar/sync` | Trigger manual sync |
| GET | `/api/calendar/status` | Sync status + last sync time |
| DELETE | `/api/calendar/disconnect` | Disconnect Google Calendar |
| POST | `/api/calendar/webhook` | Google Calendar push notification |

**Total new endpoints: ~52 (bringing total from 41 to ~93)**

---

## 7. Frontend Architecture Changes

### 7.1 Page Consolidation

| v1 Page | v2 Status | Notes |
|---------|-----------|-------|
| DashboardPage | **Keep** (enhanced) | Widget grid with toggle + reorder |
| UploadPage | **Keep** | No changes |
| CoursePage | **Keep** | No changes |
| WeekViewPage | **Keep** | No changes |
| CourseOpsPage | **Keep** | No changes |
| QAPage | **Keep** | Enhanced with chat link |
| ReviewInboxPage | **Keep** | No changes |
| StudyPage | **Merge → Study Hub** | Tab 1: Flashcards |
| TimedStudyPage | **Merge → Study Hub** | Tab 2: Timed Session |
| ExamListPage | **Merge → Study Hub** | Tab 3: Exams |
| ExamDetailPage | **Merge → Study Hub** | Inline in Exams tab |
| SettingsPage | **Keep** (enhanced) | Dark mode, AI provider, notifications, billing |
| NotFoundPage | **Keep** | No changes |
| — | **New: LoginPage** | Email/password + OAuth + magic link |
| — | **New: RegisterPage** | Account creation |
| — | **New: ProfilePage** | User profile, MFA, linked accounts |
| — | **New: ChatPage** | AI Study Companion |
| — | **New: AnalyticsPage** | Learning analytics dashboard |
| — | **New: KnowledgeGraphPage** | Interactive concept map |
| — | **New: AdminPage** | User management + system metrics (admin only) |

**v2 total: ~15 routes** (but 5 are auth-related, 1 is admin-only, so core navigation has ~8 items)

### 7.2 Navigation Structure

**Desktop Sidebar (8 items):**
1. Dashboard (`/`)
2. Upload (`/upload`)
3. Study Hub (`/study`) — replaces Study + Exams
4. Chat (`/chat`) — AI Study Companion
5. Q&A (`/qa`)
6. Analytics (`/analytics`)
7. Review (`/review`) — with badge
8. Settings (`/settings`)

**Course sub-navigation** (within course context):
- Weeks, CourseOps, Knowledge Graph

**Mobile Bottom Nav (5 tabs):**
1. Home (Dashboard)
2. Study (Study Hub)
3. Upload
4. Chat
5. More (sheet: Q&A, Analytics, Review, Settings)

### 7.3 Theme System

```css
/* index.css — Tailwind v4 dark mode */
@import "tailwindcss";
@custom-variant dark (&:where(.dark, .dark *));

:root {
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f8fafc;
  --color-bg-card: #ffffff;
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-border: #e2e8f0;
  --color-accent: #6366f1;
  --color-accent-hover: #4f46e5;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
}

.dark {
  --color-bg-primary: #0f172a;
  --color-bg-secondary: #1e293b;
  --color-bg-card: #1e293b;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-border: #334155;
  --color-accent: #818cf8;
  --color-accent-hover: #a5b4fc;
  --color-success: #34d399;
  --color-warning: #fbbf24;
  --color-danger: #f87171;
}
```

**No-flash script in index.html `<head>`:**
```html
<script>
  (function() {
    var s = localStorage.getItem('theme');
    var d = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (s === 'dark' || (!s && d)) document.documentElement.classList.add('dark');
  })();
</script>
```

---

## 8. Plans & Tier Definitions

### Free Tier
- 1 course
- 5 uploads/month
- 20 AI calls/day
- Local embeddings only (sentence-transformers)
- Claude Code CLI + Ollama backends only
- Email notifications only
- Basic analytics (study time, streak)
- No Google Calendar sync
- No knowledge graph
- Community support

### Pro Tier ($9.99/month or $99/year)
- Unlimited courses
- Unlimited uploads
- 200 AI calls/day (hosted credits) OR unlimited with BYOK
- All AI backends (Claude API, OpenAI, Ollama)
- OpenAI embeddings option
- Email + Telegram + Push notifications
- Full analytics (retention curves, readiness prediction)
- Google Calendar bidirectional sync
- Knowledge graph & mind maps
- AI Study Companion (persistent chat)
- Priority support

### Self-Hosted Mode
- All features unlocked (no tier restrictions)
- Users provide their own API keys
- No Stripe integration needed
- Admin can manage users locally
- Configured via `STUDYAIO_SELF_HOSTED=true` env var

---

## 9. Milestones (18 milestones, ~20 weeks)

### Phase 1: Authentication & Multi-Tenancy (Weeks 1-4)

#### Milestone 13 — Authentication Backend
**Goal:** User model, password hashing, JWT session management, auth middleware.

**Deliverables:**
- New models: `User`, `OAuthAccount`, `MagicLink` + Alembic migration
- `app/core/auth.py` — Argon2 hashing, JWT creation/verification (PyJWT), refresh token rotation
- `app/core/security.py` — OAuth helpers (Authlib), TOTP setup/verify (pyotp), magic link generation
- `app/services/user_service.py` — register, login, verify_email, reset_password, get/update profile
- `app/api/auth.py` — 16 auth endpoints (register, login, logout, refresh, OAuth, magic link, MFA)
- `app/api/deps.py` — `get_current_user` dependency (decode JWT from HttpOnly cookie), `require_role()`, `require_plan()`
- Config additions: `jwt_secret_key`, `jwt_algorithm`, OAuth client IDs/secrets
- ~40 tests

#### Milestone 14 — Authentication Frontend + Protected Routes
**Goal:** Login/register UI, OAuth buttons, route guards, auth context.

**Deliverables:**
- New pages: `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`, `ProfilePage`
- New components: `OAuthButtons`, `MFASetup`, `ProtectedRoute`, `RoleGate`
- `src/contexts/AuthContext.tsx` — auth state provider (user, isAuthenticated)
- `src/hooks/useAuth.ts` — login, logout, register, refresh hooks
- `src/api/auth.ts` — auth API client functions
- Router wrapped in `ProtectedRoute` (public: auth pages; protected: everything else)
- ~20 tests

#### Milestone 15 — Multi-Tenant Data Isolation
**Goal:** Per-user data scoping, settings migration to database.

**Deliverables:**
- Add `user_id` FK to existing tables: `courses`, `lecture_artifacts`, `exams`, `study_sessions`, `flashcard_reviews`, `course_documents`
- New model: `UserSettings` (replaces `data/settings.json`)
- Alembic migration with backfill (existing data → default admin user)
- All service functions updated: receive `user_id`, scope queries
- All API routers inject `current_user = Depends(get_current_user)` → pass `user_id`
- Pipeline tasks carry `user_id` alongside `artifact_id`
- SSE events scoped by user
- Admin endpoints: `GET /api/admin/users`, `PATCH /api/admin/users/{id}`, `GET /api/admin/metrics`
- `settings_service.py` rewritten: DB-backed per-user settings
- Per-user file storage: `data/users/{user_id}/uploads/`, `data/users/{user_id}/extractions/`
- ~35 tests

### Phase 2: UI Overhaul (Weeks 3-8, parallel with Phase 1)

#### Milestone 16 — UI Foundation Overhaul
**Goal:** Install new UI dependencies, redesign navigation, establish visual system.

**Deliverables:**
- Install: Motion v12, Radix UI primitives, Sonner, react-hook-form + Zod, OnboardJS
- Sidebar redesign: grouped sections, user avatar, collapsible
- MobileNav redesign: 5-tab bar with "More" sheet
- New shared components: `AnimatedCard`, `Sheet` (bottom sheet), `Skeleton` (loading), `Toast` (Sonner wrapper)
- CSS custom properties for theming (prepare for dark mode)
- Motion page transitions via `AnimatePresence` wrapping route outlet
- Migrate existing modals to Radix Dialog
- Migrate forms to react-hook-form + Zod validation
- ~10 tests

#### Milestone 17 — Multi-AI Provider System
**Goal:** OpenAI + Ollama adapters with per-user provider selection.

**Deliverables:**
- `app/agents/openai_adapter.py` — `OpenAIAdapter(AgentAdapter)` with all 6 methods
- `app/agents/ollama_adapter.py` — `OllamaAdapter(AgentAdapter)` with all 6 methods
- `app/agents/embeddings.py` extended: `OpenAIEmbeddingProvider`, `OllamaEmbeddingProvider`
- `app/agents/factory.py` updated: `get_agent(user_id)` reads per-user settings
- New `AgentAdapter` method: `stream_response()` → `AsyncIterator[str]` (for chat feature)
- `app/agents/parsing.py` enhanced: more resilient JSON extraction for less reliable providers
- Per-user settings: `agent_backend`, `openai_api_key` (SecretStr), `ollama_base_url`
- Token usage tracking per request (stored in `UsageRecord`)
- ~40 tests

#### Milestone 18 — Dark Mode + Enhanced Settings
**Goal:** Theme system, dashboard widget management.

**Deliverables:**
- Dark mode: `@custom-variant` in index.css, CSS variables for all colors, no-flash script in index.html
- `useTheme()` hook: light/dark/system with localStorage + system preference listener
- `ThemeToggle` component (Sidebar + Settings)
- react-grid-layout dashboard: draggable/resizable widgets, responsive breakpoints
- Widget registry: StudyProgress, ExamCountdown, StreakDisplay, ReviewAlert, ActivityFeed, QuickUpload, UpcomingDeadlines
- Widget toggle + reorder persisted to `UserSettings.dashboard_layout`
- Settings page enhanced: Theme section, Dashboard section, AI Provider section
- ~15 tests

### Phase 3: Billing & Study Hub (Weeks 7-10)

#### Milestone 19 — Plans & Stripe Integration
**Goal:** Free/Pro tiers, Stripe billing, feature gating.

**Deliverables:**
- New models: `Subscription`, `UsageRecord` + Alembic migration
- `app/services/billing_service.py` — Stripe Checkout, portal, webhook handler, subscription management
- `app/services/quota_service.py` — tier limit checks (uploads/month, AI calls/day, course count)
- `app/api/billing.py` — 4 billing endpoints
- `app/core/quota.py` — `check_quota()` FastAPI dependency (raises 402 on limit)
- `@require_plan("pro")` decorator for premium endpoints
- Frontend: `usePlan()` hook, `<ProBadge>` component, upgrade prompts, billing settings section
- Self-hosted mode: `STUDYAIO_SELF_HOSTED=true` bypasses all tier checks
- ~30 tests

#### Milestone 20 — Study Hub (Page Merge)
**Goal:** Merge Study + TimedStudy + Exams into single tabbed page.

**Deliverables:**
- New page: `StudyHubPage` (`/study`) with 4 tabs:
  - Flashcards (from StudyPage)
  - Timed Session (from TimedStudyPage)
  - Exams (from ExamListPage + ExamDetailPage, inline cards)
  - History (calendar heatmap, streak, session log)
- Remove: `StudyPage`, `TimedStudyPage`, `ExamListPage`, `ExamDetailPage`
- Remove routes: `/timed-study`, `/exams`, `/exams/:examId`
- Deep links: `/study?tab=exams&exam={id}`
- Navigation updates: single "Study" item replaces Study + Exams
- ~10 tests

### Phase 4: Notifications & PWA (Weeks 9-12)

#### Milestone 21 — Telegram + Email Notifications
**Goal:** Push notifications for study reminders, pipeline events, account alerts.

**Deliverables:**
- New models: `NotificationPreference`, `TelegramLink` + migration
- `app/services/notification_service.py` — dispatch to channels based on user preferences
- `app/services/telegram_service.py` — aiogram bot (webhook mode), deep link account linking, inline keyboards
- `app/services/email_service.py` — fastapi-mail templates (Jinja2): pipeline_complete, exam_reminder, cards_due, weekly_digest
- `app/api/notifications.py` — 6 endpoints (preferences CRUD, Telegram link/webhook, test)
- Celery beat tasks: `send_daily_reminders` (8am), `send_weekly_digest` (Sunday)
- Integration: pipeline completion → notification, review created → notification, cards due → daily reminder
- Docker: Telegram webhook URL config, SMTP config
- ~30 tests

#### Milestone 22 — PWA + Offline Support
**Goal:** Installable PWA with offline flashcard studying.

**Deliverables:**
- `vite-plugin-pwa` configuration in `vite.config.ts`
- `public/manifest.json` with app name, icons (192, 512, maskable), theme_color, display: standalone
- Service worker: cache-first for static, stale-while-revalidate for API data, offline fallback page
- Offline flashcard study (cache card data, queue reviews for sync when online)
- `useOnlineStatus()` hook, `OfflineBanner` component, `InstallPrompt` component
- `SyncStatus` component showing pending offline mutations
- iOS PWA install banner with instructions
- Web push notification integration (pywebpush + VAPID keys)
- ~10 tests

### Phase 5: Advanced Features (Weeks 11-16)

#### Milestone 23 — Learning Analytics & Insights
**Goal:** Visualized learning performance data.

**Deliverables:**
- New model: `AnalyticsSnapshot` + migration
- `app/services/analytics_service.py` — retention curves (Ebbinghaus), heatmaps, mastery breakdown, exam readiness prediction
- `app/api/analytics.py` — 5 endpoints
- New page: `AnalyticsPage` (`/analytics`) with tabs
- Components: `RetentionCurve` (line chart), `StudyHeatmap` (GitHub-style), `MasteryRadar` (radar chart), `ExamReadiness` (gauge), `WeeklyTrend` (bar chart) — all using Recharts
- Dashboard widget: mini analytics summary
- Celery beat: `compute_analytics_snapshots` (nightly rollup)
- ~25 tests

#### Milestone 24 — Demo Account + Onboarding Tour
**Goal:** Demo role with guided tour and sample data.

**Deliverables:**
- Demo user middleware: allow GET, block POST/PUT/DELETE (except auth endpoints)
- `scripts/seed_demo.py` — comprehensive sample data (2 courses, summaries, flashcards, exams, study history, analytics)
- OnboardJS guided tour: ~8 steps (dashboard → upload → course → study → Q&A → chat → analytics → settings)
- Tour persisted to localStorage, "Skip" and "Replay" options
- `UpgradeCTA` component shown throughout for demo users
- ~15 tests

#### Milestone 25 — Gamification System
**Goal:** XP, levels, achievements, daily challenges.

**Deliverables:**
- New models: `UserXP`, `XPEvent`, `Achievement`, `UserAchievement`, `DailyChallenge`, `UserDailyChallenge` + migration
- `app/services/xp_service.py` — award XP, level calculation, leaderboard
- `app/services/achievement_service.py` — check/unlock achievements on events
- `app/services/challenge_service.py` — daily challenge generation (Celery beat)
- `app/api/gamification.py` — 4 endpoints
- `scripts/seed_achievements.py` — ~20 achievements (First Upload, Week Warrior, 7-Day Streak, Quiz Champion, Concept Master, etc.)
- XP awards: card review (+5), quiz correct (+10), streak day (+20), achievement unlock (+varies), upload (+15)
- Level thresholds: L1=0, L2=100, L3=300, L4=600, L5=1000, L6=1500, L7=2100, L8=2800, L9=3600, L10=4500
- Components: `XPBar`, `AchievementBadge`, `AchievementUnlock` (animated modal), `DailyChallenges`, `LevelDisplay`
- Dashboard widget: XP bar + daily challenges
- ~35 tests

#### Milestone 26 — Knowledge Graph & Mind Maps
**Goal:** Auto-generated concept maps from course content.

**Deliverables:**
- New models: `Concept`, `ConceptRelation` + migration
- `app/services/concept_service.py` — extract concepts via AI, build relations via embedding similarity + AI, graph data API
- New `AgentAdapter` method: `extract_concepts(text, course_code)` → list of concept dicts
- All 4 adapter implementations updated
- New prompt: `prompts/extract_concepts.txt`
- `app/api/concepts.py` — 3 endpoints
- New page: `KnowledgeGraphPage` (`/courses/:courseCode/graph`)
- Components: `ConceptGraph` (D3 force-directed), `ConceptNode` (tooltip with definition + links), `GraphControls` (zoom, filter, search)
- Click node → navigate to relevant summary/flashcard
- ~25 tests

#### Milestone 27 — Google Calendar Bidirectional Sync
**Goal:** Live sync between StudyAIO deadlines/exams and Google Calendar.

**Deliverables:**
- New models: `CalendarSync`, `CalendarEvent` + migration
- `app/services/gcal_service.py` — create StudyAIO calendar, push/pull events, incremental sync, webhook handler
- `app/api/calendar_sync.py` — 5 endpoints
- Google OAuth scope addition: `calendar.events`
- Celery beat: `sync_calendars` (every 15 minutes)
- Settings UI: connect/disconnect, sync status, calendar picker
- CourseOps integration: "Sync to Calendar" button on deadlines
- Exam integration: "Add to Calendar" button
- ~20 tests

#### Milestone 28 — AI Study Companion (Persistent Chat)
**Goal:** Multi-turn conversational study buddy with streaming.

**Deliverables:**
- New models: `ChatSession`, `ChatMessage` + migration
- `app/services/chat_service.py` — session management, RAG context retrieval, streaming orchestration
- `app/api/chat.py` — 5 endpoints (SSE streaming for message responses)
- New prompt: `prompts/study_companion_system.txt`
- New page: `ChatPage` (`/chat`)
- Components: `ChatWindow`, `ChatMessage`, `ChatInput`, `SessionList`, `StreamingMessage` (typewriter effect)
- Context: embed question → retrieve relevant chunks → inject in system prompt with conversation history
- Differences from Q&A: persistent sessions, streaming, multi-turn context, study buddy persona
- ~25 tests

### Phase 6: Infrastructure & Polish (Weeks 17-20)

#### Milestone 29 — Cloud Infrastructure + Self-Hosted Packaging
**Goal:** Cloud deployment specs, S3 storage, self-hosted packaging.

**Deliverables:**
- `app/core/storage.py` — `StorageBackend` ABC with `LocalStorageBackend` and `S3StorageBackend`
- All file operations routed through storage backend (transparent to services)
- `infra/cloud/` directory:
  - Terraform/Pulumi for AWS: ECS Fargate, RDS PostgreSQL 16, ElastiCache Redis 7, S3 + CloudFront, ALB + ACM
  - Alternative: Railway/Fly.io deployment configs
  - `docker-compose.cloud.yml`
- `docker-compose.selfhosted.yml` — Traefik reverse proxy with Let's Encrypt TLS, backup cron, non-root services
- `scripts/setup-selfhosted.sh` — interactive setup
- GitHub Actions: build + push images to GHCR on tag, deploy to ECS on main merge
- Prometheus metrics endpoint (`prometheus-fastapi-instrumentator`)
- `docs/deployment.md` — cloud + self-hosted guides
- ~15 tests

#### Milestone 30 — Final Polish, E2E Tests, Launch Prep
**Goal:** End-to-end testing, performance optimization, documentation.

**Deliverables:**
- Playwright E2E test suite (~30 tests): register → login → upload → pipeline → study → chat → analytics
- Performance: bundle splitting per route, lazy loading for D3/react-pdf/recharts, Lighthouse 90+
- Accessibility audit: ARIA labels, keyboard nav, screen reader
- Migration guide: `docs/migration-v1-v2.md`
- Updated `docs/api.md` with all ~93 endpoints
- Updated `docs/architecture.md` with v2 diagrams
- Updated `README.md` with v2 features
- Mobile responsiveness pass on all pages
- Error state review across all components

---

## 10. Timeline & Parallelization

```
Week:  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20
═══════════════════════════════════════════════════════════════════════
Backend Track:
  M13(Auth BE)──M15(Multi-tenant)──M17(AI Providers)──M19(Stripe)──M21(Notifs)──M23(Analytics)──M25(Gamify)──M27(Calendar)──M29(Cloud)──M30
        M14(Auth FE)─┘                                                   M24(Demo)──┘            M26(KGraph)──M28(Chat)──┘

Frontend Track:
  M16(UI Foundation)────────────────M18(DarkMode+Settings)──M20(StudyHub)──M22(PWA)
═══════════════════════════════════════════════════════════════════════
```

**Critical path:** M13 → M14 → M15 → M17 → M19 → M21 → M23 → M25 → M29 → M30

**Parallel tracks:**
- M16 (UI) runs parallel with M13-M15 (no backend dependency)
- M18 (Dark Mode) runs parallel with M17 (independent)
- M20 (Study Hub) runs parallel with M19 (frontend-only)
- M22 (PWA) runs parallel with M21 (independent)
- M24 (Demo) runs parallel with M23 (independent)
- M26 (Knowledge Graph) runs parallel with M25 (independent)
- M27 (Calendar) runs parallel with M28 (Chat) (independent)

---

## 11. Test Strategy

**Estimated new tests: ~430**

| Category | Count | Focus |
|----------|-------|-------|
| Auth unit tests | ~60 | JWT, hashing, OAuth mocks, MFA, magic links |
| Multi-tenant tests | ~35 | Data isolation, user scoping, admin access |
| AI provider tests | ~40 | Each adapter method x 4 providers, factory routing |
| Billing tests | ~30 | Stripe webhooks, quota enforcement, tier transitions |
| Notification tests | ~30 | Dispatch routing, Telegram webhook, email templates |
| Analytics tests | ~25 | Retention curves, heatmaps, readiness prediction |
| Gamification tests | ~35 | XP calculation, achievements, challenges |
| Chat tests | ~25 | Session CRUD, streaming, context retrieval |
| Knowledge graph tests | ~25 | Concept extraction, relation building, graph API |
| Calendar sync tests | ~20 | Push/pull events, sync tokens, conflict resolution |
| PWA tests | ~10 | Manifest, service worker, offline banner |
| Demo/onboarding tests | ~15 | Role restrictions, seed script, tour state |
| UI foundation tests | ~10 | Component rendering, form validation |
| E2E tests (Playwright) | ~30 | Critical user journeys |

**Total v2 tests: ~981 (551 existing + 430 new)**

---

## 12. Cloud Infrastructure Specs

### AWS Architecture

```
                    ┌─────────────┐
                    │ CloudFront  │
                    │   (CDN)     │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │     ALB     │
                    │ (+ ACM TLS)│
                    └──┬─────┬───┘
                       │     │
              ┌────────┘     └────────┐
              │                       │
    ┌─────────┴──────┐    ┌──────────┴──────┐
    │  ECS Fargate   │    │  ECS Fargate    │
    │  (API + UI)    │    │  (Worker)       │
    │  2 tasks min   │    │  2 tasks min    │
    └────┬──────┬────┘    └────┬──────┬─────┘
         │      │              │      │
    ┌────┴──┐ ┌─┴────┐   ┌───┴──┐ ┌─┴────┐
    │  RDS  │ │Redis │   │  S3  │ │Celery│
    │PG 16  │ │Cache │   │Files │ │Beat  │
    │(Multi │ │(7.x) │   │      │ │(ECS) │
    │  AZ)  │ │      │   │      │ │      │
    └───────┘ └──────┘   └──────┘ └──────┘
```

### Self-Hosted Architecture

```
Docker Compose + Traefik
├── traefik (reverse proxy, Let's Encrypt TLS)
├── ui (nginx, static build)
├── api (FastAPI, uvicorn)
├── worker (Celery, configurable concurrency)
├── beat (Celery Beat scheduler)
├── db (PostgreSQL 16 + pgvector)
├── redis (Redis 7)
└── [optional] ollama (local LLM)
```

---

## 13. Migration Guide (v1 → v2)

1. **Backup** PostgreSQL database and `data/` directory
2. Run Alembic migration (adds user tables, user_id FKs)
3. Migration script creates default admin user, backfills `user_id` on all existing records
4. `data/settings.json` converted to `user_settings` DB row for default user
5. File storage reorganized: `data/uploads/` → `data/users/{admin_id}/uploads/`
6. Existing Claude Code CLI and Anthropic API adapters continue working unchanged
7. All existing API endpoints continue working (now require auth token)
8. No changes to Celery task signatures (user_id added alongside artifact_id)

---

## 14. Verification Strategy

### Per-Milestone Verification

Each milestone must pass before moving to the next:
1. All new tests pass (`pytest` green)
2. All existing tests still pass (no regressions)
3. `ruff check` passes (0 violations)
4. Frontend type checks pass (`tsc -b`)
5. Docker Compose stack starts cleanly (`docker compose up -d`)
6. Manual smoke test of new features

### End-to-End Verification (Milestone 30)

1. Full user journey: register → login → upload → pipeline → study → chat → analytics
2. Demo account: tour completes, all mutations blocked, sample data visible
3. Stripe: checkout → subscription active → feature unlocked → cancel → feature locked
4. Notifications: Telegram linked → reminder received → quick action works
5. PWA: install prompt → offline flashcard study → sync when online
6. Dark mode: toggle works, no flash, persists across sessions
7. Mobile: all pages usable at 375px, touch targets 44px+
8. Lighthouse: Performance 90+, Accessibility 100, Best Practices 100

---

## 15. Key Files to Modify

### Backend (existing files requiring changes)

| File | Changes |
|------|---------|
| `app/config.py` | ~20 new config fields (JWT, OAuth, Stripe, Telegram, S3, Ollama) |
| `app/main.py` | Auth middleware, ~8 new routers, tenant scoping |
| `app/models/__init__.py` | Import all 18 new models |
| `app/agents/base.py` | Add `stream_response()`, `extract_concepts()` abstract methods |
| `app/agents/factory.py` | Per-user agent selection, 4 backends |
| `app/agents/parsing.py` | More resilient JSON extraction |
| `app/services/settings_service.py` | Rewrite: file-based → DB-backed per-user |
| `app/core/database.py` | Multi-tenant query helpers |
| All `app/services/*.py` | Add `user_id` parameter, scope queries |
| All `app/api/*.py` | Inject `get_current_user` dependency |
| All `app/pipeline/*.py` | Carry `user_id`, scope SSE events |
| `docker-compose.yml` | Add Celery Beat service, Ollama service (optional) |
| `requirements.txt` | ~15 new dependencies |

### Frontend (existing files requiring changes)

| File | Changes |
|------|---------|
| `src/router.tsx` | Auth guards, new routes, page consolidation |
| `src/App.tsx` | AuthProvider wrapper |
| `src/index.css` | CSS variables, dark mode, custom variant |
| `index.html` | No-flash script, PWA manifest link, meta tags |
| `src/api/endpoints.ts` | ~10 new API resource groups |
| `src/hooks/useApi.ts` | ~20 new React Query hooks |
| `src/types/index.ts` | ~30 new TypeScript interfaces |
| `vite.config.ts` | PWA plugin, build optimization |
| `package.json` | ~15 new dependencies |
| `src/components/layout/Sidebar.tsx` | Navigation redesign |
| `src/components/layout/MobileNav.tsx` | 5-tab redesign |
| `src/pages/DashboardPage.tsx` | Widget grid system |
| `src/pages/SettingsPage.tsx` | Theme, AI, notifications, billing sections |
