# M32 gate: Floors dimension

**Reviewer:** `safety` (veto role), review mode · **Date:** 2026-10-11
**Tree:** `kit/retrofit` @ `94a1374`. The gated code is `main` @ `b3e0671` (MR !36), which was deployed to prod
2026-10-11 by the `deploy-selfhosted` job. `git diff --stat b3e0671 94a1374` shows one file, `docs/plan/README.md`. This review adds
one floor pin and doc corrections under `tests/safety/**` and `docs/security/**` (§7). It changes no `app/` code.

Floor text is quoted from `docs/strategy.md` §6 as amended by ADR 0003, ADR 0004 (with its amendment and
clarification) and ADR 0005. The floor-to-test map is `services/app/tests/safety/FLOORS.md`, and the threat model is
`docs/security/threat-model.md`. As at M31, this file judges whether each floor **holds in the code**, which is
stricter than asking whether the tier is green.

## 1. Run evidence

### Local, on `94a1374` (the main checkout's venv, read-only; the worktree has none)

`make test-floor`'s command, before this review's additions:

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing \
    --cov-fail-under=$(python ../../scripts/coverage-tier.py floor)        # → 95
TOTAL                                                    4675    124    97%
Required test coverage of 95% reached. Total coverage: 97.35%
=========== 373 passed, 1 skipped, 29 warnings in 286.31s (0:04:46) ============
EXIT=0
```

The skip is `test_floor2_setup_script_refuses_to_run_as_root`, which is `skipif(os.geteuid() != 0)`. CI runs as
root, so CI runs it: `374 passed` there, 0 skipped.

After this review's additions (the new SEC-05 pin and the `FLOORS.md` corrections):

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=95
TOTAL                                                    4726    124    97%
Required test coverage of 95% reached. Total coverage: 97.38%
=========== 375 passed, 1 skipped, 27 warnings in 247.43s (0:04:07) ============
EXIT=0
```

`ruff check` and `ruff format --check` on the new test file: `All checks passed!` and `1 file already formatted`.

### Pipelines, read by job name

`glab api "projects/:fullpath/pipelines/<id>/jobs?include_retried=true"`

**MR head pipeline**: `kit/retrofit` @ `5a83532` (MR !36 head), pipeline `success`.

| Job | Status |
|---|---|
| `python-lint` | success |
| `backend-tests` | success |
| `test-floor` | success: `Required test coverage of 95% reached. Total coverage: 97.48%`, `374 passed, 28 warnings in 317.77s` |
| `integration-tests` | success |
| `dependency-audit` | success |
| `frontend-checks` | success |
| `e2e-tests` | success |

**`main` pipeline**: `main` @ `b3e0671`, pipeline `success`.

| Job | Status |
|---|---|
| `python-lint` | success |
| `backend-tests` | success: unit 88.87% `2920 passed, 3 skipped`; golden `317 passed`; contracts `53 passed` |
| `test-floor` | success: `Total coverage: 97.48%`, `374 passed, 29 warnings in 326.92s` |
| `integration-tests` | success: 83.44% `537 passed` |
| `dependency-audit` | success: pip-audit `No known vulnerabilities found`; `0 unallowlisted high/critical npm advisories` |
| `frontend-checks` | success |
| `e2e-tests` | success: `92 passed`, 0 skipped |
| `build-api` | success |
| `build-ui` | success |
| `deploy-selfhosted` (run 1) | **failed, by design**: `refusing: this image requires SETTINGS_ENCRYPTION_KEY and the environment has none. … Nothing was dumped, migrated or restarted.` → `exit code 68` |
| `deploy-selfhosted` (run 2) | **failed, by design**: `backups/predeploy_…sql.gz.partial: Permission denied` → `refusing: pre-migration database dump failed; nothing was migrated or restarted` → `exit code 67` |
| `deploy-selfhosted` (run 3) | success: `Checking SETTINGS_ENCRYPTION_KEY` → `Dumping database before migration` → `Running migrations (one-off container, new image)` → `Starting containers` → `Verifying health` → `Deploy complete: b3e067191c9c… (tag b3e0671)` |

No job in either pipeline is skipped or manual. The two failed deploy runs are the `deploy.sh` guards working as
intended: each one stopped before any dump, migration or restart, and left the old stack serving.

## 2. M32 §11 gate additions owned by `safety`

### C1–C6 closed

