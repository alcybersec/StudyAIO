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
| `AGENT_BACKEND` | `claude_code` | AI backend |
| `PROMETHEUS_ENABLED` | `false` | Enable `/metrics` |

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
