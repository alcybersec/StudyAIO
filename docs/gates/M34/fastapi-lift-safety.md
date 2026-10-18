# M34-S2-SEC-007: safety review of the FastAPI lift

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** `bb922c3` on `hold/m34-fastapi`, "build(deps): lift the fastapi <0.137 cap to 0.143, walk lazy includes
in route guards". Cherry-picked cleanly onto `kit/retrofit` (base `be989a5`, later merged forward to `3f5e3ac`, which
brought in SEC-013/014 and touched no file in this change). fastapi 0.136.3 → 0.143.2, starlette 1.7.0 → 1.8.0, and the
lock re-resolved.

Reviewed against floor 1 and R-040, plus floors 2 and 3 for the auth libraries in the lock diff. I ran everything in a
fresh venv on Python 3.12, installed from `requirements-dev.txt` with the lock as constraints and the CPU torch extra
index the lock script uses. Installing pip-audit 2.10.1 into that venv added only pip-audit's own dependencies: every
locked pin stayed as locked.

## Verdict: **APPROVE**

The new walker returns the route a request actually runs. The sweep counts match the old walker on 0.136.3 exactly,
route by route. The hardened non-vacuity guard kills every mutant I tried, and the old walkers really do go blind on
0.143. Nothing in the lock diff weakens token handling. No finding blocks the change.

I added one pin, for the case the live app cannot exercise: include-level dependencies (section 1). Section 6 lists the
residuals.

## 1. Effective-route semantics

`tests/_routes.api_routes` yields one `RouteContext` per `APIRoute`, through `fastapi.routing.iter_route_contexts`.
I read the 0.143.2 source to see what each field resolves to:

- `RouteContext.__getattr__` and its properties read from the `_EffectiveRouteContext`. That object is built by
  `_EffectiveRouteContext.from_api_route`. It takes `include_context.path_for(route)` for the path (the prefixes of
  every enclosing include, joined) and `[*include_context.dependencies, *route.dependencies]` for the dependencies.
  It takes `response_model`, `methods` and `include_in_schema` from the route, ANDed with the include where that
  applies. The `dependant` that `_requires_user` walks is built from those combined dependencies.
- Nested includes are flattened by `_IncludedRouter.effective_route_contexts()`, which combines the include contexts
  on the way down.
- The request path dispatches on the same `_EffectiveRouteContext` objects (`matches`, and `app` is built from that
  context). So the guards inspect the object that serves the request, not a copy of it.
- `effective_route_contexts` leaves out `_low_priority_routes`. In 0.143.2 that list only ever holds the
  frontend-route group (`routing.py:2762`), and this app mounts none.

**Live app: identical to 0.136.3.** I installed fastapi 0.136.3 and starlette 1.7.0 into the review venv and ran the
pre-`bb922c3` `app.routes` walker. Then I restored 0.143.2 and ran `api_routes`. For every route I dumped method,
effective path, `response_model` and the full transitive dependency closure:

```
  174 deps_old_0.136.3.txt
  174 deps_new_0.143.2.txt
DEPS_IDENTICAL
SWEPT_IDENTICAL
REACHED_IDENTICAL
```

**Synthetic app: include-level dependencies.** `app/main.py` passes only `prefix` and `tags` to its 30
`include_router` calls. That means no live route can show whether include-level dependencies survive the walker. A
walker that dropped them would leave every live count unchanged. I built that mutant (effective path and response
model kept, include-level dependencies stripped from the dependant): it **passes**
`test_floor1_route_enumeration_is_not_vacuous`. If it shipped, a future
`include_router(r, dependencies=[Depends(get_current_user)])` would look anonymous to `_requires_user`. The tenant
sweep, the anonymous-caller pin and the consent gate would then all skip that route.

So I added `tests/safety/test_floor1_route_walker.py`. It builds a nested include (`/api` → `/outer` → `/inner`, with
`get_current_user` at the inner include) and checks two things:

- `…_returns_the_effective_route`: the walked route has the full prefixed path, its own `response_model`, and
  `_requires_user` true. As a control, the bare `original_route` has neither the prefix nor the dependency, and the
  old `app.routes` walk finds nothing.
- `…_dependency_is_the_one_the_request_runs`: the dependency the walker reports is enforced on a real request. The
  route returns 401 while `get_current_user` refuses, and runs the handler once it is satisfied.

Mutation check, in a scratch copy of `services/app` with `tests/_routes.py` replaced by a mutant selector:

| Mutant of `api_routes` | `test_floor1_route_walker.py` |
|---|---|
| none (control) | 2 passed |
| include-level dependencies dropped from the effective dependant | **1 failed**: "an include-level get_current_user is missing from the walked route's dependant" |
| bare `original_route` returned | **1 failed**: `['/inner/thing/{thing_id}'] == ['/api/outer/...']` |
| pre-SEC-007 `app.routes` walk | **1 failed**: `[] == ['/api/outer/...']` |

## 2. Sweep counts (R-040 lift rule)

I took these with a scratch test that calls `_sweep_routes` and `_run_sweep`, in the same way as the M33 gate. It is
not committed.

```
COUNTS api_routes=171 all_apiroutes=174 swept_pairs=135 owned_reached=113 violations=['GET /api/gamification/leaderboard'] parent_violations=[] parent_reached=113
OLDCOUNTS fastapi=0.136.3 all_apiroutes=174 api_routes=171 swept_pairs=135 owned_reached=113 violations=['GET /api/gamification/leaderboard']
```

| | M33 gate | Old walker, 0.136.3, this tree | `api_routes`, 0.143.2 |
|---|---|---|---|
| `/api` APIRoutes | 169 | 171 | 171 |
| All APIRoutes (plus the three `/health*`) | n/a | 174 | 174 |
| Swept method+path pairs | 133 | 135 | 135 |
| Pairs reaching an owned table | 111 | 113 | 113 |

**Nothing dropped.** The +2 against M33 is `GET` and `PATCH /api/onboarding` (`0df090a`, M34-S3-BACKEND-012). Both are
in the swept set and in the reached set. Backend's "routes 169→174" compares M33's `/api`-only count with an
all-routes count. Like for like, it is 169 → 171. The one violation is the ruled opt-in leaderboard
(`SWEEP_OPT_IN_CROSS_USER`), as at M33. The owned-parent pass has none.

## 3. Mutation check of the hardened non-vacuity guard

In a scratch copy (not the worktree), `tests/_routes.py` was replaced by a mutant selector, and
`test_floor1_route_enumeration_is_not_vacuous` was run against each mutant:

| Mutant | Result |
|---|---|
| none (control) | 1 passed |
| skip the onboarding router (2 operations) | **failed**: `OpenAPI documents operations the route walker misses: [('GET', '/api/onboarding'), ('PATCH', '/api/onboarding')]` |
| skip the feedback router (3) | **failed**: `… [('GET', '/api/admin/feedback'), ('PATCH', '/api/admin/feedback/{feedback_id}'), ('POST', '/api/feedback')]` |
| skip the courses router | **failed**: `… [('DELETE', '/api/courses/{course_code}'), ('GET', '/api/courses'), …]` |
| return the bare `original_route` | **failed**: `expanding app.routes yields only 0 /api APIRoutes (floor 130)` |
| pre-SEC-007 `app.routes` walk | **failed**: same |
| include-level dependencies dropped | passed: no live route has any, so section 1's pin covers it |

Skipping one small router stays above every count floor (171 − 2 > 130), so only the new OpenAPI cross-check catches
it. That is the part of the hardening that matters.

**The old walkers do go blind on 0.143.2.** On 0.143.2, `app.routes` is `['APIRoute', 'Route', '_IncludedRouter']`.
The old walker sees 3 APIRoutes (the `/health*` trio) and 0 under `/api`. Running the nine files as they were at
`be989a5` against 0.143.2: the floor-tier guards and the two unit guards fail loudly, because each has its own
non-vacuity floor (tenant isolation 3 failed, anonymous caller 2, consent gate 2, admin aggregates 2, unit consent
2, authn guard 3). One check passes vacuously: `test_no_response_model_carries_a_token_field` in the
secrets-at-rest contract. It walked zero `/api` routes and still went green. On `api_routes` it walks 174.

## 4. Lock diff

**pip-audit 2.10.1**, run through `scripts/audit-deps.sh pip` (the `+cpu` local versions stripped, `--no-deps
--disable-pip --strict`, and the allowlist has no `pip:` entries):

```
==> pip-audit (services/app/requirements.lock.txt)
No known vulnerabilities found
audit-deps.sh pip exit=0
```

For each library I diffed the sdist or wheel of the old pin against the new one. Where noted I compared ASTs with
docstrings stripped, which separates real changes from reformatting.