| | Condition | State | Evidence |
|---|---|---|---|
| C1 | ADR 0002 accepted | **Closed** | `docs/adr/0002…` Status: `Accepted (2026-10-09, by the user)`. Layer-direction contract test is in the `main` pipeline's `backend-tests` (`53 passed`) |
| C2a/b | R-016 functional bugs | **Closed** | All five strict xfails turned XPASS, then their markers were removed (QA-010). The integration tests pass in the `main` pipeline |
| C3 | e2e conditional skips | **Closed** | `main` pipeline `e2e-tests`: `92 passed`, 0 skipped |
| C4 | Global `AgentError` handler pinned directly | **Closed, re-mutated** | See the mutation table: the handler's `AgentError` branch disabled → `2 failed`. This kills M31 survivor 3c |
| C5 | Purge removes every summary and summary-version blob, including deleted courses' | **Closed, re-mutated** | `a3ab6ce` ledger purge. Ledger prefixes skipped → `3 failed`. Id-shape check removed → `1 failed` (S3 folder placeholder sweeps all of `summaries/`) |
| C6 | `user_id` required on scoped functions, or the floor fails on a `None` default | **Closed, re-mutated** | `ea5e6a4` plus AI-012. `review_service.get_review_item` back to `user_id: str \| None = None` → `test_floor1_caller_parameter_is_never_optional` fails |

### Floor tier non-empty and green, 0 strict xfails pinning R-016

- The tier is non-empty and green, with 376 tests after this review (§1).
- The xfail search covers the whole tests tree:
  `grep -rn "xfail\|XFAIL" services/app --include=*.py --include=*.toml --include=*.ini --include=*.cfg` and
  `grep -rnE "test\.(skip|fixme|fail)\(" services/ui/e2e`. **0 hits** in code. The only mentions are two prose lines
  in `tests/safety/FLOORS.md` that record the removed SAFETY-027 marker. No `xfail_strict` is configured, and there
  is no e2e `fixme` or `skip`.

### Mutation check (this review)

Script: `scratchpad/mutate_m32.py`, not committed because it edits other roles' `app/` code. It applies one mutant
at a time to a scratch copy of `services/app` at `94a1374`, runs the named floor tests before and after, and
restores the file.

| Mutant (the fix reverted) | Floor selection | Control | Mutant |
|---|---|---|---|
| **C4**: `studyaio_error_handler` `if isinstance(exc, AgentError)` → `if False` | `test_floor2_no_secrets.py -k global_handler` | 2 passed | **2 failed** |
| **C5**: ledger loop no longer appends `summaries/<course_id>` | `test_floor4_… -k purge` | 4 passed | **3 failed** |
| **C5**: `_COURSE_ID_RE` segment check removed | same | 4 passed | **1 failed** |
| **C6**: `get_review_item(…, *, user_id: str \| None = None)` | `-k caller_parameter_is_never_optional` | 1 passed | **1 failed** |
| **SEC-01**: factory sets the adapter's `_cli_path` from `user_settings["claude_code_path"]` | `test_floor2_operator_only_ai_settings.py -k factory` | 1 passed | **1 failed** |
| **AGENT-01**: CLI `cwd` back to `/app` | `test_floor2_cli_child_isolation.py` | 14 passed | **5 failed** |
| **AGENT-01**: `--model` dropped from argv | same | 14 passed | **2 failed** |
| **AGENT-01**: uid drop disabled | same | 14 passed | **1 failed** |
| **SEC-03**: `url_safety._check_ip` returns without checking | `test_floor2_operator_only_ai_settings.py` | 117 passed | **61 failed** |
| **SEC-06**: `secret_box.encrypt` returns plaintext | `test_floor2_no_secrets.py -k "plaintext or settings_put or ciphertext or export"` | 6 passed | **4 failed** |
| **SEC-05**: JWT default-key refusal keyed on `self_hosted` again | `test_floor2_jwt_default_secret.py` | 3 passed | **1 failed** |
| **SEC-05**: `get_current_user_or_default` falls back to the default admin on `self_hosted` alone | `tests/safety -k "single_user or self_hosted or jwt or anonymous or default_user"` | 104 passed | **104 passed: SURVIVED** |

