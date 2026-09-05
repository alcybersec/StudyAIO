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

## Still open

- **#37 — no per-account throttle.** Rate limiting keys on source address only.
  Once #39 lands, per-IP limiting works, but a distributed attacker still gets
  the full per-address allowance against a single account. Note that a hard
  account lock is itself a DoS vector: anyone who knows a tester's email can
  lock them out. Progressive delay is likely the better primitive, and any lock
  needs an operator unlock path that does not depend on the locked-out person's
  email.
- **Limiter storage is in-memory and per worker.** Redis is already in the
  stack. Until it is used, limits are effectively `2x` nominal and reset on every
  deploy.
- **Password floor is 8 characters** with no complexity or breached-password
  check.
- **MFA is implemented but unused** — 0 of 2 accounts. Worth enabling on the
  admin account before testers arrive.
- **CSP allows `'unsafe-inline'` for scripts**, weakening XSS defence.
