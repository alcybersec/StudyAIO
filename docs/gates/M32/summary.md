# M32 gate — Safe to grow

**Date:** 2026-10-11 · **Tree:** `kit/retrofit` @ `94a1374` (code identical to `main` @ `b3e0671`, MR !36,
deployed to prod 2026-10-11) plus the gate's own commits (`07765c2` floors + one floor-1 pin, risk updates).
**Run by:** Orchestrator. **Signers:** Orchestrator, `safety` (veto role). No contract changed in this gate
(`docs/CONTRACTS.md` unchanged since `core.clock v1`, ARCH-033), so `architect` does not sign.

## Floors

**APPROVE** — written by `safety`: [`floors.md`](floors.md). No VETO open. Threat model:
[`docs/security/threat-model.md`](../../security/threat-model.md) (new). Not restated here.

## Functional

Every M32 task in `docs/strategy.md` §11, with its handoff evidence in `docs/plan/README.md` → Completed.

| Group | Tasks | Acceptance evidence | Result |
|---|---|---|---|
| S1 — M31 conditions | C1 ARCH-027 (ADR 0002 Accepted); C2a BACKEND-001; C2b BACKEND-002; C3 QA-003; C4 SAFETY-004; C5 BACKEND-005; C6 BACKEND-006 + AI-012 + SAFETY-009 | Plan rows for each; strict xfails XPASS'd then removed; e2e `92 passed`, 0 skipped (jobs 4775, 4782); C4/C5/C6 pins re-mutated red by `safety` at this gate | met |
| S2 — R-023 clock policy | DATA-032, ARCH-033 (ADR 0006), BACKEND-034/039, FRONTEND-035, AI-036, QA-038, SAFETY-037/040 | Plan rows; ADR 0006 Accepted; clock contract green; SAFETY-040 APPROVE | met |
| S3 — GL#7/#8/#9, R-024..R-028 | DEVOPS-042/059/060, AI-041/043/044/049/058, SAFETY-045/046/050/057, QA-047 | Plan rows; MR !34 deployed `c28312d` and verified on the prod host | met |
| S4 wave 1 | BACKEND-001 SEC-01, AI-002 AGENT-01, BACKEND-003 AI-05, BACKEND-004 SEC-03, BACKEND-005 PROD-03, AI-006 AI-04, FRONTEND-008 UX-06, BACKEND-023 GL#31, BACKEND-009 QUOTA-01/COST-01, + AI-024/025/029, DATA-027/031, DEVOPS-022, FRONTEND-025, QA-021/028/030/032, SAFETY-026 | Plan rows; MR !35 deployed `677209b`, verified on VM (uid 10001 denied on data/host creds) | met (QUOTA-01 one route open → G1) |
| S4 wave 2 | AI-007 AI-03, BACKEND-010 SEC-06, BACKEND-011 BILL-01, AI-012/013 TECH-04/05, DEVOPS-014 TECH-06, BACKEND-015 SEC-05, FRONTEND-016 UX-05, DEVOPS-017 SEC-07, BACKEND-018 SEC-10, DEVOPS-019 SEC-11, QA-020 UX-08, + fix-ups AI-008/009/010, BACKEND-030/031/032, QA-033/034, DEVOPS-028..031, SAFETY-027/028/029 | Plan rows; pipeline #586 7/7 by name; MR !36 deployed `b3e0671` (`deploy-selfhosted` success), verified on the prod host; re-embed 66/66 applied, 0 failed; encrypt-user-secrets 0 plaintext | met |

No task of the milestone is missing its handoff or acceptance evidence.

## Tests

From `qa` (M32 gate Tests dimension), **PASS**, commands run on `94a1374`:

| Tier | Command | Result | Target |
|---|---|---|---|
| unit+golden+contracts | `pytest tests/unit tests/golden tests/contracts --cov=app` | `88.98%`, `3293 passed` | ≥ 75 |
| floor | `pytest tests/safety --cov=tests/safety --cov-fail-under=95` | `97.35%`, `373 passed, 1 skipped` (root-only; runs in CI) — after the gate pin: `97.38%`, `375 passed, 1 skipped` (`safety`) | ≥ 95 |
| integration | `scripts/test-integration.sh` | `83.44%`, `537 passed` | ≥ 70 |
| frontend | `npm run lint` / `tsc -b` / `vitest run` | 0 errors (2 warnings) / clean / `660 passed` | — |

Pipelines read **by job name** (`glab api …/pipelines/<id>/jobs`):

- **#586** (MR !36 head `5a83532`): python-lint, backend-tests, test-floor, integration-tests, dependency-audit,
  frontend-checks, e2e-tests — all `success`, none skipped.
- **#587** (`main` `b3e0671`): the same seven + build-api, build-ui — `success`. `deploy-selfhosted`: 4785
  failed exit 68 (key missing from the host env — guard refused before any change), 4793 failed exit 67 (backup
  dir permissions — guard refused before migrating), **4794 success** (dump → migrate → start → health). No
  skipped job behind a failed one; no stale claim.
- e2e: `92 passed`, 0 skipped, in both pipelines (C3 met without accepted skips).
- Golden `317 passed`; M32 golden changes additive (`study_nudge` in the event set, admin shapes);
  TestPromptContract green after the GL#9 prompt change.
- xfail markers: **0** in `services/app/tests` and `services/ui/e2e` (gate requires 0 pinning R-016).

## Operational

Verified on the prod host on 2026-10-11, values as booleans/counts only:

- **Deploy:** api/worker/beat/ui on `ghcr.io/…:b3e0671`, both compose files, 0 restarts; alembic
  `c8e2a5f93d16 (head)`; `/health/ready` 200; 0 error lines in api/worker since start.
