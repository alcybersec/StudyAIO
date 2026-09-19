# Login security review — September 2026

A review of the public beta's authentication surface, run against the live
deployment rather than only the source. Recorded here because two of the four
findings live in infrastructure outside this repo, and because one of my own
intermediate conclusions was wrong in a way worth remembering.

Scope: `POST /api/auth/*`, the rate limiter, session handling, and the edge in
front of them. Not a full application audit.

## What held up

Verified, not assumed:

- **Argon2id** password hashing (`core/auth.py`).
- **No SQL injection surface.** Every query goes through SQLAlchemy with bound
  parameters. The one `text()` in the codebase is a static index predicate
  (`models/review_item.py`) with no interpolation. No f-string SQL anywhere.
- **No user enumeration by response.** Login returns the same
  "Invalid email or password" for an unknown account, a passwordless account and
  a wrong password. `forgot-password` always returns 202 with an identical body,
  and delivery failures are swallowed deliberately so the response cannot differ.
- **Session cookies** are `httponly`, `secure`, `samesite=lax` — which blocks
  cross-site POST, so CSRF is covered. 15-minute access token, 7-day refresh.
- **Edge headers**: HSTS with preload, CSP with `frame-ancestors 'none'`,
  `nosniff`, Cloudflare fronting.
- **Registration is invite-gated**, demo mode off.

A timing oracle does exist in code — a nonexistent email returns before Argon2
runs — but measured over the internet it is 0.75/0.75s for a real account versus
0.68/0.86s for a nonexistent one. Network jitter swamps it. Not worth fixing.

## Findings

