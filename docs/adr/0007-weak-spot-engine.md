# ADR 0007 — Weak-spot engine: per-week weakness score, a daily "study tonight" plan, targeted generation in the worker

**Status** Accepted (user, 2026-10-15) · **Date** 2026-10-12 · **Kit version** 1.10.3

**Ruling implemented:** `docs/decisions.md` § Rulings, 2026-10-11, the M33 strategic bet: "the
weak-spot engine (audit §5, MKT-03): practice generated from each student's own mistakes, review
state and exam dates" (by: user). Task M33-S2-ARCH-018 (GL#39). This ADR decides the model; the
user accepts it before `data`, `backend`, `ai` and `frontend` start.

## Context

The audit (`docs/audits/2026-10-10-product-audit.md` §5) observed that StudyAIO already stores
every quiz answer, the SM-2 state of every reviewed card and the user's exam dates, and uses none
of them to decide what to practise next. Re-derived on 2026-10-12 at `a7eca25`:

| Input | Where | What it really holds | Limits |
|---|---|---|---|
| Quiz answers | `quiz_attempts` (`is_correct`, `created_at`, `quiz_question_id`) | every answer ever given, append-only | **no `user_id`**: owner is `quiz_questions.course_id → courses.user_id` (courses are single-owner today) |
| Quiz items | `quiz_questions` (`course_id`, `week`, `source_artifact_id`, `source_page_ref`, `archived_at`) | `week` is `NOT NULL` on every row | no concept/topic tag, no `user_id` (owner via course) |
| Card items | `flashcards` (`course_id`, `week`, `tags`, `source_page_ref`, `archived_at`) | `week` `NOT NULL` | `tags` is free AI output, not linked to `concepts` |
| SM-2 state | `flashcard_reviews` (`user_id`, `ease_factor`, `interval_days`, `repetition_count`, `next_review_at`, `last_reviewed_at`) | **current state only**, one row per card, created on first review | no review log and no lapse counter; a failed review resets `repetition_count` to 0 and lowers `ease_factor` (`srs_service.calculate_sm2`) |
| Exams | `exams` (`user_id`, `course_id`, `exam_date`, `weeks_scope`, `status`) | scope is a week list | `exam_service.days_until` clamps a past exam to 0 |
| Concepts | `concepts` (`user_id`, `course_id`, `name`, `source_weeks`, `mention_count`) | best-effort, extracted at the end of the assets stage; failures are swallowed | sparse; not linked to any quiz item or card |
| Source text | `extractions` (per artifact, page markers), `chunks` (`artifact_id`, `page_ref`, `slide_title`) | the week is on the artifact (`lecture_artifacts.week`) | chunks have no `week` column |
| Existing scoring | `readiness_service.score_week` / `exam_service.get_weak_topics` | per-week: weak if all-time accuracy < 70 % or mean ease < 2.0 | no recency, no exam weighting, no minimum evidence, exam-scoped only |
| Usage | `usage_events` (`study_plan_viewed` is already a client event), `ai_feedback` | retention readout per signup cohort (`services.usage v1`) | |

Three facts shape the decision. **Week is the only unit every item carries.** Concepts exist for
some artifacts and are attached to no item, so a per-concept score today would be a score of
nothing for most users. **Evidence is thin and old.** A student answers a handful of questions per
week, weeks apart, so an all-time accuracy ranks a week failed in September above one failed
yesterday, and three answers carry the same weight as thirty. **Generation must not move into the
request.** ADR 0003 enumerates five request-time `get_agent` sites; a sixth needs an amendment and
the user's agreement, and the work (one adapter call, then validation and dedup) has no reason to
hold an API worker.

## Decision

### 1. The unit of weakness is (user, course, week); concepts are labels inside a week

A weak spot is a `(user_id, course_id, week)` triple. Every quiz question and card has a non-null
`week`, so every piece of evidence lands in exactly one unit, and the heatmap the frontend draws is
course × week. Concepts are **not scored** in v1. They are used inside a weak week as topic
labels: the targeted-generation request names the topics a generated item should aim at
(Decision 5), and each generated item stores the label it targeted (`focus_topic`, Decision 6).

That label is what makes a per-concept score possible later: once targeted items carry a topic and
have attempts, `(user, course, concept)` can be scored with the same formula. Doing so amends this
ADR; it is not in v1.

