# StudyAIO — Deployment Guide

## Quick Start (Self-Hosted)

The fastest path to a production deployment on your own server.

### Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Docker Engine 24+ and Docker Compose v2
- Domain name pointed to your server
- Ports 80 and 443 open

### One-Command Setup

```bash
git clone https://github.com/alcybersec/StudyAIO.git
cd StudyAIO
bash scripts/setup-selfhosted.sh
```

The interactive script will:
1. Check prerequisites
2. Prompt for domain, email, and passwords
3. Generate `.env` with secure defaults
4. Build and start all services
5. Run database migrations
6. Optionally seed data

Your instance will be available at `https://your-domain.com`.

### Manual Setup

If you prefer manual configuration:

```bash
# 1. Copy and edit environment
cp .env.example .env
# Edit .env with your values (domain, passwords, JWT secret)

# 2. Create data directories
mkdir -p data/uploads data/extractions data/summaries backups

# 3. Build and start
docker compose -f docker-compose.yml -f docker-compose.selfhosted.yml build
docker compose -f docker-compose.yml -f docker-compose.selfhosted.yml up -d

# 4. Run migrations
docker compose exec api alembic upgrade head

# 5. Verify
curl https://your-domain.com/health
```

---

## AWS Cloud Deployment

### Option A: Terraform (ECS Fargate)

Full managed infrastructure: VPC, ECS Fargate, RDS PostgreSQL, ElastiCache Redis, S3, ALB with TLS.

```bash
cd infra/cloud/aws

# 1. Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

# 2. Initialize and plan
terraform init
terraform plan

# 3. Apply
terraform apply

# 4. Run migrations (one-time)
# SSH into a bastion or use ECS exec:
aws ecs execute-command --cluster studyaio-prod-cluster \
  --task <task-id> --container api \
  --interactive --command "alembic upgrade head"
```

**Resources created:**
- VPC with public/private subnets across 2 AZs
- NAT Gateway for private subnet egress
- RDS PostgreSQL 16 (encrypted, 7-day backups)
- ElastiCache Redis 7.1
- S3 bucket (versioned, encrypted, private)
- ECS Fargate cluster with API + Worker services
- ALB with HTTP→HTTPS redirect
- CloudWatch log group (30-day retention)
- IAM roles with least-privilege S3 access

### Option B: Single-VM Cloud Compose

For smaller deployments using managed RDS/ElastiCache but running containers on a single VM.

```bash
# 1. Set up your VM (EC2, DigitalOcean, etc.)
# 2. Install Docker
# 3. Copy the cloud compose file
scp infra/cloud/docker-compose.cloud.yml your-server:~/studyaio/docker-compose.yml

# 4. Create .env with external service URLs
cat > .env <<EOF
DOMAIN=studyaio.example.com
ACME_EMAIL=admin@example.com
DATABASE_URL=postgresql+asyncpg://user:pass@your-rds-endpoint:5432/studyaio
DATABASE_URL_SYNC=postgresql://user:pass@your-rds-endpoint:5432/studyaio
REDIS_URL=redis://your-elasticache-endpoint:6379/0
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket
S3_REGION=us-east-1
JWT_SECRET_KEY=$(openssl rand -hex 32)
SELF_HOSTED=false
EOF

# 5. Start
docker compose up -d
```

---

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/deploy.yml`) automates:

1. **Build** — On push to `main` or version tags (`v*`):
   - Builds API and UI Docker images
   - Pushes to GitHub Container Registry (GHCR)
   - Tags: `latest`, semver, git SHA

2. **Deploy** — After successful build:
   - Updates ECS services with `--force-new-deployment`
   - Waits for stable deployment

### Required Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user for ECS deployment |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |

### Required Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region |
| `ECS_CLUSTER` | `studyaio-prod-cluster` | ECS cluster name |
| `ECS_API_SERVICE` | `studyaio-prod-api` | API service name |
| `ECS_WORKER_SERVICE` | `studyaio-prod-worker` | Worker service name |

---

## Storage Configuration

StudyAIO supports two storage backends:

### Local Filesystem (default)

```env
STORAGE_BACKEND=local
DATA_DIR=/app/data
```

Files stored under `data/uploads/`, `data/extractions/`, `data/summaries/`.

### S3-Compatible

```env
STORAGE_BACKEND=s3
S3_BUCKET=my-studyaio-bucket
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=AKIA...      # Optional if using IAM roles
S3_SECRET_ACCESS_KEY=...      # Optional if using IAM roles
S3_ENDPOINT_URL=              # For MinIO/LocalStack
S3_PREFIX=                    # Optional key prefix
CDN_BASE_URL=https://cdn.example.com  # Optional CDN
```

Works with AWS S3, MinIO, DigitalOcean Spaces, and any S3-compatible service.

---

## Backup & Restore

### Create Backup

```bash
# Self-hosted
make backup