| # | Finding | State |
|---|---|---|
| [#36](https://github.com/alcybersec/StudyAIO/issues/36) | Origin accepted traffic from any address, bypassing Cloudflare | Fixed on the VPS |
| [#39](https://github.com/alcybersec/StudyAIO/issues/39) | Every client shared one rate-limit bucket | Fixed (PR #40) |
| [#37](https://github.com/alcybersec/StudyAIO/issues/37) | No per-account brute-force throttle | Fixed (PR #43) |
| [#38](https://github.com/alcybersec/StudyAIO/pull/38) | Access log recorded no client address | Merged |

### The correction worth recording

My first probe of the rate limiter appeared to show correct per-IP bucketing:
one host at 429 while another still got 401. I reported that as sound. **It was
not.**

`--workers 2` with slowapi's default in-memory, per-process storage means each
worker holds its own counter, so a second source can land on the other worker
and look independent. The probe was too short to distinguish that from real
per-IP limiting.

Merging #38 settled it. One log line, from a request sent by `94.201.13.1`:

```json
{"path": "/api/access-log-probe-1788639515", "status_code": 404,
 "client_ip": "192.168.1.200", "event": "http_request"}
```

`192.168.1.200` is the inner proxy. Then the unambiguous experiment — fourteen
attempts from one source, then three from a host that had sent none:

```
source A: 401 401 401 401 401 429 429 429 429 429 429 429 429 429
source B: 429 429 429
```

**The generalisable rule:** any test of a rate limit that sends fewer than
`limit x worker_count` requests can produce a false pass. Exhaust from one
source with enough requests to fill every worker, then test from a second.

The related lesson is that the header-spoofing results I had treated as evidence
of safety (forged `X-Forwarded-For`, `X-Real-IP`, `True-Client-IP` and
`Forwarded` all failed to create new buckets) meant the opposite of what I
concluded: the header was being **discarded entirely**, not safely resolved.
There was no granularity to spoof around.

## What changed

**Infrastructure** (see the homelab runbook,
`sessions/2026-09-05_studyaio-security-hardening/`):

- Edge Caddy restricts the site to Cloudflare's ranges and aborts everything
  else, refreshed weekly with a guard against applying a truncated list.
- Edge Caddy overwrites `X-Forwarded-For` from `CF-Connecting-IP`; the inner
  Caddy passes it through instead of appending.

**This repo:**

- `client_ip` in the access log (#38).
- `--forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-127.0.0.1}` in the production
  compose, documented in `.env.example`, with a startup warning when the app is
  behind a proxy it has not been told to trust.
- `docs/deployment.md` gained a **Running Behind a Reverse Proxy** section. Its
  absence is part of why this happened.

### Ordering constraint

#36 had to land before #39's header change. `CF-Connecting-IP` is only
trustworthy because the origin now refuses non-Cloudflare traffic; trusting it
while the origin was open would have let anyone reaching the origin directly
forge their own address — evading the rate limit *and* poisoning the audit log.
Strictly worse than the original bug.

## Round two — full audit, 2026-09-06/07

The review above covered the login surface. A second pass audited the authenticated
surface, then the authentication *mechanisms*, then expanded test coverage. It found
substantially more than the first, and the pattern in *how* it found things is worth
as much as the findings.

### The dominant finding: one bug class, seventeen times

**Id-addressed lookups that never checked the owner.** Found in three waves:

| | Where | Count |
|---|---|---|
| #47 | `get_course_document` | 2 endpoints |
| #53 | review items, summaries, exams, schedules, assets, pipeline status | 6 clusters, 3 writes |
| #55 | the whole `courseops` router | 11 endpoints, 6 writes, +1 more found during the fix |

Six were **writes** — `DELETE /courseops/documents/{id}` let any user destroy another
user's document, and `POST /review-items/{id}/resolve` let one user resolve another's
item and restart their pipeline.

**Manual sweeps did not find these.** A brief that *explicitly asked* for a sweep of the
services layer returned six clusters and missed eleven in the very file the fix had just
edited. A route-walking guard found all eleven at once, and then its own blind spot
surfaced a twelfth.

### Findings a guard could not have caught

- **`GET /api/files/{file_type}/{path}` served user content to anonymous callers** (#66).
  Confirmed live: an unauthenticated request returned 28,915 bytes of generated study
  material, and the summaries path **was then** `<COURSE_CODE>/<COURSE_CODE>_Week<N>.md` —
  guessable, so the whole corpus was enumerable. Fixed and verified: the same request now
  401s, and #92 later re-keyed the path on a UUID, removing the enumerable half as a side
  effect. No code-shaped fallback was kept, deliberately: a fallback *would have been* the
  disclosure, because the caller genuinely owns a course by that code while the bytes
  belong to whoever ran last (`api/files.py:192-194`).
- **`GET /api/uploads/pipeline-events` streamed every user's events to any authenticated
  caller** (#69). A third shape: the endpoint *was* authenticated and had no object lookup
  to scope, so neither the authn nor the authz guard would ever have flagged it.
- **MFA backup codes were generated, displayed, stored in plaintext — and verified by
  nothing** (#71). A user was handed recovery codes that did not work, and losing a TOTP
  device was a permanent lockout.
- **OAuth bound to an existing local account by email** (#70) — the classic
  pre-account-takeover. Not exploitable here (both client IDs empty), so it was fixed
  before enabling rather than after an incident.
- **Service worker caches and the offline mutation queue survived logout** (#73). The
  read half leaked; the write half executed *user A's queued mutations as user B*.

### Verified sound, so the next audit does not repeat the work

SQL injection (parameterised throughout — `DROP TABLE` a no-op, payloads echoed as literal
text), path traversal in upload filenames (flattened into the uploads directory), stored XSS
via upload (`octet-stream` + `attachment` + `nosniff`), CORS from a foreign origin, invite-code
enumeration (exhausted and bogus codes byte-identical), JWT algorithm pinning and token-type
confusion (closed both directions), `tokens_valid_from` enforced on both token paths including
refresh, magic-link tokens hashed at rest with single-use and expiry, reset and verification
tokens non-interchangeable, and no endpoint anywhere accepting a client-supplied `user_id`.

### The structural lesson

Five guards now exist that did not before, and each catches what the others structurally
cannot:

1. **authz route walk** — every id-addressed endpoint rejects a foreign object
2. **authn route walk** — every non-public endpoint 401s an anonymous caller
3. **subscription scoping** — every `subscribe()` is handed the caller's identity
4. **the wiring-assertion convention** — documented in `developer_guide.md` §4
5. **the test storage floor** — `DATA_DIR` is redirected to a temp root and a non-temp root
   is *refused* (`services/app/conftest.py:116,154`). Redirect and refusal are separate on
   purpose: a redirect that stops working fails silently, and the refusal is what makes
   that loud.

That last one exists because, **six separate times**, a revert check showed the obvious
assertion still passing while the fix was reverted:

```
assert response.status_code == 404          <- still passes
> assert mock.await_args.kwargs.get("user_id") == default_test_user.id
E AssertionError: assert None == '00000000-...-0001'
```

Two traps are recorded with it: asserting a handler *mentions* `user.id` is insufficient
(one passed it to a logging call while its lookup was unscoped), and a status code with
several causes proves nothing (one test returned 400 from an ownership miss rather than the
branch it existed to test, and would have passed forever while testing nothing).

### Each test layer earned its place

Three findings were reachable only from one layer:

- **Route-walking guards** found eleven endpoints three targeted greps missed.
- **A real database** exposed a stale global `UNIQUE(sha256)` on `lecture_artifacts` (#80) —
  two users cannot upload the same file, and the error discloses that someone else already
  has it. `tests/unit` validates the model's `__table_args__`, which are correct; only the
  schema shows the divergence.
- **A real render** exposed that `queryClient.removeQueries()` drops queries out from under
  mounted observers, blanking the analytics page and dashboard widgets. Mocked `caches` and
  IndexedDB verify the purge *decides* correctly, not that it breaks the components around it.

### Deployment notes

- The embedding model could not load in the **api** container at all (uid 999, root-owned
  `/app`), so `POST /api/qa` had returned 500 and chat had answered with **no lecture
  context**, silently, since 2026-03-04. Fixed by baking the model into the image (#44/#46).
- `pytest tests/integration` did not run locally at all (#56) — testcontainers started
  Postgres but the app engine stayed on the compose default. Integration tests were written
  blind and verified only after push, which is exactly how one PR shipped a fixture that had
  encoded an IDOR.

## Round three — the same defect, one layer down

Twelve PRs merged after the round-two write-up: #84, #87, #88, #94, #95, #96, #98, #99, #102,
#104, #105, #106. **No new route-level IDOR was found.** What the work did instead was show
the same owner-less-namespace defect in places where there is no request to scope and nothing
fails closed.

### It was a chain, not a set — each fix's audit found the next member

```
#80/#84  UNIQUE(sha256) with no owner      -> unblocks the path to
#85/#95  chunks.stable_id with no owner    -> its audit finds
#92/#96  summaries/<CODE>/ with no owner   -> its audit finds
#97/#99  purge enumerating by artifact     -> its audit finds previews/ and courseops/
```

- **#80 was migration drift** — the model was right, the schema wrong (a `DROP CONSTRAINT`
  omitted while the same migration did it correctly for `courses` two lines above).
  **#85 was a design gap** — model *and* schema both wrong, and `chunks` has no `user_id`
  column at all. The dates settle it: `_build_stable_id` has one commit ever (`3b08d05`,
  2026-02-28); multi-tenancy landed 2026-03-04 and never touched `chunks`.
- The best one-line statement of the class came from #85's audit: at the **database** level
  `chunks.stable_id` was the last owner-less constraint over user data. The remaining
  instances live in **storage keys**, where there is no constraint to fail — so instead of
  crashing, they overwrite silently. #92 was exactly that: two users with `CSIT302` shared one
  key, the second run overwrote the first, `file_path` was stored on both rows, and nothing
  raised.
- **#97's lesson generalises best**: *artifact-scoped is not the same as reached*. The purge
  deleted `file_path` by exact key and swept two prefixes; `previews/v<N>/<artifact_id>.pdf`
  was neither, so nothing touched it — despite looking artifact-scoped.

**A namespace registry was deliberately rejected** (#99). It would make the sweep uniform but
cannot decide *whether* a namespace is owner-scoped, which is the actual judgement — and
`courseops/` must be excluded for a reason no registry could express. What was done instead is
the cheap half: `summary_key_prefix_for_course()` and `preview_keys_for_artifact()` live beside
their writers, so the writer and the purge cannot disagree.

Anchors: `services/app/app/services/index_service.py:27-44` ·
`services/app/app/services/summary_service.py:247-289` ·
`services/app/app/services/account_service.py:215-290` (its docstring is the best existing
statement of the rule) · `services/app/app/api/files.py:164-209`

### Transaction handling: `rollback()` alone is not enough

Six stages committed on a session already marked for rollback (#93/PR #102), so
`PendingRollbackError` replaced the typed error, the failure rows rolled back, and a
deterministic failure **retried twice** against an explicit intent not to. #104 then made
ingest a **seventh** caller of the shared helper — not because ingest had the commit bug, but
because its failure can arrive on a session poisoned by either of two flushes.

The non-obvious half, and why PR #54 looked at this code and correctly left it: the
`PipelineRun` was inserted by a `flush()` inside the rolled-back transaction, so the rollback
**un-inserts the row and expunges the object to transient** — `session.get()` returns `None`.
A handler that merely re-fetched would still have recorded nothing. The correct order is: read
identifiers off the ORM objects first (while that needs no SQL), roll back, re-materialise,
commit — and a failure inside the bookkeeping is logged and swallowed so it can never again
replace the stage's own error. See `app/pipeline/failures.py`.

### One missing `.lower()`, three failures

#91/PR #94. A case-only difference read as a change and ran the full `_repoint_email`:
sessions revoked, OAuth unlinked, magic links killed, `email_verified` cleared. The new casing
was then *stored*, and since every lookup was exact-match the user **could no longer log in** —
with no signal, because `forgot-password` returns 202 either way. It also partially reopened
#70, since `get_user_by_email` could not find a differently-cased account.

Two details worth keeping: the fix folds a case-only difference against a pre-migration row
**in place** rather than repointing it — otherwise the bug survives its own fix for exactly the
rows most likely to hit it. And the migration **aborts, naming every row**, if two accounts
already differ only by case, because merging them means choosing which keeps its sessions and
courses.

### The test suite was writing into real data

Not a near-miss. `settings.data_dir` defaults to `/app/data`, nothing set `DATA_DIR`, and the
integration suite had been writing test artifacts there **on every run** — caught live, nine
files in three batches of three, while #105 was being developed. The fixed branch added zero.
The deletion risk (`test_endpoint_authn_guard.py`'s walk requests `DELETE /api/auth/account`,
which runs `purge_user_storage` for real) was the sharper edge of the same missing isolation,
and the only thing preventing loss was UUID randomness.

The ordering constraint is #56 again: `settings` reads the environment once at import, so the
rootdir conftest **checks that no `app` module is in `sys.modules`** rather than assuming its
own timing.

### UI semantics lagging backend semantics

A security fix that changes what a control *does* creates a UI honesty bug. Twice:

- #76 made backup codes real; the login field was `maxLength={6}`/`inputMode="numeric"`, so a
  16-symbol code could not be typed at all (#77/PR #87).
- #88 gave admin mutations genuine destructive power; #98 then found the UI firing them from a
  `Select` and a wrapped `button` with **no confirmation at all**. And the PATCH response does
  not carry `sessions_revoked` even though the service logs it, so the UI could not have told
  the truth if it wanted to. #101 is the residue.

## Tests that passed for the wrong reason

The most transferable thread in this document. Each was caught by a revert check or by an
unrelated change disturbing the coincidence — none by reading the test, none by coverage.
All were *covering* their code; none was testing it.

1. **A status code from the wrong branch.** `test_dismiss_already_resolved_returns_400` (#58)
   asserted `400` — supplied by the **ownership miss**, not the already-resolved branch it
   existed to cover. PR #79 later retrofitted the *cause* to three more multi-cause 404s.
2. **A mock that answers regardless of the SQL.** PR #94: "an `AsyncMock` session returns
   whatever the test wired **regardless of the SQL it was handed** — every assertion here would
   have passed against the unfixed code." Fixed by answering from the statement's real bound
   parameters. Same class in `test_classify.py::test_error_message_stores_exception_not_artifact_id`
   (an `AsyncMock` has no pending-rollback state) and in `cli._ensure_admin`, where reverting
   the `commit()` failed both *integration* tests while the mock-based unit test stayed green.
3. **A hardcoded path that matched by accident.** `test_normalize_strips_data_dir` asserted
   against `/app/data`, which only matched *because nothing set `DATA_DIR`*. Pinning the root
   broke it. Its docstring now says it: *"the `/app/data` version of this assertion passed for a
   different reason than it claimed."*
4. **A deletion test that never looked at the disk.** `test_account_deletion.py` before #99
   asserted only on rows — which is precisely why summary files surviving deletion went
   unnoticed. The one on this list with a security consequence.

Also worth recording, though it left no artifact: while #73 was in development its
`extraction-images` test **passed under revert**, because its expectation was derived from the
same constant it was testing. It was rewritten before the commit, so the flawed version is not
in the history — a reminder that the revert check catches these *during* the work, which is the
only cheap moment.

A related shape, from #95: `_build_stable_id`'s format tests asserted the **old, broken** shape
as correct, restating the implementation's f-string using the test's own input. #85 predicted
this exact case before it was looked at.

## Corrections to this record's own issues

A review record that hides its own errors is not a review record. Every one of these was found
by someone reading the code rather than the issue.

| Issue | Claimed | True |
|---|---|---|
| #93 | Six files including `ingest.py` | `ingest.py` does **not** have the bug — it logs and re-raises without committing. `courseops_task.py` **does**, and was missed. Net six either way, one swapped for another |
| #97 | `previews/` "probably covered, verify" | **Not covered at all.** Now deleted by exact key across every cache version — not by prefix, because `delete_prefix` is backend-dependent and a `PREVIEW_CACHE_VERSION` bump orphans rather than removes |
| #85 | The global uniqueness existed for idempotent upserts | **Never implemented that way.** Idempotency is an artifact-scoped `DELETE`; there is no `ON CONFLICT` anywhere and `stable_id` is never a conflict target. `docs/PRD.md` stated the same false rationale |
| #85 | Existing rows need rewriting, or both shapes tolerating | `stable_id` is **write-only** — nothing reads it. Both shapes coexist; **code-only fix, no migration** |
| #103 | "A corrupt upload, an unreadable file, a storage error" become visible | Those are pre-artifact failures the `NOT NULL` FK cannot record, and mostly never reach ingest — the endpoint validates and stores *before* dispatching. The real gain is that a vanished artifact row or a flush error stops being invisible, including to `GET /uploads/{id}/status` |
| #68 | A push to `master` ships 233-commit-old code, reverting seven fixes | **Production was never at that risk** — the deploy job's own `if:` gate would have skipped. The real residual was a `workflow_dispatch` pushing a stale `:latest`. The substantive finding stands on other grounds: **a skipped job reports the run green** |
| #68 | `gh pr create` defaults to `master` | The default branch **is `main`, and always was**. A cause was inferred that fit the symptom and written up as fact; the actual reason PR #64 targeted `master` is still unknown |
| #100 | "Nothing was destroyed; safety came from id randomness" | True of the deletion hazard, understated overall — the suite had been writing into real data continuously |

Two process errors belong here too. The extension to #60 item 1 **was never posted to the
issue** — an agent was told to read a comment that did not exist, and worked from the brief
instead. And #60 item 3's "a form that submits every field" hazard was **hypothetical**: there
is no general edit form, while the live hazard ran the other way, from controls that commit on
change.

## Still open

| # | |
|---|---|
| **#90** | `main` has no branch protection, no rulesets: no required checks, no required PR, force-push permitted. The highest-value item here, and not code |
| **#101** | three fields the admin UI infers because the API does not surface them |
| **#89** | `ci.yml` still lists `master` (lines 9, 11) which no longer exists; `developer_guide.md:327` repeats it. Plus a decision on `develop` |
| **#63** | summary-backed review items are created silently and cannot be resolved — needs a product decision first |
| **#107** | `courseops/<sha256[:16]>_<name>` is content-addressed with no owner, so two users share one blob and it is deliberately excluded from the deletion purge. Needs refcounting or per-user keys |
| **#108** | 12 fixtures across 8 files patch `data_dir` without `reset_storage()`, so they no-op against the memoised singleton; `tests/unit` and `tests/golden` add no isolation of their own |

Nothing here is live-exploitable. **#90 is the one to read**: roughly thirty PRs were merged on
the convention of checking green first, with nothing enforcing it. PR #78 shipped a regression
that only E2E caught, with five of six checks green; PR #64 was merged against the wrong base
because nobody verified it. A security review whose own remediation record rests on a
convention rather than a gate should say so.