The weeks of a course are the union of the weeks of its summaries and of its active quiz questions
and cards. Archived courses are excluded.

### 2. The score: a deterministic formula, no AI

The scorer is a pure function `score_week(quiz, cards, days_to_exam)` in `weakspot_service`. The
service fetches the evidence with owner-scoped queries and hands plain values to it, so the formula
is unit-testable without a database and gives the same answer for the same input on every call.

**Quiz evidence.** Every attempt on a question of the unit (archived questions included: an
answer is history of the user's knowledge of that week, whatever later happened to the item) with
age ≤ `QUIZ_WINDOW_DAYS`. Age is `(utc_now() - created_at)` in fractional days, floored at 0;
it is an elapsed time, not a calendar question, so it needs no zone.

* weight `w = 0.5 ** (age_days / QUIZ_HALF_LIFE_DAYS)`: an answer two weeks old counts half.
* accuracy `acc = (Σ w·correct + QUIZ_PRIOR_WEIGHT · QUIZ_PRIOR_ACCURACY) / (Σ w + QUIZ_PRIOR_WEIGHT)`,
  a Beta-style prior worth two answers at 50 %, so three answers cannot move the score to 0 or 1.
* quiz weakness `q = 1 - acc`, in (0, 1). Absent when there is no attempt in the window.

**Card evidence.** Every `flashcard_reviews` row of the user for an **active** card of the unit
(an archived card's state is no longer scheduled). A card that was never reviewed is not evidence.

* ease term `e = clamp((EASE_CEILING - ease_factor) / (EASE_CEILING - EASE_FLOOR), 0, 1)`;
* lapse term `l = 1` when `repetition_count == 0`, else `0`. A review row exists only after a
  review, and SM-2 resets the count to 0 only on a failed one, so this reads "the last review of
  this card failed". It replaces a lapse counter the schema does not have (Alternatives);
* overdue term `o = clamp(overdue_days / max(1, interval_days), 0, 1)`, where
  `overdue_days = max(0, utc_now() - next_review_at)` in days: a card a full interval late is
  as forgotten as SM-2 can tell;
* card weakness `CARD_EASE_WEIGHT·e + CARD_LAPSE_WEIGHT·l + CARD_OVERDUE_WEIGHT·o`; the unit's
  card weakness `f` is the mean over its cards. Absent when there is none.

**Combination.** `evidence = (attempts in the window) + (reviewed active cards)`.

* `evidence < MIN_EVIDENCE` → status **`unknown`**, weakness `None`, priority `0.0`. An unknown
  unit is never shown or ranked as weak (Decision 3).
* otherwise each source is weighted by how much of it there is, saturating at
  `EVIDENCE_SATURATION`: `wq = min(Σ w, 5) / 5` (decayed weight, so old answers count less here
  too), `wf = min(cards, 5) / 5`, and `weakness = (wq·q + wf·f) / (wq + wf)` over the sources
  present. Range [0, 1].
* `confidence = min(1, evidence / CONFIDENCE_FULL_EVIDENCE)`; reported, not used for ranking.
* status, on the rounded weakness: **`weak`** ≥ `WEAK_THRESHOLD`, **`solid`** < `SOLID_THRESHOLD`,
  **`shaky`** between.

**Exam proximity.** `days_to_exam` is the number of user-local days to the **soonest** exam of the
course with `status == "active"`, `week ∈ weeks_scope` and an exam local date ≥ the user's today,
computed with `exam_service.days_until(exam_date, tz)` (ADR 0006: exam countdown is user-local).
An exam whose local date has passed is ignored, not counted as 0 (`days_until` clamps to 0, so the
caller filters first). No such exam: `None`.

* `urgency = 0.5 ** (days_to_exam / EXAM_HALF_LIFE_DAYS)`, or `0.0` when `None`: 1 on exam day,
  0.5 a week out, 0.06 a month out.
* `priority = weakness · (1 + EXAM_URGENCY_GAIN · urgency)`: at most three times the weakness on
  exam day. Priority ranks; weakness is what the heatmap shows.

**Numbers.** Everything is computed in floats and each output (`weakness`, `confidence`,
`urgency`, `priority`) is rounded with `round(x, SCORE_DECIMALS)` once, at the end; status is
decided on the rounded weakness. **Ties** (equal rounded priority) break by weakness descending,
then `days_to_exam` ascending with `None` last, then course code ascending, then week ascending.
The order is total, so a plan built twice from the same evidence is the same plan.

The surface and the constants are the contract; `services/app/tests/contracts/test_weakspot_service_contract.py`
parses this block and compares it with `app/services/weakspot_service.py`:

```python
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import QuizQuestion
from app.models.study_plan import StudyPlan
from app.models.targeted_generation import TargetedGeneration

# Scoring (Decision 2)
QUIZ_WINDOW_DAYS = 90
QUIZ_HALF_LIFE_DAYS = 14.0
QUIZ_PRIOR_ACCURACY = 0.5
QUIZ_PRIOR_WEIGHT = 2.0
EASE_CEILING = 2.5
EASE_FLOOR = 1.3
CARD_EASE_WEIGHT = 0.5
CARD_LAPSE_WEIGHT = 0.3
CARD_OVERDUE_WEIGHT = 0.2
EVIDENCE_SATURATION = 5.0
MIN_EVIDENCE = 3
CONFIDENCE_FULL_EVIDENCE = 8
WEAK_THRESHOLD = 0.40
SOLID_THRESHOLD = 0.25
EXAM_HALF_LIFE_DAYS = 7.0
EXAM_URGENCY_GAIN = 2.0
SCORE_DECIMALS = 4

# Cold start (Decision 3)
DIAGNOSTIC_QUESTIONS = 3
DIAGNOSTIC_QUESTIONS_MAX = 5
DIAGNOSTIC_URGENCY = 0.5

# "Study tonight" (Decision 4)
DEFAULT_PLAN_MINUTES = 25
MIN_PLAN_MINUTES = 10
MAX_PLAN_MINUTES = 90
MAX_PLAN_ITEMS = 20
FOCUS_WEEKS = 3
REVIEW_SHARE = 0.5
PLAN_ALGORITHM_VERSION = 1

# Targeted generation (Decision 5)
TARGETED_KINDS = ("quiz", "flashcards")
TARGETED_ITEMS_PER_REQUEST = 5
TARGETED_GENERATIONS_PER_DAY = 6
TARGETED_AI_CALLS = 1
DEDUP_JACCARD = 0.8


@dataclass(frozen=True)
class QuizEvidence:
    is_correct: bool
    age_days: float


@dataclass(frozen=True)
class CardEvidence:
    ease_factor: float
    repetition_count: int
    interval_days: int
    overdue_days: float


@dataclass(frozen=True)
class WeekScore:
    status: str
    weakness: float | None
    confidence: float
    urgency: float
    priority: float
    evidence: int


@dataclass(frozen=True)
class WeekWeakSpot:
    course_id: str
    course_code: str
    week: int
    score: WeekScore
    exam_id: str | None
    days_to_exam: int | None


def score_week(
    quiz: list[QuizEvidence], cards: list[CardEvidence], days_to_exam: int | None
) -> WeekScore: ...


def is_duplicate(candidate: str, existing: list[str]) -> bool: ...


async def get_weak_spots(
    session: AsyncSession, *, user_id: str, tz: str | None, course_id: str | None = None
) -> list[WeekWeakSpot]: ...


async def get_tonight_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int = DEFAULT_PLAN_MINUTES
) -> StudyPlan: ...


async def refresh_tonight_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int | None = None
) -> StudyPlan: ...


async def get_diagnostic_questions(
    session: AsyncSession, *, user_id: str, course_id: str, week: int
) -> list[QuizQuestion]: ...


async def request_targeted_generation(
    session: AsyncSession, *, user_id: str, user_tier: str, course_id: str, week: int, kind: str
) -> tuple[TargetedGeneration, bool]: ...


async def get_targeted_generation(
    session: AsyncSession, generation_id: str, *, user_id: str
) -> TargetedGeneration | None: ...
```

**Worked examples.** Ages in days, cards as `(ease_factor, repetition_count, interval_days,
overdue_days)`. The contract test evaluates `score_week` on every row (tolerance 1e-4).

| Case | quiz (correct, age) | cards | days_to_exam | status | weakness | confidence | urgency | priority |
|---|---|---|---|---|---|---|---|---|
| A | none | none | None | unknown | None | 0.0 | 0.0 | 0.0 |
| B | (F,0) ×2 | none | 3 | unknown | None | 0.25 | 0.743 | 0.0 |
| C | (F,0) ×3 | none | None | weak | 0.8 | 0.375 | 0.0 | 0.8 |
| D | (T,0) ×3 | none | None | solid | 0.2 | 0.375 | 0.0 | 0.2 |
| E | (T,0) ×3, (F,0) ×2 | none | 7 | weak | 0.4286 | 0.625 | 0.5 | 0.8571 |
| F | (F,28) ×3 | none | None | weak | 0.6364 | 0.375 | 0.0 | 0.6364 |
| G | none | (1.3,0,1,0), (1.7,0,1,2), (2.5,4,30,0) | None | weak | 0.5444 | 0.375 | 0.0 | 0.5444 |
| H | (F,0), (F,7), (T,14), (T,21) | (2.0,1,1,3), (2.6,3,15,0) | 1 | weak | 0.4228 | 0.75 | 0.9057 | 1.1887 |
| I | (F,100) ×5, (T,0) ×3 | none | None | solid | 0.2 | 0.375 | 0.0 | 0.2 |
| J | (F,0) ×3 | none | 0 | weak | 0.8 | 0.375 | 1.0 | 2.4 |
| K | (T,0) ×4, (F,0) ×2 | none | None | shaky | 0.375 | 0.75 | 0.0 | 0.375 |

(B: two answers are below `MIN_EVIDENCE` however wrong. F: the same three misses as C, four weeks
older, score lower. I: answers outside the window are not evidence at all. G: a card with ease
above the ceiling clamps to `e = 0`.)

### 3. Cold start: "unknown" is not "weak"; a diagnostic uses existing items first

A unit is **unknown** when it has fewer than `MIN_EVIDENCE` pieces of evidence, and **weak** only
when it has enough evidence and a weakness ≥ `WEAK_THRESHOLD`. The heatmap shows unknown as its
own state (not as red), and the API returns `weakness: null` for it.

The **diagnostic** for a unit is up to `DIAGNOSTIC_QUESTIONS_MAX` of its **existing active quiz
questions**, ordered: never attempted by the user first, then fewest attempts, then `created_at`,
then `id`. Answers go through the existing `POST /api/study/quiz-attempt`, so a diagnostic is just
evidence. When the unit has fewer than `DIAGNOSTIC_QUESTIONS` active questions the response says
`needs_generation: true` and the client may request a targeted `quiz` generation for the unit
(Decision 5) — **only on a user action**, behind consent and quota. Nothing generates on its own
for a cold-start user.

### 4. "Study tonight": one frozen plan per user per local day

The plan answers "what should I do tonight, in about 25 minutes?". It is built from the scores
above and the existing items; it calls no AI.

**Build** (pure and deterministic given the evidence, the local date and `minutes`):

1. **Focus weeks**: the top `FOCUS_WEEKS` units by the Decision 2 order whose status is `weak` or
   `shaky`, across all the user's courses.
2. **Diagnostic week** (at most one): among `unknown` units with ≥ 1 active quiz question, the one
   with the highest urgency, then the Decision 2 tie order. It is included when there are fewer
   than `FOCUS_WEEKS` focus weeks **or** its urgency ≥ `DIAGNOSTIC_URGENCY` (an exam within a
   week). It contributes `DIAGNOSTIC_QUESTIONS` questions, first.
3. **Budget**: `minutes` (default `DEFAULT_PLAN_MINUTES`, clamped to
   [`MIN_PLAN_MINUTES`, `MAX_PLAN_MINUTES`]), with item costs from `timed_session_service`
   (`MINUTES_PER_CARD = 2`, `MINUTES_PER_QUIZ = 3`, one source of truth). After the diagnostic,
   `REVIEW_SHARE` of what remains (floored to whole minutes) goes to review and the rest to
   practice; minutes one half cannot use pass to the other.
   * **review**, in order: due cards (due by the end of the user's local day, ADR 0006) of focus
     weeks by week priority, then `next_review_at`, then `id`; then due cards of other weeks.
   * **practice** (active questions only), in order: focus-week questions whose latest attempt by
     the user was wrong (`missed`), oldest miss first; then focus-week questions never attempted, `origin='targeted'`
     before `origin='pipeline'`, then `created_at`, `id` (`new` / `targeted`).
4. At most `MAX_PLAN_ITEMS` items. Each item records `item_type` (`card` | `quiz`), `item_id`,
   `course_id`, `week`, `reason` (`diagnostic` | `missed` | `review` | `new` | `targeted`) and
   `minutes`.

**Frozen per day.** The first `GET` on a user-local date (ADR 0006: the study surface is
user-local) builds the plan and stores it (`study_plans`, Decision 6); later reads that day return
the stored plan. A plan does **not** reshuffle while the user works through it: an item's `done`
flag is derived on read (a card reviewed, or a question attempted, at or after the plan's
`built_at`), and items that were archived or whose course was deleted since are dropped on read.
`POST …/refresh` rebuilds it on demand (after a targeted generation completes, or when everything
is done) and increments its `version`. A new local date builds a new plan; earlier plans stay.

The scores themselves are **not cached**: they are derived on every read of the heatmap. A
`study_plans` row is the only stored output of the engine besides generated items.

### 5. Targeted generation runs in the worker; ADR 0003 is unchanged

**Where.** A Celery task, `app.pipeline.targeted_task.generate_targeted_items(generation_id)`, in
`app/pipeline/targeted_task.py`, is the only new `get_agent` caller. The request handler never
obtains an adapter: it validates, records a `targeted_generations` row and enqueues the task.
**No new request-time call site; ADR 0003's allowlist is unchanged.** The task registers with
Celery, which is what `safety`'s floor-3 test requires of a pipeline module that calls `get_agent`.

**Request path** (`POST /api/weak-spots/targeted`, body `{course_id, week, kind}`, `kind` in
`TARGETED_KINDS`), in this order:

1. `require_ai_consent` as a route dependency (`api.ai-consent v1`): 403 before anything else.
2. The course is the caller's and the week has a processed artifact of the caller's: else 404.
3. An in-flight generation (`queued` or `running`) for the same `(user, course, week, kind)`:
   return it with `200` instead of creating another. The database enforces this (partial unique
   index, Decision 6), so two concurrent clicks cannot both enqueue.
4. Daily cap: the caller has fewer than `TARGETED_GENERATIONS_PER_DAY` rows created on the current
   **UTC** day, else `429` code `targeted_daily_cap`. UTC, not local: the cap guards AI spend, and
   ADR 0006 Decision 6 puts every spend limit on UTC so a zone change cannot reset it.
5. `quota_service.check_ai_quota(session, user_id, user_tier, calls=TARGETED_AI_CALLS)`: the
   existing quota and instance ceiling errors and handlers apply unchanged.
6. Insert the row (`status='queued'`), commit, then `generate_targeted_items.delay(row.id)`;
   respond `202`.

**Worker path.** The task takes the row id only (primitive argument), opens its own session and
reads the owner from the row (as the pipeline stages read it from the artifact).

* **Target artifact**: the unit's processed artifact of the owner with the most questions the
  owner missed (latest attempt wrong) in the last 30 days; ties by newest `created_at`, then `id`.
  One artifact, so every page reference is unambiguous.
* **Prompt inputs** (`GenerationFocus`, see `pipeline.targeted_generation v1` in
  `docs/CONTRACTS.md`): `topics`, up to 5: the `slide_title`s of the chunks at the pages of the
  owner's recently missed questions, then the unit's concepts by `mention_count` (case-insensitive
  dedup); `missed_questions`, up to 5 stems the owner got wrong (stems only, never the owner's typed
  answer); `avoid`, up to 30 stems/fronts of the unit's active items; `page_refs`, the pages of the
  missed questions. The source text is the target artifact's extraction, with its page markers,
  and the unit's summary, which is what `generate_quiz`/`generate_flashcards` already take. Chunks
  supply the topic labels; the extraction supplies the text, so a citation is a page of the
  extraction.
* **Adapter**: `generate_quiz(..., focus=...)` or `generate_flashcards(..., focus=...)`, an additive
  keyword on the two existing methods (`agents.AgentAdapter` v2), rendered from new templates
  `prompts/generate_targeted_quiz.txt` and `generate_targeted_flashcards.txt`, so the untargeted
  prompts and their eval baseline do not move. Count `TARGETED_ITEMS_PER_REQUEST`. Usage is metered
  with `billing_service.record_agent_usage` as in the assets stage.
* **Citation rule** (GL#34 standard: every item cites its slide): an item whose `source_page_ref`
  is not a page of the target extraction is dropped (`dropped_uncited`). Kept items store the
  target artifact as `source_artifact_id`.
* **Dedup**: an item is dropped (`dropped_duplicate`) when `weakspot_service.is_duplicate(stem,
  existing)` is true against the unit's active items and the batch's earlier items. Normalise
  (casefold, non-alphanumerics to spaces, collapse whitespace), then duplicate when the normalised
  strings are equal or the Jaccard similarity of their word sets is ≥ `DEDUP_JACCARD`. Deterministic,
  no embedding call.
* **Store**: insert-only into `quiz_questions` / `flashcards` with `origin='targeted'`, the row's
  `targeted_generation_id`, `focus_topic` (the topic the model says it targeted, else the first
  topic), and the unit's current maximum `generation_version` (a targeted item joins the current
  generation; only a pipeline regeneration bumps it). Then the row becomes `completed` with its
  counts, or `failed` with an `error_code` (no provider text, floor 2). Transient adapter errors
  retry per `pipeline/resilience.py`.

### 6. Storage: scores derived on read; two new tables; provenance on items

**Scores are derived on read**, not materialised. Per user the data is small (courses × weeks in
the tens, attempts in the hundreds to low thousands); the read is three owner-scoped grouped
queries (attempts in the window joined to their questions and courses; review rows joined to active
cards and courses; active exams) and a Python pass. A `topic_mastery` table was rejected for v1
(Alternatives). If the `studyaio_weakspot_score_seconds` p95 exceeds 250 ms in production, a
per-user cache invalidated by attempts, reviews and exam edits is the follow-up, not a table.

**New tables** (owner `data`; every row carries `user_id NOT NULL` → `users.id`, floor 1):

* `study_plans`: `id`, `user_id`, `plan_date` (`Date`, the user-local date, ADR 0006 Decision 2),
  `minutes`, `items` (JSONB list, Decision 4), `focus` (JSONB: the focus and diagnostic units with
  their scores at build time), `algorithm_version`, `version` (refresh count, from 1), `built_at`,
  `created_at`, `updated_at`. Unique `(user_id, plan_date)`.
* `targeted_generations`: `id`, `user_id`, `course_id` → `courses.id`, `week`, `kind`, `status`
  (`queued` | `running` | `completed` | `failed`), `requested_count`, `created_count`,
  `dropped_duplicate_count`, `dropped_uncited_count`, `topics` (JSONB list of labels),
  `error_code` (nullable), `created_at`, `updated_at`, `completed_at`. Index
  `(user_id, created_at)` for the daily cap; partial unique index on `(user_id, course_id, week,
  kind)` where `status in ('queued', 'running')`.

**New columns** on `quiz_questions` and `flashcards`: `origin` (`String(20)`, `NOT NULL`, server
default `'pipeline'`, values `pipeline` | `targeted`), `targeted_generation_id` (nullable FK →
`targeted_generations.id`), `focus_topic` (`String(200)`, nullable). Existing rows backfill to
`pipeline` through the server default.

**Index for the scoring query**: `quiz_attempts (quiz_question_id, created_at)`. The others it
needs exist (`quiz_questions (course_id, week)`, `flashcard_reviews (user_id)`,
`exams (user_id)`).

**Not changed**: `quiz_attempts` gets no `user_id` in v1. Ownership through the question's course
is exact while courses are single-owner. Shared course spaces (audit PROD-04) would break that
for attempts and reviews alike and must add `user_id` to `quiz_attempts` first; recorded under
Consequences.

### 7. API, events, metrics

All routes require a caller; every lookup carries `user_id` (floor 1); a foreign or absent id is
`404`, never `403`. Full shapes in `docs/CONTRACTS.md` `api.weak-spots v1`.

| Route | Purpose |
|---|---|
| `GET /api/weak-spots` (`course_id?`) | the heatmap: per course, per week, status, weakness, confidence, priority, the evidence counts and the next exam |
| `GET /api/weak-spots/diagnostic` (`course_id`, `week`) | Decision 3 question ids and `needs_generation` |
| `POST /api/weak-spots/targeted` | Decision 5; consent-gated, quota-checked, capped |
| `GET /api/weak-spots/targeted/{generation_id}` | status and counts of one of the caller's generations, with the created item ids |
| `GET /api/study-plan/tonight` (`minutes?`) | today's plan, built on first read (Decision 4) |
| `POST /api/study-plan/tonight/refresh` (`minutes?`) | rebuild today's plan |

**Events** (`services.usage v1`, additive): server-side `study_plan_built` (properties `count`,
`duration_seconds` = planned minutes × 60) on a build or refresh, and
`targeted_generation_requested` (`count`, `week`) on a `202`. `study_plan_viewed` stays a client
event, sent when the plan is on screen. No content and no topic labels in properties.

**Metrics** (the observability rule: they land with the feature): `backend` adds
`studyaio_weakspot_score_seconds` (histogram, heatmap and plan scoring),
`studyaio_study_plan_builds_total{outcome=built|refreshed|reused}` and
`studyaio_targeted_requests_total{kind,outcome=queued|existing|capped|quota|not_found}`; `ai` adds
`studyaio_targeted_generations_total{kind,outcome=completed|failed|retried}`,
`studyaio_targeted_items_total{kind,outcome=saved|dropped_duplicate|dropped_uncited}` and
`studyaio_targeted_generation_seconds` (histogram). No `user_id` label. Structured logs
`weakspot_scored`, `study_plan_built`, `targeted_generation_{queued,completed,failed}` carry ids
and counts only.

**Frontend needs**: a "Study tonight" dashboard card (plan items run through the existing study
runner by id, as `POST /api/study/timed-plan` results do), a course × week heatmap with the four
states, a diagnostic entry point on unknown weeks, a "practise this week" action that requests a
generation and polls its status, then offers the refresh; consent and quota errors use the existing
dialogs.

### 8. Floors

* **Floor 1.** Both new tables carry `user_id NOT NULL`; every service function takes `user_id`
  as a required keyword (C6); item, attempt and review evidence is joined through
  `courses.user_id`; the worker reads the owner from the generation row and loads only that
  owner's course, artifact, attempts and concepts. No endpoint returns a cross-user aggregate; the
  only cross-user number is the admin retention split (Decision 9), which reports counts, as the
  existing readout does. `safety`'s scoping guards cover the new routes automatically.
* **Floor 2.** The worker resolves credentials through `get_user_ai_context`; a failure stores an
  `error_code`, never provider text. No credential, prompt or lecture text in logs or metrics.
* **Floor 3.** One new `get_agent` caller, in `app/pipeline/targeted_task.py`, a registered
  Celery task. No request-time site is added; ADR 0003 is unchanged. The targeted route is consent-
  gated and quota-checked; `safety`'s derived consent guard catches it because it reaches
  `check_ai_quota` and `.delay`.
* **Floor 4.** Generation only inserts. It never updates, archives or deletes an existing item, and
  dedup drops new candidates, never existing items. **The pipeline's asset regeneration
  (`asset_service.save_flashcards` / `save_quiz_questions`) must archive only `origin='pipeline'`
  items**, so re-running a lecture does not retire the user's targeted practice; archiving
  (`archived_at`) is still the only retirement and keeps attempts and reviews. `study_plans` rows
  are derived scheduling data, not user content; a refresh rewrites today's row in place, and rows
  are removed only by account deletion.

### 9. Evaluation

* **Scoring** is pinned by the worked examples above (contract test) and by `backend`'s unit tests
  for the plan builder: determinism (same evidence, same plan), the budget split, ordering and ties,
  user-local day boundaries, archived items dropped.
* **Targeted generation** (`ai`, `services/app/evals/`): at least 10 synthetic cases, each a short
  multi-page extraction plus a focus (topics, missed stems, `avoid`). Scored deterministically:
  *on-topic* (the item's cited page is a page of a focus topic, or its stem or answer contains a
  focus term) ≥ 0.8 of kept items; *citation validity* 1.0 after the drop rule, with the drop rate
  reported; *dedup* (no kept item duplicates `avoid`) ≥ 0.95; plus structure (fields, types). Run in
  CI with a stored baseline, as the summary eval does (M33-S1-AI-012).
* **Gate metric** (M33 gate: "D7/D30 of users with a plan reported against those without"): the
  admin retention readout gains a split per signup cohort, **with plan** = the user has a
  `study_plans` row dated within days 0–6 after signup, **without** = the rest; `d7`/`d30` keep the
  `services.usage v1` definitions. This is a correlation: users who open a plan are more engaged to
  begin with. A causal answer needs a holdout (Open questions).

## Consequences

- **Tasks** (one per owner, `docs/strategy.md` §11 S2): `data` adds the two tables, the three item
  columns and the attempts index (M33-S2-DATA-019); `backend` writes `weakspot_service`, the
  routes, the domain errors, the two usage events, the metrics, account deletion of the new rows,
  the `origin='pipeline'` filter in `asset_service` regeneration and the retention split
  (M33-S2-BACKEND-020); `ai` adds `GenerationFocus`, the `focus` keyword on all backends, the two
  templates, `targeted_task` and its eval cases, and bumps `agents.AgentAdapter` to v2 in
  `docs/CONTRACTS.md` in the same change (M33-S2-AI-021); `frontend` builds Decision 7's surfaces
  (M33-S2-FRONTEND-022); `qa` covers attempts → scores → plan → targeted quiz end to end
  (M33-S2-QA-023); `safety` reviews floors 1, 3 and 4 and the spend path (M33-S2-SAFETY-024).
- **Two weakness notions coexist** until a follow-up: exam readiness (`readiness_service`,
  `GET /api/exams/{id}/weak-topics`) keeps its all-time 70 %/2.0 rule. Moving it onto
  `score_week` changes a shipped number and is its own task.
- **Shared course spaces need `quiz_attempts.user_id` first** (Decision 6). Until then, an attempt's
  owner is its course's owner.
- **A per-concept score** is the natural v2 once targeted items carry `focus_topic` and have been
  answered; it amends Decision 1.
- **Constants are tuning, not truth.** The half-lives, thresholds and weights are first guesses.
  Changing one is a one-line change plus the ADR block and examples, which the contract test keeps
  in step, and bumps `PLAN_ALGORITHM_VERSION` so stored plans say which rule built them.

## Alternatives considered

- **Per-concept as the primary unit.** The most precise unit, and the one marketing would name.
  Rejected for v1: concepts are best-effort and attached to no item, so most evidence would have no
  unit. Week is solid today; concepts enter as labels and grow into a unit (Decision 1).
- **Both units at once, blended.** Doubles the scoring and the UI for a signal that is mostly
  absent. Rejected for v1.
- **Reuse `readiness_service.score_week`.** No recency, no minimum evidence, no exam weighting, and
  all-time accuracy lets one bad week in September outrank yesterday. Rejected; the new scorer is
  separate and readiness can move onto it later.
- **An AI-judged weakness** (ask the model which topics the user is weak at). Non-deterministic,
  costs quota on every read, and cannot be unit-tested. Rejected: no AI in scoring.
- **Add a lapse counter to `flashcard_reviews`.** More exact than "last review failed", but it
  starts at 0 for every existing card and needs a write-path change in `srs_service`. Rejected for
  v1; ease already falls with every failure, and the proxy is exact about the most recent review.
- **A materialised `topic_mastery` table** updated on each attempt and review. Fast reads, but it
  needs recompute triggers on attempts, reviews, exam edits, archive and regeneration, and goes
  stale when any is missed or when the clock alone changes the score (decay, overdue, exam
  proximity all move without a write). Rejected for v1 on volume (Decision 6).
- **Recompute the plan on every read.** Always fresh, but the list reorders under the user mid-
  session. Rejected for a frozen daily plan with live `done` flags and an explicit refresh.
- **Generate at request time** (a sixth ADR 0003 site). Gives the items in the response, but holds
  an API worker for a provider call, needs an ADR 0003 amendment and the user's agreement, and
  buys nothing the job-and-poll flow does not. Rejected.
- **A new table for generated items.** Keeps targeted items apart, but every study flow, the SRS,
  attempts, feedback and exports read `quiz_questions` and `flashcards`. Rejected for provenance
  columns on the existing tables.
- **Generate automatically for every weak week** (nightly beat). Spends the user's quota and the
  instance's credentials without a request, and before consent is certain for the batch. Rejected:
  generation is always a user action.

## Open questions for the user

1. **Holdout.** Hide "Study tonight" from a deterministic 10 % of new users (by a hash of the user
   id) so D7/D30 with vs without the plan is causal rather than a correlation? It costs those users
   the feature for the milestone.
2. **Daily cap.** `TARGETED_GENERATIONS_PER_DAY = 6` (each one AI call of 5 items) on top of the
   tier's AI quota. Keep, or tie it to the tier?
3. **Default budget.** 25 minutes, with 2 minutes per card and 3 per question (the timed-session
   costs). Is 25 the right evening default?