# Or directly
bash scripts/backup.sh
```

Creates `backups/studyaio_YYYYMMDD_HHMMSS_db.sql.gz` and `..._data.tar.gz`.

### Automated Backups to S3

```bash
S3_BACKUP_BUCKET=my-backup-bucket bash scripts/backup.sh
```

### Automated Daily Backups

Enable automated backups via Celery beat by setting these environment variables:

```bash
BACKUP_ENABLED=true
BACKUP_SCHEDULE_HOUR=2   # Hour (UTC) for daily backup, default 2 AM
BACKUP_RETENTION=7       # Number of backups to keep
```

The backup task runs daily and includes dump integrity verification.

### Retention Policy

Default: keep last 7 backups. Override with `BACKUP_RETENTION=14`.

### Restore

Use the restore script for a guided restore process:

```bash
# List available backups and restore interactively
make restore ts=20260310_020000

# Or directly
bash scripts/restore.sh 20260310_020000

# List available backups without restoring
bash scripts/restore.sh
```

The restore script will:
1. Verify dump integrity
2. Stop application services
3. Restore the database (with schema recreation)
4. Restore the data directory (if archive exists)
5. Run migrations
6. Restart all services

**Manual restore** (if the script is not available):

```bash
# Database
gunzip -c backups/studyaio_20260306_db.sql.gz | \
  docker compose exec -T db psql -U studyaio studyaio

# Data directory
tar xzf backups/studyaio_20260306_data.tar.gz
```

### Pre-flight Configuration Check

Before deploying, validate your `.env` file:

```bash
make preflight
# Or: bash scripts/preflight-check.sh
```

This checks for common misconfigurations: default JWT secrets, insecure cookie settings, exposed OpenAPI docs, and more.

---

## Monitoring

### Prometheus Metrics

Enable with:

```env
PROMETHEUS_ENABLED=true
```

Metrics endpoint: `GET /metrics` (Prometheus text format).

Includes standard FastAPI metrics: request count, latency histograms, in-progress requests.

### Error Monitoring (Sentry)

Off unless a DSN is set — no DSN means the SDK is never initialized, in the API,
the worker, or the browser.

```env
SENTRY_DSN=            # the DSN from your Sentry project settings
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1   # 0 disables performance tracing
SENTRY_RELEASE=                  # optional, e.g. the git SHA
```

The frontend DSN is compiled in at **build** time, not read at runtime:

```bash
docker build --build-arg VITE_SENTRY_DSN=https://... services/ui
```

In CI this comes from the `VITE_SENTRY_DSN` repository secret (see
`.github/workflows/deploy.yml`); leaving the secret unset builds a UI with
monitoring disabled.

**What is scrubbed.** `send_default_pii=False`, plus a `before_send` hook that
filters `Authorization`/`Cookie`/`x-api-key` headers, drops cookies entirely, and
replaces `?token=` in URLs. Password-reset and email-verification links are bearer
credentials for the account — they must never reach a third-party service.

### Health Check

```bash
curl https://your-domain.com/health
# {"status": "ok"}
```

---

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async Postgres connection |
| `DATABASE_URL_SYNC` | `postgresql://...` | Sync Postgres connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `DATA_DIR` | `/app/data` | Base data directory |
| `APP_BASE_URL` | `http://localhost:3001` | Public frontend origin. **Set this in production** — password reset links are built from it, so a wrong value emails users a link they cannot open. |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `S3_BUCKET` | | S3 bucket name |
| `S3_REGION` | `us-east-1` | AWS region |
| `S3_ENDPOINT_URL` | | Custom S3 endpoint |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SELF_HOSTED` | `true` | Bypass tier/quota checks |
| `JWT_SECRET_KEY` | (insecure default) | **Change in production** |
| `CORS_ORIGINS` | `http://localhost:3001` | Comma-separated origins |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max upload file size |
| `AGENT_BACKEND` | `claude_code` | AI backend: `claude_code`, `anthropic_api`, `openai`, `zai`, `ollama` |
| `ZAI_API_KEY` | | Z.ai (GLM) API key, when `AGENT_BACKEND=zai` |
| `ZAI_MODEL` | `glm-5.3` | GLM model id, e.g. `glm-5.3`, `glm-5.3-flash`, `glm-4.6` |
| `ZAI_BASE_URL` | `https://api.z.ai/api/paas/v4/` | Override only for a regional or self-hosted endpoint |
| `PROMETHEUS_ENABLED` | `false` | Enable `/metrics` |
| `REGISTRATION_MODE` | `open` | `open`, `invite` (a valid code is required), or `closed`. Enforced server-side on `POST /api/auth/register`. |
| `SENTRY_DSN` | | Error monitoring for API + worker. Empty disables it entirely. |
| `SENTRY_ENVIRONMENT` | `development` | Environment tag on Sentry events |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Performance trace sampling; `0` disables |
| `SENTRY_RELEASE` | | Release tag, e.g. the git SHA |
| `VITE_SENTRY_DSN` | | Frontend DSN — a **build arg**, not runtime |
| `FREE_MAX_COURSES` | `1` | Courses per free account; 0 = unlimited |
| `FREE_MAX_UPLOADS_PER_MONTH` | `5` | Uploads per free account per month |
| `FREE_MAX_AI_CALLS_PER_DAY` | `100` | AI calls per free account per day (~4 per upload) |
| `PRO_MAX_COURSES` / `PRO_MAX_UPLOADS_PER_MONTH` / `PRO_MAX_AI_CALLS_PER_DAY` | `0` | Pro equivalents; 0 = unlimited |
| `GLOBAL_MAX_AI_CALLS_PER_DAY` | `0` | Instance-wide daily AI call ceiling; 0 disables |
| `GLOBAL_MAX_AI_TOKENS_PER_DAY` | `0` | Instance-wide daily token ceiling; 0 disables |

