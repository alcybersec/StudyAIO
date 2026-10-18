# M34-S2-SEC-006: safety review of the non-root AI pools

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** `b27fc19` "fix(infra): run AI worker pools as non-root studyaio", held on `hold/m34-sec006`, not on
trunk. Reviewed against `kit/retrofit` @ `8c64d1c`, the threat model (`docs/security/threat-model.md` B4), R-030,
M32 note N-3 (`docs/gates/M32/floors.md`) and the 2026-10-10 decision to set prod `data/` to `750`.

## Verdict on `b27fc19` as-is: **VETO**

The goal is right and the gain is real. The commit still cannot land as it stands, because it silently undoes a
closed, verified control (AGENT-01, R-030) on a path that prod users can reach, and it adds no guard for either the
gain or the loss. Section 4 lists the variants I would approve.

## 1. What the commit changes

| | Before (`8c64d1c`) | After (`b27fc19`) |
|---|---|---|
| `worker`, `worker-ondemand` uid | 0 (`user: "0:0"`) | 999 (`studyaio`) |
| PDF/DOCX/PPTX parsing (`extract_artifact`, `process_course_document`, both on the `pipeline` queue) | as root | as 999 |
| `claude -p` child uid | 10001 (`CLAUDE_CLI_UID`), `extra_groups=[]` | 999, the same uid as the worker |
| `CLAUDE_CLI_UID/GID` in compose | set on both AI pools in all three stacks | removed everywhere |
| HOME | root's | `/tmp/claude-home`, a uid-999 `0700` tmpfs |
| Login dir on the host | readable by root | must be owned by 999 |

What the child keeps: `--tools ""`, `--strict-mcp-config`, the env allowlist (`PATH`, `HOME`, `LANG`, `LC_ALL`, plus
the per-call login), a fresh empty `0700` cwd, the operator-only binary and model, and the fixed system prompt.

What the child loses at uid 999:

- **`data/`, every tenant's files.** The prod `750` on `data/` exists only to keep uid 10001 out. At 999 the
  child is the owner.
- **The worker's `/proc/<pid>/environ`.** Reading it needs only `PTRACE_MODE_READ` against a same-uid, dumpable
  process. Yama `ptrace_scope=1` restricts attach, not environ. That file holds `.env`: `DATABASE_URL` with the
  password, `JWT_SECRET_KEY`, the instance AI keys and `SETTINGS_ENCRYPTION_KEY`. The DB password plus the
  encryption key decrypts every user's stored AI credential (B6). That is the floor-2 asset.
- **Signal and ptrace reach.** The child can now signal the worker, and with Yama off it can attach to it.

### The existing guards do not notice

I ran the floor tier on the `b27fc19` tree, extracted to a scratch directory:
`565 passed, 13 failed, 1 skipped`. All 13 failures are `git ls-files` exiting 128, because the extract is not a
git checkout. None of them is a finding. So the floor tier is effectively green on a change that removes the
uid drop. `test_floor2_cli_child_isolation.py` sets `CLAUDE_CLI_UID` itself and tests the adapter's behaviour. No
pin checks that a deployment actually configures the drop, or that the AI pools are not root. That gap is the
second reason for the veto. Section 5 lists the guards that close it.

## 2. Which is worse

The right comparison is the **increment** each choice adds over the other, not the absolute harm.

**A root worker parsing untrusted documents (today).**
- *Exposure:* every upload by any authenticated user. The parsers include C code reached directly by attacker
  bytes: MuPDF (`pymupdf`), libxml2 (`lxml`, under `python-docx`/`python-pptx`), and Pillow.