**The one survivor.** The floor tier did not pin SEC-05's core fix. The unit tier does
(`tests/unit/test_single_user_mode.py::…test_self_hosted_alone_unauthenticated_is_rejected` and
`test_deps_default_user.py::…test_saas_mode_requires_auth` both fail on that mutant), so the hole was never unguarded
in CI. A floor-1 property still belongs in the floor tier, so this review adds
`tests/safety/test_floor1_anonymous_caller.py`. It calls every user-requiring route, admin routes included, with no
cookie on a `SELF_HOSTED`, multi-user instance. It asserts 401 everywhere, asserts that the default admin is never
resolved, and has a single-user control. On the mutant it fails with
`Floor 1 (SEC-05): an unauthenticated request on a self-hosted, multi-user instance resolved the default admin 103 time(s)`.
It is green on `94a1374`.

### Every audit S1 closed with a floor pin shown red on the hole

| S1 | Code | Pins | Red on the hole |
|---|---|---|---|
| **SEC-01**: user-settable `claude_code_path` executed by the worker | `a5f3255` (operator-only keys), `045f85c` (factory and adapter take no per-user path or model) | `test_floor2_operator_only_ai_settings.py` (PUT 422 + stores nothing; stored legacy values never reach the CLI or the Anthropic API; factory choke point; GET never echoes) | SAFETY-026 showed the factory pin red on `a5f3255` (VETO), green on `045f85c` with no test edit. Re-mutated above → red |
| **AGENT-01**: CLI cwd `/app`, root, model ignored, no system prompt | `c28312d` (no tools, env allowlist), `ff90277` and `045f85c` (cwd, uid, `--model`, `--system-prompt`, host-copy redaction) | `test_floor2_cli_child_isolation.py` (14), plus the SAFETY-057 sandbox pins | Re-mutated above: cwd, model and uid each red. SAFETY-057 mutation-checked `--tools ""` and the env allowlist. Prod: `CLAUDE_CLI_UID=10001`, uid denied on `/app/data` and `/run/claude-host` (R-030, verified on the prod host) |

**Both S1s are closed.**

### No open audit S2 in security, money or data integrity

| S2 | Verdict | Evidence |
|---|---|---|
| **SEC-03**: SSRF via user base URLs | **Closed** (residual noted) | Operator-only when not self-hosted. Self-hosted values must be public http(s), validated against 48 bypass spellings and every resolved address, re-validated at use, with no redirects (`a5f3255`, AI-024 `ee6b441`). Mutation above: 61 pins red. Residual: no DNS pinning, so rebinding is narrowed, not closed (ruled acceptable in SAFETY-026). R-032 in the register still says `open`, which is stale |
| **SEC-05**: unauthenticated = admin on self-host; DB and Redis published | **Closed** | `33c7d1d` and `8356b15`: `self_hosted=False` and `single_user_mode=False` by default. Single-user requires a loopback `BIND_HOST` or `I_UNDERSTAND_NO_AUTH`. The JWT default key is refused whenever login is on (SAFETY-027 VETO → lifted by SAFETY-028). `docker-compose.selfhosted.yml` and `.prod.yml` set `ports: !override []` on db and redis, and the base file binds them to `127.0.0.1`. New floor pin added (above). R-035 is stale at `open` |
| **SEC-06**: plaintext per-user AI credentials | **Closed** | BACKEND-031 `7c1fc3f`..`8356b15`: `enc:v1:` MultiFernet, a multi-user start refuses with no key or the all-zero test key outside pytest (SAFETY-029 `c4bdb1e`), ciphertext-shaped input is re-encrypted, and export carries no credential. Mutation above: 4 red. Prod: key set in api and worker, and the `encrypt-user-secrets` dry run reported 0 plaintext rows. R-033 is stale at `open` |
| **BILL-01**: Stripe dedupe, ordering, `trialing` | **Closed** (residual noted) | `b7974d1`: `SET NX` per event id, a per-customer `created` high-water mark, `trialing` ∈ `PRO_STATUSES`. Floor-1 pins: mutates only the named customer, replay or stale event mutates nothing, an old subscription's delete keeps the current one (dedupe mutation red, SAFETY-027). Residual: dedupe and ordering live in Redis with a TTL, so a Redis flush reopens replay; events in the same second are unordered. Not a floor matter. R-034 is stale at `open` |
| **TECH-04**: transient error = permanent failure; stuck items | **Closed** | `b011c3d`: retry with backoff through `resilience.handle_retryable` (owner-routing pin accepts it as a relay only when every call site passes a resolved owner), per-stage time limits, and the recovery beat job. Recovery is worker-only, resumes each artifact as its own row owner, and never deletes (`test_floor1_worker_jobs.py`, mutation-checked in SAFETY-027) |
| **TECH-05**: concurrent same-week summarize | **Closed** | `b011c3d`: per-(course, week) lock. Orchestrator revert check: lock removed → concurrency test fails, restored → `9 passed`. Floor 4: re-summarize under the lock still snapshots (`test_floor4_resummarize_preserves_prior_version` green) |
| **TECH-06**: backup can't run; deploy migrates without a dump | **Closed in code; first scheduled run not yet observed** | `50d769f`, AI-009/010. The predeploy dump ran in deploy run 3 (`Dumping database before migration` precedes `Running migrations`), and deploy run 2 shows it fails closed (exit 67). `BACKUP_ENABLED=true` in api and worker on prod. The first nightly `run_backup` falls after this deploy, so the Orchestrator should confirm it in the Operational dimension. Floor 4: backup retention removes only `studyaio_*` copies under the backup dir, never `data/` |