| Package | Change | Floor relevance |
|---|---|---|
| **authlib** 1.8.0 → 1.9.1 | The app uses only `AsyncOAuth2Client.fetch_token` and a userinfo `GET` (`app/core/oauth.py`). The app mints, stores and compares the state itself. On that path the only semantic change is `OAuth2Client.parse_response_token`: a token response that is not a JSON object now raises `HTTPStatusError` or `ValueError("Token endpoint response is not a JSON object (HTTP n).")`. Before, it raised from `resp.json()`. The app already sends `Accept: application/json`. The callback catches the error and redirects with `oauth_failed`, so it fails closed. The new message carries a status code, not the response body. The production log renderer is `JSONRenderer` with `format_exc_info`, so tracebacks do not include frame locals such as `client_secret`. The other semantic changes are in `jose`, `oidc`, OAuth 1, RFC 7521/7523/7592/9101 and a new `oauth2/drafts` package, none of which the app imports. | None |
| **google-auth** 2.61.0 → 2.62.0 | One change: `compute_engine.IDTokenCredentials` now binds ID tokens by default even when `GOOGLE_API_CERTIFICATE_CONFIG` is set. The app uses `google.oauth2.credentials` and `transport.requests` for Calendar (`gcal_service.py`), never compute-engine credentials. | None |
| **py-vapid** 1.9.4 → 1.9.6 | AST-equal apart from `utils.b64urldecode`, which now also accepts the standard base64 alphabet (`+`, `/`). ECDSA verification is unchanged. Key input is now more lenient; nothing is weakened. | None |
| **starlette** 1.7.0 → 1.8.0 | Multipart and form parsing close the request stream (`aclosing`). An unknown multipart charset now falls back to `latin-1` instead of being kept as given. `max_files`, `max_fields` and `max_part_size` are unchanged. `BaseHTTPMiddleware` forwards early hints. IPv6 hosts are bracketed in URLs. `SessionMiddleware` (not used here) now honours `max_age=0`. `StaticFiles` sends `Allow` on 405. | None. The four `BaseHTTPMiddleware` subclasses are covered by the unit tier |
| **fastapi** 0.136.3 → 0.143.2 | Lazy `include_router` (sections 1–3). | Covered above |
| multidict 6.9.1 → 7.1.0, aiohttp 3.14.4 → .5, boto3/botocore, filelock, pluggy, ruff, transformers, truststore, wrapt | Transitive, on the aiogram, S3 and ML paths. None handles credentials or request identity. | None found. pip-audit is clean |

## 5. Test evidence (review venv, fastapi 0.143.2, starlette 1.8.0)

Floor tier, run before the final `kit/retrofit` merge. That merge touched only `docs/risk-register.md` and
`tests/integration/test_oauth_flow.py`:

```
$ python -m pytest tests/safety -q --cov=tests/safety --cov-fail-under=95
TOTAL                                                    8332    185    98%
Required test coverage of 95% reached. Total coverage: 97.78%
756 passed, 1 skipped, 34 warnings in 480.57s (0:08:00)
```

Unit and contracts:

```
$ python -m pytest tests/unit tests/contracts -q --no-cov
3911 passed, 272 warnings in 268.82s (0:04:28)
```

Pins changed, all in `services/app/tests/safety/`:

- `test_floor1_route_walker.py`: new, two tests (section 1). Commit `ef29cc8`, with the two rows below.
- `test_floor1_tenant_isolation.py`: comments only. The `MIN_API_ROUTES` comment no longer says fastapi is capped
  below 0.137, and the non-vacuity docstring describes both checks. No assertion changed.
- `FLOORS.md`: the enumeration row is rewritten for the walker and the OpenAPI cross-check, and the two new pins are
  mapped.

## 6. Residuals (non-blocking)

1. **`architect`** (`tests/contracts/**`): in `test_secrets_at_rest_contract.py`,
   `test_no_response_model_carries_a_token_field` has no floor of its own. It went green walking zero routes on the
   old walker. It is safe now that it uses `api_routes`. Still, an `assert routes_checked >= N` beside it would make it
   fail on its own, without relying on the floor-1 guard in another file.
2. **Note**: `/api/billing/webhook` is the only `include_in_schema=False` API route, so the OpenAPI cross-check
   cannot see it on its own. It is public, so it is not in the sweep. Its billing siblings are documented, so skipping
   the billing router would still fail the check. If more hidden routes are added, the authn guard's exact public
   allowlist is what still covers them.
3. **Floor counts** (`MIN_API_ROUTES = 130`, `MIN_SWEPT_ROUTES = 100`, `MIN_ROUTES_WITH_OWNED_QUERIES = 90`) are left
   as they are. The OpenAPI cross-check is now the strong guard, and the floors only need to catch a blind walker.