- *Increment of root over 999, given a parser RCE:* the attacker already has every tenant's data and the worker
  env at 999, because the worker *is* that uid. Root adds persistence (the image's `/usr/local` and `/app` are
  root-owned and become writable), root-owned writes into host bind mounts (including setuid files on a mount
  that is not `nosuid`), and the full default capability set for an escape (`CAP_DAC_OVERRIDE`, `CAP_SETUID`,
  `CAP_MKNOD`, `CAP_SETFCAP`, `CAP_NET_RAW`, `CAP_SYS_CHROOT`). This is a host-compromise multiplier. Data
  confidentiality is lost either way.

**A CLI child at the worker's uid (`b27fc19`).**
- *Exposure:* only a compromise of the CLI process itself. With `--tools ""`, prompt injection cannot read a file
  (threat model §4). The realistic vectors are a malicious or vulnerable `@anthropic-ai/claude-code` or node
  build at runtime, and the CLI's own parsing of model output and of a user-supplied credential JSON.
- *Reachability in prod:* prod runs `AGENT_BACKEND=zai`, so the *instance* never spawns the CLI. However, any user
  may set `agent_backend=claude_code` with their own `claude_cli_credentials` (`VALID_BACKENDS` in
  `services/settings_service.py`, the `factory.py` default branch). The CLI therefore runs in the prod `worker`
  on demand, fed attacker-chosen credentials JSON. "Prod loses nothing" is not true.
- *Increment of 999 over 10001, given a CLI compromise:* from nothing to everything. At 10001 the child reaches no
  tenant file, no login mount and no worker env. At 999 it reaches all tenants' files and every secret, including
  the means to decrypt every user's AI credentials.

**Judgement.** The root parser is the more *likely* path. The same-uid CLI is the larger *increment* on a path
that is currently contained to zero. Neither crosses a floor's literal text, which governs app behaviour, not
post-compromise containment. `b27fc19` still turns a closed control (R-030, verified on the prod host) into a
log line, with no operator signal, on a path any prod user can reach. It also trades it for a gain that does not
change what a parser RCE can read. I will not approve that trade silently. Both properties are attainable
(section 3), so the trade is not needed.

## 3. Alternatives that keep both properties

The constraint, as devops states it: a uid-999 process cannot `setuid` or `chown`. Giving python file caps
would hand them to every parser in the process.