**Security, money and data integrity: none open.** Two residuals (SEC-03 rebinding, BILL-01 Redis-held state) are
recorded in the threat model, B3 and B7.

### QUOTA-01 / COST-01 on every AI-spending route (the "no bypass route" part)

I enumerated every request-time AI entry point: each `get_agent` and `get_embedding_provider` call outside
`agents/` and `pipeline/`, and each route that enqueues pipeline work (`run_pipeline`, `resume_pipeline`,
`*.delay`, `*.apply_async`).

| Route | Quota / ceiling check |
|---|---|
| `POST /uploads`, `/uploads/batch` (per file), quick capture, `/uploads/{id}/retry` | `check_upload_quota` + `check_ai_quota(calls=PIPELINE_AI_CALLS_PER_UPLOAD)` |
| `POST /artifacts/{id}/reclassify` | `check_ai_quota(calls=2)` |
| `POST /review-items/{id}/resolve` (lecture artifact) | `check_ai_quota(calls=PIPELINE_AI_CALLS_AFTER_CLASSIFY)` before applying |
| course merge regeneration | `check_ai_quota(calls=len(ids))`; skips regeneration on refusal and keeps the target's summaries (floor 4 safe) |
| `POST /courseops/documents` | upload + AI quota |
| chat send and stream, `POST /qa/ask`, `POST /concepts/extract/{id}` | `check_ai_quota` (and rate-limited) |
| classify, new course | course quota for the row owner's tier (AI-029, pinned) |
| **`POST /api/settings/test-ai`** | **None.** No `check_ai_quota`, no global ceiling, no `record_usage` and no rate limit. A user with no stored credentials gets `get_agent(None)`, which is the **instance** provider. On prod that is metered `zai`, so each call is a `classify_lecture` request billed to the operator and invisible to the global ceiling |

**Gate addition not fully met: one bypass route remains.** It is not a floor breach. Quota is not one of the four
floors, and test-ai is an ADR 0003 sanctioned call site, so floor 3 holds. It does fail the M32 gate addition
"QUOTA-01/COST-01 enforced on every AI-spending route". Remediation, owner `backend`: put `check_ai_quota(calls=1)`
and a `@limiter.limit` on `test_ai_connection`, and meter it. Alternatively, refuse test-ai when the user has no own
credentials, since there is nothing of theirs to test. `safety` will add the floor-tier route enumeration pin once the
fix lands. Whether the gate can proceed CONDITIONAL on this is the Orchestrator's and the user's call. It does not
carry a `safety` VETO. Non-zero ceilings in prod are out of scope here; the Orchestrator is verifying them separately.

## 3. Prior M32 `safety` verdicts rolled up

