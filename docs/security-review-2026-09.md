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
| [#39](https://github.com/alcybersec/StudyAIO/issues/39) | Every client shared one rate-limit bucket | Proxies fixed; app half in flight |
| [#37](https://github.com/alcybersec/StudyAIO/issues/37) | No per-account brute-force throttle | Open |
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
  material, and the summaries path is `<COURSE_CODE>/<COURSE_CODE>_Week<N>.md` — guessable,
  so the whole corpus was enumerable. Fixed and verified: the same request now 401s.
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

Four guards now exist that did not before, and each catches what the others structurally
cannot:

1. **authz route walk** — every id-addressed endpoint rejects a foreign object
2. **authn route walk** — every non-public endpoint 401s an anonymous caller
3. **subscription scoping** — every `subscribe()` is handed the caller's identity
4. **the wiring-assertion convention** — documented in `developer_guide.md` §4

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

## Still open

| # | |
|---|---|
| **#80** | stale global `UNIQUE(sha256)` — confirmed on production; fires when two users upload the same file. Pinned with `xfail(strict=True)` so it turns red when fixed. |
| **#82**, **#77** | login page has no UI for the backup-code login or the OAuth MFA challenge, and shows a misleading message for a refused OAuth link. Same shape; best done together. |
| #63 | summary-backed review items are created silently and cannot be resolved — needs a product decision first |
| #59 | no decompression bound on docx/pptx extraction |
| #60 | four deferred follow-ups from the beta hardening work |

Nothing in this list is live-exploitable. #80 is the highest priority because it is a plain
functional bug that will present as a broken upload to the first two testers who share a
lecture deck.
