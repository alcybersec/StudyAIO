# StudyAIO v1 to v2 Migration Guide

This guide covers upgrading from StudyAIO v1 (Milestones 1-15) to v2 (Milestones 16-30).

## Overview of Changes

v2 adds 23 new database models, 60+ new API endpoints, multi-AI provider support, authentication, billing, gamification, and cloud deployment. The core pipeline is unchanged.

## Database Schema Changes

v2 adds these tables (run `alembic upgrade head` to apply all migrations):

**Authentication:**
- `users` — User accounts with role (demo/user/admin) and tier (free/pro)
- `oauth_accounts` — OAuth provider links (Google, GitHub)
- `magic_links` — Passwordless login and email verification tokens

**Multi-Tenant:**
- `user_settings` — Per-user settings (JSON), theme, dashboard layout
- Added `user_id` FK to: `courses`, `lecture_artifacts`, `exams`, `study_sessions`, `flashcard_reviews`, `course_documents`

**Gamification:**
- `xp_events`, `achievements`, `user_achievements`, `daily_challenges`, `user_challenges`

**Social:**
- `chat_sessions`, `chat_messages` — Persistent AI chat
- `notification_preferences`, `telegram_links`, `push_subscriptions` — Multi-channel notifications

**Billing:**
- `subscriptions` — Stripe subscription state
- `usage_records` — Daily usage tracking per user

**Knowledge:**
- `concepts`, `concept_relations` — AI-extracted knowledge graph with pgvector embeddings

**Calendar:**
- `calendar_syncs`, `calendar_events` — Google Calendar integration

### Migration Steps

```bash
# 1. Stop services
docker compose down

# 2. Pull latest code
git pull origin main

# 3. Rebuild containers
docker compose build

# 4. Run migrations (applies all new tables)
docker compose run --rm api alembic upgrade head

# 5. Seed default data
docker compose run --rm api python scripts/seed_achievements.py

# 6. Start services
docker compose up -d
```

## New Environment Variables

Add these to your `.env` file (all have sensible defaults):

### Required for new features

```bash
# JWT Authentication (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
STUDYAIO_JWT_SECRET_KEY=your-secret-key-here

# Self-hosted mode (default: true — bypasses auth, single-user)
STUDYAIO_SELF_HOSTED=true
```

### Optional (enable specific features)

```bash
# Multi-AI Provider (default: claude_code)
STUDYAIO_AI_BACKEND=claude_code  # or: anthropic_api, openai, ollama
STUDYAIO_ANTHROPIC_API_KEY=sk-ant-...
STUDYAIO_OPENAI_API_KEY=sk-...
STUDYAIO_OLLAMA_BASE_URL=http://ollama:11434

# Embedding Provider (instance-wide; default: sentence_transformers)
# Anything but the default needs the vector columns migrated to that backend's
# width and every artifact re-indexed — see docs/architecture.md.
STUDYAIO_EMBEDDING_BACKEND=sentence_transformers  # or: openai, ollama

# Stripe Billing (SaaS mode only)
STUDYAIO_STRIPE_SECRET_KEY=sk_...
STUDYAIO_STRIPE_WEBHOOK_SECRET=whsec_...
STUDYAIO_STRIPE_PRO_PRICE_ID=price_...

# OAuth (SaaS mode only)
STUDYAIO_GOOGLE_CLIENT_ID=...
STUDYAIO_GOOGLE_CLIENT_SECRET=...
STUDYAIO_GITHUB_CLIENT_ID=...
STUDYAIO_GITHUB_CLIENT_SECRET=...

# Google Calendar Sync
STUDYAIO_GOOGLE_CALENDAR_CLIENT_ID=...
STUDYAIO_GOOGLE_CALENDAR_CLIENT_SECRET=...

# Telegram Notifications
STUDYAIO_TELEGRAM_BOT_TOKEN=...

# Web Push (VAPID keys — generate with: python -m py_vapid --gen)
STUDYAIO_VAPID_PRIVATE_KEY=...
STUDYAIO_VAPID_PUBLIC_KEY=...
STUDYAIO_VAPID_CLAIMS_EMAIL=admin@example.com

# S3 Storage Backend (default: local)
STUDYAIO_STORAGE_BACKEND=local  # or: s3
STUDYAIO_S3_BUCKET=studyaio-data
STUDYAIO_S3_REGION=us-east-1
STUDYAIO_S3_ACCESS_KEY_ID=...
STUDYAIO_S3_SECRET_ACCESS_KEY=...
```

## Breaking API Changes

### Authentication Required (SaaS mode)

When `STUDYAIO_SELF_HOSTED=false`, all API endpoints except `/api/auth/*` and `/health` require authentication via HttpOnly cookies. The frontend handles this automatically via `fetchWithRefresh()`.

### User-Scoped Data

In multi-tenant mode, all data queries are scoped to the authenticated user. Endpoints return only the current user's courses, artifacts, exams, etc.

### New Response Fields

Several existing endpoints return additional fields:
- `GET /api/dashboard` now includes `active_exams`, `streak`, `gamification`, `upcoming_deadlines`
- `GET /api/courses` courses now include `user_id`
- Upload responses include `user_id` in pipeline payloads

## Frontend Changes

The frontend is fully rebuilt with:
- Route-level code splitting (React.lazy)
- Dark mode support (CSS custom properties)
- PWA with offline support
- Radix UI component primitives
- Motion page transitions
- 20 pages (up from 7 in v1)

No action needed — the UI container serves a pre-built static bundle.

## Storage Backend Migration

To migrate from local storage to S3:

1. Set `STUDYAIO_STORAGE_BACKEND=s3` and configure S3 credentials
2. Upload existing `data/uploads/` and `data/extractions/` to your S3 bucket maintaining the same key structure
3. The database already stores relative keys — no DB migration needed

## Self-Hosted vs SaaS Mode

| Feature | Self-Hosted (`true`) | SaaS (`false`) |
|---------|---------------------|----------------|
| Authentication | Bypassed (default admin) | Full JWT + OAuth |
| Registration | Disabled | Enabled |
| Multi-tenant | Single user | User isolation |
| Billing/Quotas | Bypassed | Stripe + tier limits |
| Demo account | Available | Available |

## Rollback

To rollback to v1:
```bash
git checkout v1.0  # or your v1 tag/commit
docker compose build
docker compose run --rm api alembic downgrade <v1-revision>
docker compose up -d
```

Note: v2 data (gamification, chat, achievements) will be lost on downgrade.