- **Backups (TECH-06):** `run_backup` executed in the worker → `SUCCESS`, DB dump 8.0 MB + data archive;
  pre-migration dump `predeploy_…_b3e0671.sql.gz` (6.0 MB) written by `deploy.sh`; `daily-backup` on the beat
  schedule (02:00). Backup dir now `2770` + ACL (deploy user and worker uid only). The first **scheduled** run is
  not yet observed → G4.
- **Recovery (TECH-04):** `recover-stuck-artifacts` sent by beat at 10:30Z, succeeded, `{'requeued': [], 'failed': []}` — visible in the central log store.
- **Logs:** structured logs for re-embed, recovery, backup and retries reach the central log store.
- **Metrics: gap.** `prometheus_enabled=False` on prod (`/metrics` 404); TECH-04's retry counters live in an
  in-process `Counter` that nothing exports. The kit's "counters and latency with the feature" rule is not met
  for the new jobs → G3.
- **Spend ceilings:** `global_max_ai_calls_per_day=300`, `global_max_ai_tokens_per_day=2000000` (non-zero).
- **Config:** encryption key set and `BACKUP_ENABLED=true` in api and worker; `SELF_HOSTED=false`; registration
  `invite`; notifications enabled, SMTP host and app base URL set.
- **Runbook:** `docs/deployment.md` § SETTINGS_ENCRYPTION_KEY (generation, secret manager, rotation, never lose it,
  `encrypt-user-secrets`); `deploy.sh` exit 68/67 guards; host `deploy.sh` reinstalled.
- **Rollback:** wave 2 added no migration (head unchanged since wave 1), so `IMAGE_TAG=677209b` is
  schema-compatible. Caveat: credentials written after `b3e0671` are encrypted and unreadable by older images
  (0 credentials existed at deploy time).
- **Data model / backup coverage:** no schema change in wave 2; credential ciphertext is in `user_settings`
  (covered by the DB dump); the key is not in backups by design — losing it loses stored credentials.

## Milestone additions

From `docs/strategy.md` §11 M32 Gate additions:

| Addition | Status | Evidence |
|---|---|---|
| C1–C6 closed | **met** | Functional S1; `safety` re-mutated C4/C5/C6 |
| Floor tier non-empty and green | **met** | 375 passed, 97.38% |
| 0 strict xfails pinning R-016 | **met** | 0 xfail markers anywhere (`qa` inventory) |
| Every S1 (SEC-01, AGENT-01) closed with a floor pin shown red on the hole | **met** | `safety`: SEC-01 1 red; AGENT-01 cwd 5 red, `--model` 2 red, uid 1 red |
| QUOTA-01/COST-01 enforced on every AI-spending route, non-zero ceilings in prod | **partly met** | ceilings 300 / 2M in prod; **`POST /api/settings/test-ai` calls the instance provider with no quota, ceiling, metering or rate limit** (`floors.md` N-1) → G1 |
| No open audit S2 in security/money/data integrity | **met** | SEC-03, SEC-05, SEC-06, BILL-01, TECH-04, TECH-05, TECH-06 closed (`floors.md`); TECH-06 scheduled run → G4 |
| `safety` APPROVE | **met** | [`floors.md`](floors.md) |

Also outstanding from the milestone's own decisions: PROD-08 ("beta users get Pro") — prod has 1 active user
still on the free tier → G2.

## Verdict

**CONDITIONAL.**

| # | Condition | Owner | Deadline task |
|---|---|---|---|
| G1 | `POST /api/settings/test-ai`: quota check, global ceiling, usage recording and rate limit when it uses the instance provider; `safety` floor pin | `backend` (+`safety` pin) | M33-S1-BACKEND-001 |
| G2 | Run `grant-pro` for remaining beta users (dry run first); confirm 0 active free-tier beta users | user (operator) | M33-S1-OPS-002 |
| G3 | Export counters/latency for retries, recovery, re-embed and backup (enable Prometheus on prod or ship equivalent log-based alerts) | `devops`, `ai` | M33-S1-DEVOPS-003 |
| G4 | Observe the first scheduled `daily-backup` on prod (02:00) succeed and land in the backup dir | Orchestrator, `devops` | M33-S1-OPS-004 |

**Condition status (2026-10-11, after the gate):**

| # | Status | Evidence |
|---|---|---|
| G1 | **closed** | MR !37 (`b92177a`, deployed): quota + global ceiling checked before the instance provider, usage recorded on success and failure, 5/minute rate limit; 7 red-first unit tests; `safety` floor pin over every request-time AI call site, 9 mutants red; floor `437 passed` |
| G2 | **closed** | `grant-pro` dry run then apply on prod: 1 granted, 1 already Pro; active users by tier now `pro 2` |
| G3 | **closed** | MR !37 deployed: api `/metrics` 200 (31 families), worker metrics server on loopback port 9101 returns 200 with `studyaio_*` families, UI returns 404 for `/metrics`; label policy pinned in the floor tier (4 mutants red) |
| G4 | **closed** 2026-10-12 | scheduled `daily-backup` ran at 02:00 UTC on prod and succeeded in 22.7 s (DB dump 8.0 MB + data archive written to the backup directory; worker log `Backup complete`) |

Non-blocking notes (N-2 … N-10) are listed in [`floors.md`](floors.md) with owners.

**Carried conditions.** M31's C1–C6 entered M32 as carried conditions and **all six are closed** — none
survives a second milestone. G1–G4 are new at this gate (first milestone carried: M33).

Signed: Orchestrator (2026-10-11) · `safety`: APPROVE (`floors.md`).