---

## Transactional Email

Password reset is the one flow that cannot work without email. `POST /api/auth/forgot-password`
mints a one-hour, single-use token and emails a link to `APP_BASE_URL/reset-password?token=…`.

Both of these must be set for it to work in a multi-user deployment:

- `APP_BASE_URL` — the origin the user's browser can reach.
- `SMTP_HOST` and `SMTP_FROM_EMAIL` (plus `SMTP_USERNAME` / `SMTP_PASSWORD` if the
  server needs auth). Without them `send_email` short-circuits and nothing is sent.

The endpoint always returns 202, whether or not the address belongs to an account
and whether or not the mail server accepted the message — that is deliberate, so it
cannot be used to enumerate users. Check the logs to see what actually happened:

- `email_sent` — delivered to the SMTP server.
- `password_reset_email_undeliverable` — SMTP is unconfigured or refused it. In
  SaaS mode (`SELF_HOSTED=false`) the link is deliberately **not** logged; it is a
  bearer credential for the account.
- `password_reset_link_not_emailed` — self-hosted only. The link is included in
  this log line so a single-user operator with no mail server can still get in.

---

## Running a Closed Beta

Before inviting anyone, run `make preflight` — it now fails on the two
configurations that break a beta silently.

**0. Create an admin account.** Every step below needs one, and a fresh
instance has none you can log in to: the self-hosted default admin is created
with no password and an undeliverable `admin@studyaio.local` address, and the
admin API requires a real session. Bootstrap one while still in self-hosted
mode:

```bash
make ensure-admin email=you@example.com
```

On a deployed host there is no checkout and no Makefile — only the compose
files are copied there — so use the underlying command directly:

```bash
docker compose exec -T api python -m app.cli ensure-admin --email you@example.com
```

The command prints a single-use set-password link valid for 24 hours. It
targets the existing default admin row when there is one, so everything that
account already owns keeps its owner. It also prints the base URL the link was
built from: if `APP_BASE_URL` is still an internal hostname or `localhost`, the
token is not origin-bound, so substitute an origin your browser can reach and
keep the `?token=` intact.

Follow the link, set a password, and confirm you can log in **before** changing
`SELF_HOSTED` — after the flip the default identity no longer exists and there
is no other way in.

Re-running the command is safe, but it voids any link an earlier run printed.
If you run it twice, use only the newest link — an older one fails with
"Reset token already used", which is supersession, not a compromise.

The link is a bearer credential for an admin account. Do not paste it into a
shared channel.

**1. Multi-user mode.** `SELF_HOSTED=false`. Left at `true`, the API falls back
to a single shared admin identity and there are no real accounts.

**2. Working outbound email.** Set `SMTP_HOST` and `SMTP_FROM_EMAIL`. With them
empty, `send_email()` returns `False` without sending, so password resets and
verification emails quietly do nothing — a tester who forgets their password has
no way back into their account. Preflight treats this as an error in SaaS mode.

**3. Gate registration.**

```env
REGISTRATION_MODE=invite
```

Then mint a code per tester (Admin → Invite codes, or the API):

```bash
curl -X POST https://your-domain.com/api/admin/invites \
  -H 'Content-Type: application/json' \
  --cookie 'access_token=<admin token>' \
  -d '{"max_uses": 1, "expires_in_days": 30, "note": "Sam"}'
# {"code": "BETA-7F3KQ2MN", ...}
```