| Task | Verdict | Status at the gate |
|---|---|---|
| SAFETY-004 (C4 handler pin, F-2, C5/C6 red pins) | red pins by design | All green; C4/C5/C6 re-mutated above |
| SAFETY-009 / -013 (C5 review, C6 classification) | APPROVE with routed reds | Green (BACKEND-006, AI-012) |
| **SAFETY-024** (GL#10 chat, R-022 SSE owner routing) | APPROVE floors 1–4 | Pins green in the `main` pipeline |
| SAFETY-037 → **SAFETY-040** (R-023 zone validation) | VETO → lifted | Green; stale "RED until" notes removed from `FLOORS.md` here |
| SAFETY-045 → SAFETY-046 (GL#8 host-credential retry) | VETO → lifted | Green |
| SAFETY-053 → SAFETY-057 (R-027 CLI tools/env) | VETO → lifted | Green |
| **SAFETY-026** (all of wave 1) | VETO on 2 floor-2 reds (SEC-01 factory, uid-mode host copy) | Lifted by AI-025 `045f85c`; both pins green with no test edit, re-mutated above |
| **SAFETY-027** (wave 2: recovery, webhook, SEC-05) | **VETO** on SEC-05 `33c7d1d` (floor 2: committed JWT key live under `SELF_HOSTED`) | Lifted by **SAFETY-028** (`dd487f0`): XPASS on `8356b15`, marker removed, SEC-06 guards added |
| **SAFETY-028** | APPROVE | Green |
| **SAFETY-029** (R-040 sweep repair after fastapi 0.136; Fernet test-key pin) | APPROVE `6b43cbb` | `a4c81dc`→`b2205da` and `89b64e7`→`c4bdb1e` are ancestors of `94a1374` and `b3e0671` (`git merge-base --is-ancestor`). This gate's evidence is all from after them |

**R-040 rule re-applied.** `db39717` lifted pytest to 9.1.1 after SAFETY-029, which is a dependency lift. I re-ran the
floor tier (§1) and compared the sweep counts by running `_sweep_routes` and `_run_sweep` from a scratch test:

```
COUNTS api_routes=149 swept_pairs=115 owned_reached=99 violations=['GET /api/gamification/leaderboard']
```

SAFETY-029 recorded 149, 115 and 98, so nothing dropped. The one violation is the ruled opt-in leaderboard
(`SWEEP_OPT_IN_CROSS_USER`, pinned separately). `fastapi` is still capped at `>=0.134,<0.137` and the lock has
`fastapi==0.136.3`. pytest left the runtime image in `db39717`, because the lock is now only a constraints file.
That strengthens the `_running_under_pytest()` signal SAFETY-029 ruled on.

**No `safety` VETO is open.**

## 4. Per-floor judgement

### Floor 1: tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id

**Holds in the code: YES.**
- The route sweep covers 115 method+path pairs, 99 of which reach owned tables. Harness errors now fail the test
  (R-040). The four upload routes are swept, and route enumeration is guarded at ≥130/≥100.
- The C6 detector shows no optional caller parameter outside the ruled allowlist (re-mutated).
- M32 worker surfaces are pinned: SSE events go to the row owner (R-022), recovery resumes as the row owner, the
  nudge selection is correlated per user and worker-only, the classify course quota reads the row owner's tier, the
  Stripe webhook mutates only the named customer, and chat scope carry is not an existence oracle (GL#10, GL#31).
  Re-embed runs per user and the detector classifies it.
- New this gate: an anonymous caller on a self-hosted multi-user instance gets 401 on every user route (SEC-05).
- Still open, not red: R-010 (`review_items` and `quiz_attempts` are join-scoped).

### Floor 2: no secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API

**Holds in the code: YES.**
- The committed-file scan ran with git present (R-018), locally and in CI. The only `.env`-like tracked file is
  `.env.example`.
- Per-user AI credentials are encrypted at rest (SEC-06), never echoed by PUT, GET or export, and redacted at the
  adapter boundary and in the global handler (C4). Operator and host Claude logins are never handed back or logged
  (GL#8 pins). The CLI child gets an allowlisted env and no tools. Sentry frame locals are off.
- The committed JWT default key and the all-zero Fernet test key are refused at startup in every multi-user mode.
- Outside the floor's literal text, still open: OAuth and calendar tokens are plaintext at rest (R-017).

### Floor 3: AI only via the adapter (ADR 0003, ADR 0005)

> every AI call goes through a sanctioned gateway … outside `app/agents/**` and `app/pipeline/**` … each gateway is called only at the call sites enumerated in ADR 0003 (`get_agent`) and ADR 0005 (`get_embedding_provider`)

**Holds in the code: YES.** The request-time `get_agent` sites are `qa`, `settings/test-ai`, chat send and stream, and
concepts. The `get_embedding_provider` sites are `qa`, chat (two), concepts and the `main.py` startup check. Both
sets equal the ADR allowlists (`test_floor3_*_sites_equal_adr_*_allowlist`). M32 added no request-time site.
Re-embed, recovery and backup are worker-only.

### Floor 4: user data is never lost (ADR 0004)

> nothing deletes uploads or generated content under data/ except explicit account deletion and the explicit user-initiated deletes of the user's own items enumerated in ADR 0004, and dedup/re-summarize/asset regeneration never destroys prior versions or study history

**Holds in the code: YES.**
- Every blob delete is classified. The account purge is reachable only from account deletion, and with C5 it now
  reaches deleted courses' summary blobs, bounded to id-shaped ledger segments (re-mutated).
- Re-summarize under the TECH-05 lock still snapshots. Recovery never deletes. Re-embed writes new chunks before it
  deletes old ones, in one transaction. Chunks are derived DB rows, not `data/` content.
- Backup retention prunes only backup copies outside `data/`. Deploy takes a verified dump before migrating, and
  fails closed.
- The merge-regeneration quota refusal keeps the target's summaries.

## 5. Threat-model delta

Recorded in `docs/security/threat-model.md` §5 (the file is new; the 2026-10-11 delta is its first section).
Summary:

- **Encrypted per-user credentials (SEC-06):** closed for floor 2. The key is now a single point of loss: it is held
  only in the secret manager, and backups are useless for credentials without it.
- **Single-user mode (SEC-05):** opt-in only, and guarded on a declared bind. `BIND_HOST` is declared by the operator,
  not observed. Pinned at the floor tier from this gate.
- **Redis limiter, fail-closed on `/api/auth/*` (SEC-10):** brute-force protection survives a Redis outage, and auth
  availability is what pays for it (rate-limited auth routes return 503). Keys depend on `FORWARDED_ALLOW_IPS` (#39).
- **CLI sandbox at uid 10001 (AGENT-01):** closed. Residual: the drop is configured only by compose (if it is unset,
  the child stays root with only a warning), and the worker that parses untrusted documents runs as root.
- **Re-embed, recovery and backup jobs:** worker-only, owner-correct, non-destructive (pinned or verified).
- **Dependency audit in CI (SEC-07):** green with an empty allowlist. R-040 showed that a lift can blind a guard
  silently, so lifts now re-run the tier and compare sweep counts (done above). `pip-audit` itself is unpinned in CI.
- **`deploy.sh` guards:** both fired correctly in production. The key guard tests presence only, so a malformed or
  test key passes it and then crash-loops after migration (fail-closed, but an outage).
- **New cost surface found:** `POST /api/settings/test-ai` is an unmetered instance-AI route (§2).

## 6. Open non-blocking notes, with owners

| # | Note | Owner |
|---|---|---|
| N-1 | **`test-ai` quota/ceiling/metering/rate-limit bypass** (§2). This is gate-relevant for the QUOTA-01/COST-01 addition, not a floor | `backend`; `safety` pins after |
| N-2 | `fastapi` stays capped `<0.137` until `_sweep_routes`, the authn guard and `test_floor1_anonymous_caller._user_routes` expand lazy `_IncludedRouter` entries | `safety` (guards), `devops` (lift) |
| N-3 | Worker container runs as root (`user: "0:0"`) for the credential mounts, and parses untrusted PDF, DOCX and PPTX as root. Run as `studyaio` and give only the copy step the privilege it needs, or fail startup when `agent_backend=claude_code` and `CLAUDE_CLI_UID` is unset | `devops`, `ai` |
| N-4 | `deploy.sh` key check should run `secret_box.check_startup()` (validity, test-key refusal), not just test presence | `devops` |
| N-5 | CI installs `pip-audit` unpinned in `dependency-audit` | `devops` |
| N-6 | Risk register rows R-032, R-033, R-034 and R-035 still read `open`, but are closed in code and deployed (`b3e0671`) | Orchestrator (`/risk`) |
| N-7 | OAuth and calendar tokens are plaintext at rest (R-017 residual). Extend `secret_box` to them | `backend`, `data` |
| N-8 | Stripe dedupe and ordering state lives in ephemeral Redis with a TTL. A durable `last_event_created` column would survive a flush | `backend`, `data` |
| N-9 | `services/app/proof.py` is an empty file committed in `5541a28`. Remove it | `backend` |
| N-10 | TECH-06: confirm the first scheduled `run_backup` on prod (Operational dimension) | Orchestrator, `devops` |

## 7. Changes made in this review (`safety` paths only)

- `services/app/tests/safety/test_floor1_anonymous_caller.py` (new): the SEC-05 floor-1 pin and its control. It was
  red on the surviving mutant and is green on `94a1374`.
- `services/app/tests/safety/FLOORS.md`: maps the new pin. It removes the stale **RED until** notes on the SEC-01
  factory pin, the uid-mode host-copy pin (both green since AI-025) and the three R-023 zone pins (green since
  BACKEND-039).
- `docs/security/threat-model.md` (new).

**Verdict: APPROVE**
