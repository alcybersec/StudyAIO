# ADR 0006 — Clock policy: user-local "today" for the study surface, UTC for quota and money

**Status** Accepted (2026-10-09, by the user) · **Date** 2026-10-09 · **Kit version** 1.10.3

**Ruling implemented:** `docs/decisions.md` § Rulings, 2026-10-09, "R-023 clock policy:
**per-user time zone** for user-facing 'today' (streaks, study history, daily challenge, due-today,
exam countdown, per-user analytics, reminder/digest send time at user's 08:00); **UTC** for daily
AI quota, billing, admin/platform stats; stored timestamps stay UTC. Zone stored in
`user_settings.timezone` (IANA, default `UTC`), auto-detected from the browser, user-editable"
(by: user). The ruling settles the substance; this ADR adds the boundary rules, the shared module
and its contract test.

## Context

StudyAIO asks "what day is it?" in three incompatible ways today. Re-derived on 2026-10-09 at
`ace89e6` by `tests/contracts/test_clock_contract.py` (the AST walk in §Enforcement):

| Way | Answers in | Sites |
|---|---|---|
| `date.today()` | the **container's** zone (UTC in the shipped images by accident, not by contract) | 18, in `quota_service`, `streak_service`, `challenge_service`, `study_service`, `analytics_service`, `admin_service`, `billing_service`, `courseops_service`, `calendar_service`, `chat_service` |
| naive `datetime.now()` | the container's zone, **without** a tzinfo | 6, in `chat_service` (4), `admin_service`, `courseops_service` |
| `datetime.now(UTC).date()` | UTC | `srs_service`, `exam_service`, `schedule_service`, `pipeline/notification_tasks.py`, and others |

None of them is the user's day. A student in Sydney (UTC+10/+11) who studies at 08:00 local is
studying "yesterday" by every one of them, so a streak breaks, a daily challenge belongs to the
wrong day, "due today" is off by one for half the day, and the 08:00 reminder arrives at 18:00 or
19:00. The beat schedule in `app/worker.py` fires reminders at fixed UTC hours for every user.

The opposite mistake is just as real for a different set of questions. The daily AI quota, the
usage records billing reads, and the admin's platform-wide numbers must use one day that every user
shares and no user can move.

## Decision

**1. Two kinds of "today", chosen by domain, never by convenience.**

| Domain | Day boundary | Notes |
|---|---|---|
| Streaks (`streak_service`) | **user-local** | consecutive local dates |
| Study history and sessions (`study_sessions.session_date`, `study_service`, timed sessions) | **user-local** | a session's date is the local date it started |
| Daily challenge (`challenge_service`, `daily_challenges.challenge_date`) | **user-local** | the user sees the challenge for *their* date; any generator of challenge rows must cover every date that is "today" somewhere, i.e. `utc_today() - 1` … `utc_today() + 1` |
| Due-today and the SRS day (`srs_service` `due_today`, deadlines "due today"/"overdue") | **user-local** | a card due at any instant of the local day counts as due today |
| Exam countdown and study schedule (`exam_service`, `schedule_service`) | **user-local** | days-until and the per-day plan count local dates |
| Per-user analytics (`analytics_service` per-user views, per-user `analytics_snapshots.snapshot_date`) | **user-local** | |
| Reminder, deadline-reminder and weekly-digest send time (`pipeline/notification_tasks.py`) | **user-local** | see Decision 5 |
| Daily AI quota (`quota_service`, `usage_records.record_date`) | **UTC** | see Decision 6 |
| Billing and usage records (`billing_service`, `usage_records`) | **UTC** | |
| Admin and platform-wide stats (`admin_service`, instance-wide analytics, `get_global_usage_today`) | **UTC** | one axis for all users |

A domain not in this table is UTC until an amendment of this ADR places it. A function that mixes
both (for example a per-user analytics view that also reads usage records) uses the zone each
domain prescribes for each part, and says so in a comment.

**2. Stored instants are always UTC-aware.** Every `DateTime` column is `timezone=True` and is
written with an aware UTC value (`utc_now()`). A zone is used **only** to answer a date-boundary
question: "which local date is this instant?", or "which UTC instants fall on local date D?". The
zone is never stored with the instant, and an instant is never converted to local time before it
is stored.

`Date` columns hold a calendar date with no zone. Which calendar it is follows the table:
`session_date`, `challenge_date` and per-user `snapshot_date` hold the user's local date at the
time of writing; `usage_records.record_date` holds the UTC date; `deadlines.due_date` holds the
date the user typed, compared with `user_today(tz)`.

**3. A local-day range query converts the bounds, never the column.** "Sessions today" is the
half-open interval `[local midnight of D, local midnight of D+1)` in the user's zone, converted to
UTC and compared with the stored UTC instants. SQL that casts a `timestamptz` to a date
(`func.date(col)`, `col::date`, `date_trunc('day', col)`) answers in the database session's zone
and is not used for a user-local question. A day across a DST change is 23 or 25 hours long; the
bounds computed from local midnights handle that and a fixed `timedelta(days=1)` from UTC does not.

**4. The zone.** `user_settings.timezone` holds an IANA key (`Europe/Berlin`), `NOT NULL`, default
`'UTC'`. The SPA reads `Intl.DateTimeFormat().resolvedOptions().timeZone` and, while the stored
value is still the default `UTC`, offers or sends it; the user can change it in Settings at any
time.

* **On write** the API rejects a key for which `valid_timezone` is false (422). Validation is by
  membership in `zoneinfo.available_timezones()`, not by "`ZoneInfo(key)` did not raise", so
  path-like or host-specific keys (`/etc/localtime`, `localtime`, `../x`) are refused.
* **On read** an absent, `None` or invalid value (a row written before the column existed, a key
  dropped by a later tzdata) is treated as `UTC`, silently, by the clock module. A bad zone
  degrades a user to UTC; it never raises in a request or a beat task.
* `tzdata` is a declared dependency of `services/app`, so the key set does not depend on the base
  image shipping `/usr/share/zoneinfo`.

A zone change is **not retroactive**. Dates already written stay as written; only questions asked
after the change use the new zone. The change can move one day boundary by at most 26 hours
(UTC−12 to UTC+14). For streaks and challenges that is accepted: they are low-value, and the
leaderboard is opt-in (R-007). For quota it is not: see Decision 6.

**5. Notifications go out at the user's 08:00; the beat becomes hourly.** The three reminder
tasks (daily reminder, deadline reminder, weekly digest) run every hour at minute 0 instead of at
fixed UTC hours. Each run selects the users whose `user_now(tz).hour == 8`; the weekly digest also
requires the local weekday to be Sunday. (The digest moves from 09:00 to the user's 08:00, as
ruled.) Users in a :30 or :45 zone receive theirs at 08:30 or 08:45 local; that is accepted rather
than running the beat every 15 minutes. Each send is idempotent per
`(user_id, notification kind, user-local date)`, so a retried or duplicated beat run, or a zone
change during the day, does not send twice. Backup and calendar-sync schedules are unchanged.

**6. Quota, billing and platform stats stay on UTC, and this is a security decision.** The zone
is user-supplied and unverified. If the daily AI quota reset at the user's local midnight, a user
could exhaust today's quota, switch their zone from `Etc/GMT+12` to `Pacific/Kiritimati` and be in
"tomorrow" immediately, getting a fresh allowance, then switch back and repeat. Each round trip
buys another full quota, spent on the instance's AI credentials, which `quota_service` and
`get_global_usage_today` exist to cap. Pinning the quota day to UTC gives every user the same
24-hour window, which no setting can move. Billing and usage records are UTC for the same reason
and because they reconcile against providers who bill in UTC. Admin and platform stats are UTC so
a "day" means the same instants for every user they aggregate. The UI may show the user when their
quota resets in local time; the reset itself is UTC midnight.

**7. One clock module.** `app/core/clock.py` (owner `backend`, layer `core`, so every layer may
import it under ADR 0002) is the only place that reads the host clock. It uses `zoneinfo` only. Its
public surface is exactly the block below. Helpers are private (`_`-prefixed), including any module
logger. `user_now` and `user_today` take the zone **without** a default, so a caller cannot ask a
user question and silently get UTC by forgetting the argument: it must pass `settings.timezone`
(or, deliberately, `None`).

```python
from datetime import date, datetime

#: Files under services/app/ allowed to read the host clock directly.
CLOCK_EXEMPT = {"app/core/clock.py"}


def utc_now() -> datetime:
    """The current instant, aware, tzinfo UTC. Use for every stored timestamp."""


def utc_today() -> date:
    """The current UTC calendar date. Quota, billing, admin and platform stats."""


def user_now(tz: str | None) -> datetime:
    """The current instant, aware, in zone `tz`; UTC when `tz` is None or invalid."""


def user_today(tz: str | None) -> date:
    """The user's current local calendar date; UTC's when `tz` is None or invalid."""


def valid_timezone(tz: str) -> bool:
    """True iff `tz` is a key of zoneinfo.available_timezones(). Never raises."""
```

## Enforcement

`services/app/tests/contracts/test_clock_contract.py` (owner `architect`) parses this ADR's one
`python` block and checks:

1. **No ambient clock reads.** Every `.py` under `services/app/app/` is walked with `ast`,
   function-local code and lambdas included, except the files in `CLOCK_EXEMPT`. These are banned,
   in any import spelling (`datetime.datetime.now()`, `dt.date.today()`,
   `from datetime import datetime as D; D.utcnow()`) and as uncalled references
   (`default=datetime.utcnow`):
   `date.today()`, `datetime.today()`, `datetime.utcnow()`, and `datetime.now()` with no zone or
   with `None`. The detector is tested on a planted file containing each form.
2. **The surface.** The public top-level names of `app/core/clock.py` equal the five stubs above,
   and each signature (parameter names, annotations, defaults, return annotation) matches as source
   text.
3. **Semantics callers rely on.** Results are aware; `None`, `""`, an unknown key and a path-like
   key all fall back to UTC; `valid_timezone` returns a bool for hostile input and never raises.

The test was committed red (M32-S2-ARCH-033), listing the 24 sites in the table under Context, and
goes green when `backend` lands `clock.py` and converts them.

**What the test cannot see.** An aware read such as `datetime.now(UTC).date()` is syntactically
fine but semantically wrong when it answers a user-local question. Those sites (the third row
under Context: `srs_service`, `exam_service`, `schedule_service`, `notification_tasks`) are
converted by the implementing tasks against the table in Decision 1, and reviewers check new code
against it. Aware `datetime.now(UTC)` stays legal outside `clock.py`, so ORM column defaults in
`app/models/**` need not change. New code uses `utc_now()`.

## Consequences

- Follow-up tasks, one per owner: `data` adds `user_settings.timezone` and its migration; `backend`
  writes `clock.py`, converts `app/services/**` and `app/api/**`, and validates the settings field;
  `ai` makes the beat hourly in `app/worker.py` and converts `app/pipeline/**`; `frontend`
  auto-detects and edits the zone; `devops` (or `backend`) declares `tzdata` as a direct
  dependency. `safety` reviews the quota rule and the zone validation.
- Every user-local service function gains access to the caller's zone, by reading
  `user_settings.timezone` once per request or task, not once per row.
- Tests that freeze time must freeze `app.core.clock`, not `datetime`, which is one patch point
  instead of many.
- A local-day bounds helper (`(tz, date) -> (start_utc, end_utc)`) is the obvious next member of
  the surface. It is not in v1; adding it amends Decision 7 and this block first.

## Alternatives considered

- **UTC everywhere.** Simple, and wrong for the core study loop: streaks and reminders follow the
  user's waking day, not Greenwich's. Rejected by the ruling.
- **User-local everywhere, including quota.** It invites the zone-hopping abuse in Decision 6.
  Rejected.
- **Store the zone on each row.** That doubles every date column for a question the settings row
  already answers, and still needs a rule for which zone a cross-row query uses. Rejected.
- **Derive the zone from the request (`Accept-Language`, IP geolocation).** Neither is available in
  a beat task, and both are guesses. Rejected: the browser detects the zone once and the user owns
  it from then on.