Codes are single-use by default and revocable (`DELETE /api/admin/invites/{id}`).
`users.invite_code_id` records which code each account used, so a code that leaks
can be traced to the accounts it created.

Alternatively, create the account yourself in **Admin → Users → Add user**. That
returns a single-use set-password link which is emailed when SMTP is configured
and always shown on screen so you can relay it directly — useful before SMTP is
working. The same panel can reset a tester's password, resend their verification
email, change their tier, or delete them outright.

If you mistype a tester's address, an admin can correct it with
`PATCH /api/admin/users/{id}` (`{"email": "..."}`), which also revokes any
outstanding setup or verification link addressed to the old inbox. The admin UI
cannot send this field yet, so use `curl` or `/docs`.

**4. Raise the free-tier limits.** The defaults are shaped for a paywall, not a
beta: 1 course and 5 uploads/month. Keep testers on the **free** tier and raise
the limits by environment instead of promoting them to `pro`, which
short-circuits every per-user check and leaves only the global ceiling:

```env
FREE_MAX_COURSES=10
FREE_MAX_UPLOADS_PER_MONTH=60
FREE_MAX_AI_CALLS_PER_DAY=200
```

`0` means unlimited for any of these. `PRO_MAX_*` exist too, if you would rather
raise the pro tier than the free one.

The three do not need to balance: at roughly four pipeline calls per upload, 200
calls/day would allow ~50 uploads in a day, so the monthly upload cap is what
actually bounds pipeline usage. The daily call limit is there to bound chat and
Q&A, which no upload cap touches.

**4b. Bound the bill.** Per-user limits do not cap what the *instance* spends:
five testers on 100 calls/day is 500 calls/day. Set a ceiling:

```env
GLOBAL_MAX_AI_CALLS_PER_DAY=300
```

Once reached, new uploads and chat return `429` with `Retry-After`; pipelines
already running finish, so no artifact is left half-processed. The counter resets
at 00:00 UTC. Unlike the per-tier limits this applies to pro accounts and in
self-hosted mode too — it is a cost guard, not a plan feature. Today's spend and
the ceiling are shown on **Admin → metrics**.

Pipeline AI calls are metered from this release on. Token counts are recorded for
OpenAI, Z.ai and Anthropic; the Claude Code CLI reports no usage, so its calls are
counted with zero tokens.

**5. Decide who pays for AI.** `AGENT_BACKEND=claude_code` shells out to the CLI
using the credentials mounted into the worker, so every tester's usage bills to
that personal account — fine for a single-user box, wrong for a beta serving
other people. For a closed beta prefer a metered key:

```env
AGENT_BACKEND=zai
ZAI_MODEL=glm-5.3-flash
ZAI_API_KEY=...
```

`anthropic_api` is the higher-quality, higher-cost alternative. Preflight now
fails if the backend you select has no credential, rather than letting every
pipeline run break with a symptom far from the cause.

Cap spend at the provider account level as well as in the app — the in-app
ceiling can be defeated by a bug, and two independent limits are the point.

Prompts were tuned against Claude. Before inviting anyone, run one real lecture
end to end on your chosen model and read the summary against the eight sections
`prompts/summarize.txt` requires — the golden test derives its section list from
that prompt but asserts against a fixture, so a model swap can change the output
structure with the suite green.

Testers *can* supply their own credentials in Settings → AI Providers, which
moves the cost to them, but it is a rough first-run experience.

**6. Turn on Sentry.** See *Error Monitoring* above. Without it, "it broke" reports
arrive with no timestamp and no stack.

### Deleting a tester's data

`DELETE /api/auth/account` (Settings → Data & Privacy) hard-deletes the account,
every row it owns across all 40 tables, and its files in storage. There is no
grace period and no recovery. `GET /api/auth/account/export` returns the same
data as JSON, minus credentials — worth suggesting before anyone deletes.

---

## Troubleshooting

### Services won't start

```bash
docker compose logs api    # Check API logs
docker compose logs worker # Check worker logs
docker compose exec db pg_isready -U studyaio  # Check DB
docker compose exec redis redis-cli ping       # Check Redis
```

### Database migration errors

```bash
# Reset and re-run
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
```

### TLS certificate issues

- Ensure ports 80 and 443 are open
- Verify DNS A record points to your server
- Check Traefik logs: `docker compose logs traefik`

### S3 connection errors

- Verify bucket exists and region is correct
- Check IAM permissions (GetObject, PutObject, DeleteObject, ListBucket)
- For MinIO: set `S3_ENDPOINT_URL=http://minio:9000`