| # | Option | Keeps non-root parsing | Keeps the CLI off the worker's uid | Cost and risk | Roles · effort |
|---|---|---|---|---|---|
| **B** | **CLI sidecar.** A new `claude-cli` service on the same image (same codebase, like the worker pools, so architecture rule 1 holds), `user: "10001:10001"`, `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, tmpfs `/tmp`, **no `data/` mount, no `.env`**. It holds the login mount read-only. The worker pools no longer mount the login at all. A small asyncio server on a unix socket in a shared volume (socket `0660`, group 10002 `clisock`; the AI pools get `group_add: 10002`, which opens nothing else). Request: prompt, optional per-user credential JSON, timeout. Response: stdout and redacted stderr. The sidecar spawns `claude -p` with today's argv, env allowlist, cwd and cleanup, and kills on timeout (same uid). `ClaudeCodeAdapter` keeps its interface. Only its transport changes, and `get_agent` call sites do not move (floor 3 unchanged) | yes | yes, and stronger than today: a separate PID and mount namespace, so there is no `/proc/<worker>/environ` to read and no `data/` to be `750`-ed against | One more long-running process (about 40 MB idle). A per-user credential crosses the socket, so it must never be logged (floor-2 pins extend). The concurrency has to match pools × `--concurrency` (4). Removes the instance login from the worker pools, a floor-2 gain | `architect` ADR (transport, socket auth, credential-in-transit) 0.5 d · `ai` server and adapter transport and unit tests 2 d · `devops` service in 4 compose files, socket volume, preflight, login-dir owner 10001, 1 d · `safety` pins 1 d · `qa` real-socket integration 0.5 d. **About 5 agent-days** |
| A | **Capability helper.** A compiled C binary (python scripts ignore setuid and file caps), `root:studyaio 0750`, file caps `cap_setuid,cap_setgid=ep` only. It hardcodes 10001:10001: `setgroups(0)`, `setresgid`, `setresuid`, verify, clear all caps, `PR_SET_NO_NEW_PRIVS`. *After* the drop it creates its own cwd and config dir (so no `chown` is needed), reads the per-user credential from fd 3, `fork`s and `exec`s a compiled-in CLI path, enforces the timeout itself, sets `PR_SET_PDEATHSIG` after the drop, and removes its dirs. It must supervise, because a 999 worker cannot signal or `rmtree` a 10001 child | yes | yes, at today's strength | Privileged C code: a memory bug while it holds `CAP_SETUID` means root. Needs the container *without* `no-new-privileges`, which rules out that hardening on the AI pools. Timeout, kill and cleanup move into C | `architect` (ownership of a C helper; none of today's paths fit) · `devops` Dockerfile build stage and caps 1 d · `ai` or `devops` helper 1.5 d · `ai` adapter 0.5 d · `safety` review, mutation pins and fuzzing of argv/fd 1 d. **About 4 agent-days** |
| C | **Split parsing off the AI pools.** Route `extract_artifact` and the parse step of `process_course_document` to a non-root `worker-parse` pool. The AI pools stay root and keep the drop | yes | yes | AI pools stay root (N-3 only half met). `courseops` must be split into parse and AI tasks. One more pool | `ai` 1.5 d · `devops` 0.5 d · `safety` 0.5 d. **About 2.5 agent-days** |
| D | **userns-remap / rootless Docker** | no (root in the container still parses and reads everything) | n/a | Daemon-wide, so it changes every container on the host. Ownership of bind mounts breaks. Defence in depth for container escape only | operator decision · `devops` 1 d. Complementary, not a substitute |
| E | **Root with a capability diet.** `cap_drop: [ALL]`, `cap_add: [CHOWN, DAC_OVERRIDE, FOWNER, KILL, SETUID, SETGID]` on the AI pools | no | yes | Cuts the escape surface (no `MKNOD`, `SETFCAP`, `NET_RAW`, `SYS_CHROOT`) but uid 0 still owns the image files | `devops` 0.5 d, `safety` 0.25 d. **Interim only** |
| F | **`b27fc19` plus fail-closed.** Land the non-root pools. In the adapter, before spawning: if `os.geteuid() != 0` and no drop is possible, and the deployment is multi-user, **refuse** the `claude_code` backend with a configuration error (instance and per-user), unless the operator sets an explicit `CLAUDE_CLI_SHARED_UID_ACCEPTED=true`. `SINGLE_USER_MODE` is allowed (one tenant). Also refuse clearly when `CLAUDE_CLI_UID` is set on a non-root worker, instead of failing mid-call on `os.chown` with `PermissionError`. This is N-3's own second option | yes | by refusal, not by isolation | In prod, users who chose `claude_code` lose it until B lands. Multi-user self-hosters on the default backend must opt in or switch backends | `ai` guard 0.5 d · `safety` pins 0.5 d · `devops` docs 0.25 d. **About 1.25 agent-days** on top of `b27fc19` |

The other ideas raised: a mechanism "free of `docker exec`" is B in substance, and docker-socket access from a worker
would be far worse than root. "Parser non-root, CLI spawner root" inside one container is C, or A at process level.

## 4. Recommendation

1. **Target: B, the CLI sidecar.** It is the only option that improves on today on both axes at once. Parsing
   runs non-root, and the CLI child loses even the theoretical reach it has now (it gets a separate PID and mount
   namespace, no `.env`, no `data/`). It also lets the worker pools drop the Claude login mount, which
   simplifies floor 2. It needs no privileged code. It needs an ADR first (`architect`), because it changes the
   adapter's transport and moves a credential across a process boundary.
2. **If SEC-006 must close in M34 before B is built: F.** I would **APPROVE** `b27fc19` re-landed together with
   F's fail-closed adapter guard and the section 5 pins. It delivers the non-root parsers now and turns the lost
   isolation into an explicit, refused configuration instead of a silent one. B then lifts the refusal.
3. **Not recommended:** A (privileged C for a property B gets without privilege), C (leaves root pools, N-3 half
   done), D as a substitute. E is acceptable only as a stop-gap if neither B nor F is scheduled.

**User decision needed:** whether prod users who have selected `claude_code` with their own login may lose it
between F and B. Safety cannot read the prod DB to count them. A read-only count by the operator
(`agent_backend = 'claude_code'` in `user_settings`) would size the impact.

## 5. Guards I would add (`services/app/tests/safety/**`, `safety` writes them with the fix)

All of them are static compose and Dockerfile parses, in the style of `test_floor2_claude_login_mounts.py`, run
over `docker-compose.yml` merged with each of `docker-compose.prod.yml`, `docker-compose.production.yml` and
`docker-compose.selfhosted.yml` (anchors and `<<` resolved, `!reset` honoured).

1. **Non-root worker pools.** For `worker`, `worker-ondemand` and `worker-maintenance` in every stack, the
   effective `user` is set and is not `0`, `0:0`, `root` or `root:<any>`. An absent `user` falls back to the
   Dockerfile's final `USER`, which must be `studyaio`. Mutation check: put `user: "0:0"` back on the anchor and
   the test goes red.
2. **The CLI uid is never the worker's uid** (whichever option lands):
   - *B:* `CLAUDE_CLI_UID` is absent from every worker pool. The `claude-cli` service is `10001:10001`, mounts
     neither `./data` nor anything under it, has no `env_file`, and has `read_only`, `cap_drop: [ALL]` and
     `no-new-privileges`. It is the **only** service with a `/run/claude-host` mount, which supersedes today's
     "only the AI pools" pin.
   - *F:* `CLAUDE_CLI_UID` is absent from the AI pools, *and* an adapter pin: with `geteuid() != 0`, no drop and
     multi-user, both the instance and the per-user `claude_code` refuse before `create_subprocess_exec` is called.
     With the opt-in flag or `SINGLE_USER_MODE` it spawns. With `CLAUDE_CLI_UID` set on a non-root worker it
     refuses with the configuration error, not `PermissionError`. Mutation: delete the guard and the multi-user
     case spawns.
   - *If the drop stays (root pools, options C and E):* `CLAUDE_CLI_UID`/`GID` are present and non-zero on every
     pool that mounts a Claude login, in every stack. Today no pin checks this, which is how `b27fc19` removed
     them on a green tier.
3. **HOME.** On every AI pool, `HOME` is set, and is not `/`, `/root`, `/app` or anything under `/app/data` or
   `/run/claude-host`. A `tmpfs` entry exists at exactly that path with `uid=<pool uid>` and `mode=0700`. The
   adapter pin that the child's `HOME` is its private cwd whenever it drops (already in
   `test_floor2_cli_child_isolation.py`) stays.
4. **Login-dir ownership documented, never chmod-widened.** `preflight-check.sh` may report a uid-999 (or, under B,
   10001) owned dir as OK, but must never suggest `chmod` beyond `0700`/`0600`. Grep pin.
5. **Docs follow the code.** Threat model B4 and R-030 are updated in the same change (`safety`). The 2026-10-10
   `750` decision gets a follow-up row saying what it protects under the chosen option (under F it protects
   nothing against the CLI; under B it is moot but harmless).

## 6. Notes on `b27fc19` regardless of option

- `worker-maintenance` now inherits `user` from the anchor instead of declaring it. That is fine, and pin 1
  covers it.
- The Dockerfile comment still describes `claudecli` as "only used by a root worker". Under B it becomes the
  sidecar's user. The comment has to change with B.
- `setup-claude-login.sh`'s advice to run `sudo -u '#999' env HOME=/nonexistent bash …` is sound. Under B the
  uid becomes 10001.
