# Contracts

Every interface crossing a role boundary is recorded here **before** it is implemented: shape,
version, and what changed.

## Current

### agents.AgentAdapter v2

The single interface every AI call in StudyAIO goes through (floor 3, `docs/strategy.md` §6).
Provider: `ai` — `services/app/app/agents/base.py` (the ABC and its data types) and
`services/app/app/agents/factory.py` (`get_agent`, the only sanctioned way to obtain an instance).
Recorded as-built on 2026-10-04: v1 is the interface that already shipped with M1–M30, not a new
design. Decided in [ADR 0002](adr/0002-module-boundaries.md).

v2 (2026-10-15, additive): `generate_flashcards` and `generate_quiz` gain a trailing
`focus: GenerationFocus | None = None` keyword and the `GenerationFocus` data type is added, for
targeted generation ([ADR 0007](adr/0007-weak-spot-engine.md) Decision 5,
`pipeline.targeted_generation v1`). Every v1 caller is unaffected: `focus` defaults to `None`, and
`None` selects the same template and produces the same output as v1.

The block below is the contract. `services/app/tests/contracts/test_agent_adapter_contract.py`
parses it and compares it, signature by signature and field by field, against the source — so
changing either side without the other fails the suite. A change to anything in it is a version
bump here first.

```python
class AgentAdapter(ABC):
    # Abstract: every backend implements all seven.
    @abstractmethod
    async def classify_lecture(
        self, text_preview: str, filename: str, known_courses: list[str]
    ) -> ClassificationResult: ...

    @abstractmethod
    async def generate_summary(
        self, extraction: ExtractionData, existing_summary: str | None
    ) -> SummaryResult: ...

    @abstractmethod
    async def generate_flashcards(
        self,
        summary: str,
        extraction: ExtractionData,
        count: int,
        focus: GenerationFocus | None = None,
    ) -> list[FlashcardData]: ...

    @abstractmethod
    async def generate_quiz(
        self,
        summary: str,
        extraction: ExtractionData,
        count: int,
        focus: GenerationFocus | None = None,
    ) -> list[QuizQuestionData]: ...

    @abstractmethod
    async def answer_question(self, question: str, context_chunks: list[dict]) -> AnswerResult: ...

    @abstractmethod
    async def extract_course_ops(
        self, document_text: str, course_code: str, document_type: str
    ) -> CourseOpsResult: ...

    @abstractmethod
    async def extract_concepts(
        self, text: str, existing_concepts: list[str] | None = None
    ) -> ConceptExtractionResult: ...

    # Concrete: async generator; the default yields answer_question()'s answer whole.
    async def stream_answer(
        self, question: str, context_chunks: list[dict]
    ) -> AsyncIterator[str]: ...

    # Metering: consumers read `usage` after a call, then `reset_usage()`.
    @property
    def usage(self) -> "TokenUsage": ...

    def reset_usage(self) -> None: ...

    # Output language: set by get_agent; applied by content methods only.
    @property
    def output_language(self) -> str | None: ...

    def set_output_language(self, language: str | None) -> None: ...

    def language_directive(self) -> str: ...

    def with_language(self, prompt: str) -> str: ...


def get_agent(
    user_settings: dict[str, Any] | None = None,
    output_language: str | None = None,
) -> AgentAdapter: ...


@dataclass
class ClassificationResult:
    course_code: str
    week: int
    title: str
    confidence: float
    reasoning: str = ""


@dataclass
class SummaryResult:
    content_md: str
    embedded_images: list[str] = field(default_factory=list)


@dataclass
class FlashcardData:
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    source_page_ref: int = 1


@dataclass
class QuizQuestionData:
    question_type: str
    question: str
    options: list[str] | None = None
    correct_answer: str = ""
    explanation: str = ""
    source_page_ref: int = 1


@dataclass
class GenerationFocus:
    topics: list[str]
    missed_questions: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    page_refs: list[int] = field(default_factory=list)


@dataclass
class AnswerResult:
    answer: str
    citations: list[dict] = field(default_factory=list)


@dataclass
class ExtractionData:
    pages: list[dict]
    metadata: dict


@dataclass
class CourseOpsAssessment:
    title: str
    assessment_type: str
    weight_pct: float | None = None
    description: str = ""
    weeks_relevant: list[int] = field(default_factory=list)


@dataclass
class CourseOpsDeadline:
    title: str
    due_date: str
    deadline_type: str
    description: str = ""


@dataclass
class CourseOpsResult:
    assessments: list[CourseOpsAssessment] = field(default_factory=list)
    deadlines: list[CourseOpsDeadline] = field(default_factory=list)
    course_info: dict = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class ConceptData:
    name: str
    description: str
    category: str = "general"


@dataclass
class ConceptRelationData:
    source: str
    target: str
    relation_type: str = "related_to"
    confidence: float = 0.8


@dataclass
class ConceptExtractionResult:
    concepts: list[ConceptData] = field(default_factory=list)
    relations: list[ConceptRelationData] = field(default_factory=list)


@dataclass
class TokenUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
```

**Semantics the signatures do not carry**

- `get_agent` raises `ProviderCredentialError` when `user_settings` names a provider but holds no
  credential for it. It never falls back to the instance credential (issue #30).
- `classify_lecture`, `extract_course_ops` and `extract_concepts` return records the app parses, so
  they never apply the output-language directive. The four content methods do.
- Every override keeps the base signature exactly: same parameter names, order, annotations and
  defaults. Consumers call with keyword arguments (`text=`, `existing_concepts=`, …).
- `focus=None` is v1 behaviour exactly. A non-`None` focus selects the targeted template
  (`generate_targeted_quiz.txt` / `generate_targeted_flashcards.txt`); every backend honours it.
- `refreshed_credentials` is **not** part of v2. Only `ClaudeCodeAdapter` sets it, and consumers
  read it with `hasattr`. Promoting it to the ABC is a v3 change.

**Backends** — each one a concrete subclass, selected by `agent_backend`:

| `agent_backend` | Class | Module |
|---|---|---|
| `claude_code` | `ClaudeCodeAdapter` | `services/app/app/agents/claude_code.py` |
| `anthropic_api` | `AnthropicAPIAdapter` | `services/app/app/agents/anthropic_api.py` |
| `openai` | `OpenAIAdapter` | `services/app/app/agents/openai_adapter.py` |
| `zai` | `ZaiAdapter` | `services/app/app/agents/zai_adapter.py` |
| `ollama` | `OllamaAdapter` | `services/app/app/agents/ollama_adapter.py` |

Consumers: `ai`, `backend`. Every module outside `app/agents/` that imports this contract's
types or `get_agent`, or duck-types an adapter, is listed below. The contract test re-derives the
import-based part of this list from the source and fails on any module missing from it.

| Module | Owner | Uses |
|---|---|---|
| `services/app/app/pipeline/classify.py` | `ai` | `get_agent`, `classify_lecture`, `usage` |
| `services/app/app/pipeline/summarize.py` | `ai` | `get_agent`, `generate_summary`, `usage` |
| `services/app/app/pipeline/assets.py` | `ai` | `get_agent`, `generate_flashcards`, `generate_quiz`, `usage` |
| `services/app/app/pipeline/courseops_task.py` | `ai` | `get_agent`, `extract_course_ops`, `usage` |
| `services/app/app/pipeline/targeted_task.py` | `ai` | `get_agent`, `generate_flashcards`, `generate_quiz`, `GenerationFocus`, `ExtractionData`, `usage` |
| `services/app/app/services/concept_service.py` | `backend` | `get_agent`, `extract_concepts`, `ConceptExtractionResult` |
| `services/app/app/services/chat_service.py` | `backend` | `get_agent`, `answer_question`, `stream_answer` |
| `services/app/app/services/asset_service.py` | `backend` | `FlashcardData`, `QuizQuestionData` |
| `services/app/app/services/courseops_service.py` | `backend` | `CourseOpsResult` |
| `services/app/app/services/summary_service.py` | `backend` | `ExtractionData` |
| `services/app/app/services/billing_service.py` | `backend` | `usage`, `reset_usage` (duck-typed, no import) |
| `services/app/app/api/qa.py` | `backend` | `get_agent`, `answer_question` |
| `services/app/app/api/settings.py` | `backend` | `get_agent`, `classify_lecture` |

Indirect consumers, reaching the adapter through a service above:
`services/app/app/api/chat.py` (via `chat_service`), `services/app/app/api/concepts.py` and
`services/app/app/pipeline/concepts_task.py` (via `concept_service`).

**Floor 3.** Resolved by [ADR 0003](adr/0003-floor3-request-time-ai-calls.md) (Accepted
2026-10-04): every AI call goes through this contract via `get_agent`, and `get_agent` is called
only in `app/pipeline/**` and at five request-time call sites the ADR enumerates —
`api/qa.py` `ask_question`, `api/settings.py` `test_ai_connection`, `services/chat_service.py`
`send_message` and `stream_message`, and `services/concept_service.py`
`extract_and_save_concepts`. A new request-time call site amends that ADR; it is not a change to
this contract.

### core.clock v1

The only module that reads the host clock (ruling R-023). Provider: `backend` —
`services/app/app/core/clock.py`. Consumers: every layer (it is in `core`, ADR 0002); first users
are `app/services/**`, `app/api/**` and `app/pipeline/**`. Decided in
[ADR 0006](adr/0006-clock-policy.md), whose single `python` block **is** the contract: five
functions, `utc_now() -> datetime`, `utc_today() -> date`, `user_now(tz: str | None) -> datetime`,
`user_today(tz: str | None) -> date`, `valid_timezone(tz: str) -> bool`. `None` or an invalid zone
means UTC; results are aware. Not duplicated here, so there is one copy to keep in step.
`services/app/tests/contracts/test_clock_contract.py` compares that block with the source and bans
`date.today()`, `datetime.today()`, `datetime.utcnow()` and naive `datetime.now()` everywhere else
under `app/`. A new public member is a version bump here and an amendment of ADR 0006 first.

### api.ai-consent v1

AI-processing disclosure and consent (SEC-08, GL#38). Provider: `backend` —
`services/app/app/services/consent_service.py`, `app/api/deps.py` (`require_ai_consent`),
`app/api/auth.py`. Consumers: `frontend` (disclosure dialog), `safety` (floor 2 pin), `qa`.

- Storage: `users.ai_processing_consent_at` (timestamptz) and `users.ai_processing_consent_version`
  (smallint), both NULL until consented. Current wording version: `AI_CONSENT_VERSION` (int, default 1).
- `POST /api/auth/consent` (caller required). Optional body `{"version": int}`: a value other than
  the current version is refused 409 so a stale page cannot consent to wording it did not show.
  Records now and the current version. Response `{"ai_consent_required": false, "ai_consent_version": n}`.
- `GET /api/auth/me` (and every `UserProfileResponse`) gains `ai_consent_required: bool`: true when
  the timestamp or version is NULL, or the version is below the current one, and
  `ai_consent_version: int`, the CURRENT required disclosure version (`AI_CONSENT_VERSION`, not the
  user's stored one), so a client can echo it to `POST /api/auth/consent` on every path. The raw
  record is not exposed.
- Gate: every route that spends AI or enqueues AI pipeline work for the caller declares
  `dependencies=[Depends(require_ai_consent)]` and refuses **403** with body
  `{"detail": ..., "code": "ai_consent_required", "consent_version": n}` before any quota check, spend or
  enqueue. Routes: `POST /api/settings/test-ai`, `/api/chat/sessions/{id}/messages` and `.../messages/stream`,
  `/api/qa/ask`, `/api/concepts/extract/{id}`, `/api/uploads`, `/api/uploads/batch`,
  `/api/uploads/capture`, `/api/uploads/{id}/retry`, `/api/artifacts/{id}/reclassify`,
  `/api/review-items/{id}/resolve`, `/api/courses/{code}/merge`, `/api/courseops/documents`.
- Single-user mode: the operator is treated as consented (`ai_consent_required` is always false).
- Logging: no log line carries an email address. Call sites log `user_id`; the structlog processor
  `app.core.logging.redact_emails` and the stdlib `EmailRedactingFilter` redact any address-shaped
  value as defence in depth.

### api.ai_feedback v1

Per-item thumbs up/down on AI output (M33-S1-BACKEND-015, GL#36). Provider: `backend` —
`services/app/app/api/ai_feedback.py`, `services/app/app/services/ai_feedback_service.py`. Consumer:
`frontend`. Storage: `ai_feedback` (`AIFeedback`), unique on `(user_id, target_type, target_id)`;
the database enforces none of the value rules, the service does. Distinct from the app-bug
`POST /api/feedback`.

| Endpoint | Body / query | Result |
|---|---|---|
| `PUT /api/feedback` | `{target_type, target_id, rating, reason?, comment?}` | `200` `{target_type, target_id, rating, reason, comment, course_id, updated_at}`; replaces the caller's earlier vote |
| `DELETE /api/feedback/{target_type}/{target_id}` | none | `204`; removes the caller's own vote, `404` when there is none |
| `GET /api/feedback/mine` | `target_type`, repeated `target_ids` (max 100) | `200` `{items: [vote]}` — only the caller's votes |
| `GET /api/admin/ai-feedback` (admin) | `days` (1-365, default 30) | `200` `{total, by_target_type, by_reason, by_rating, recent_negative: [{target_type, reason, comment, course_id, created_at}]}` — no user ids or emails |

Rules: `target_type` in `AI_FEEDBACK_TARGET_TYPES`; `rating` is `1` or `-1`; `reason` in
`AI_FEEDBACK_REASONS` and only with `-1`; `comment` at most 1000 characters. A target that does not
exist **and** one owned by someone else both return `404` (no existence probe), resolved through the
owner-scoped getters (floor 1). `course_id` is inferred from the target, never taken from the
client. The admin route lives at `/admin/ai-feedback` because `/admin/feedback` is the app-bug
inbox. `answer` resolves to an assistant `chat_message`. Account deletion removes the rows
(`user_id` column).

**Study cards (M34-S3-BACKEND-012; no interface change, so no version bump).** The study surfaces
(Study hub review, timed and plan runs) rate a card with `flashcard` and a question with
`quiz_question`, the card's or question's own id, exactly as the week tabs do. That is `frontend`
work; the backend already serves it. The owner-scoped getters skip archived rows, so a vote on a
card or question archived after it was shown (`api.study-items`) is `404`; the control treats that
as "item gone", not as an error to retry.

`POST /api/qa/ask` answers are **not** rateable, by decision (2026-10-16): no UI calls that route,
so there is no `qa_answer` target type, no `qa_answers` table and no `answer_id` on `QAResponse`.
`AI_FEEDBACK_TARGET_TYPES` stays the five v1 types. Revisit only if a QA surface ships.

### services.usage v1

Per-feature usage events for retention (M33-S1-BACKEND-016, GL#37). Provider: `backend` —
`services/app/app/services/usage_service.py`, `services/app/app/api/usage.py`. Storage:
`usage_events` (`UsageEvent`), append-only.

`usage_service.record(session, user_id, event, *, course_id=None, properties=None) -> bool` — flushes
one row inside a savepoint and **never raises into the caller**: an unknown event, bad properties
or a database error is logged, counted (`studyaio_usage_events_total{outcome}`) and returns
`False`. The caller owns the commit. `event` is one of `USAGE_EVENTS`; `properties` has at most 8
keys from `ALLOWED_PROPERTY_KEYS`, values are `bool`, `int`, `float` or a short
`[a-z0-9_.-]` token (at most 40 characters). No free text, no content, no PII.

| Endpoint | Body / query | Result |
|---|---|---|
| `POST /api/usage-events` | `{event, course_id?}`; `event` in `summary_viewed`, `study_plan_viewed` only | `204`; rate limited; `course_id` must be the caller's (`404` otherwise) |
| `GET /api/admin/usage/retention` (admin) | `weeks` (1-26, default 8) | `200` `{cohorts: [{week_start, signups, d1, d7, d30}], features: [{week_start, event, active_users}]}` |

A cohort is the users who signed up in an ISO week (UTC, Monday). `dN` is the number of cohort
users with any event on day N after signup (calendar day offset from the signup date, UTC); a
cohort whose first possible signup day has not yet reached day N reports `null` for `dN`. Admin and demo accounts are excluded. Server
side events are emitted where the action happens: flashcard review, quiz answer, study session,
chat send, upload accepted, AI feedback. Account deletion removes the rows (`user_id` column).

**Pending additive change (M33-S2, [ADR 0007](adr/0007-weak-spot-engine.md) Decisions 7 and 9),
recorded before implementation:** `USAGE_EVENTS` gains the server events `study_plan_built`
(properties `count`, `duration_seconds`) and `targeted_generation_requested` (`count`, `week`);
`CLIENT_EVENTS` is unchanged. `GET /api/admin/usage/retention` gains `plan_split: [{week_start,
with_plan: {users, d7, d30}, without_plan: {users, d7, d30}}]`, where *with plan* means a
`study_plans` row dated within days 0–6 after signup, and `d7`/`d30` keep the definitions above.
Still v1: both are additions.

### services.weakspot v1

Per-(user, course, week) weakness scores, the daily "study tonight" plan, the cold-start diagnostic
and the request side of targeted generation (M33-S2, GL#39). Provider: `backend` —
`services/app/app/services/weakspot_service.py`. Consumers: `backend` (`app/api/weakspots.py`),
`ai` (`app/pipeline/targeted_task.py` calls `is_duplicate`), `qa`. Decided in
[ADR 0007](adr/0007-weak-spot-engine.md), whose single `python` block **is** the contract: the
scoring, cold-start, plan and generation constants, the `QuizEvidence` / `CardEvidence` /
`WeekScore` / `WeekWeakSpot` dataclasses, the pure `score_week` and `is_duplicate`, and six async
functions, each taking `user_id` as a required keyword. Not duplicated here, so there is one copy
to keep in step. The ADR's worked-examples table pins the formula's numbers.
`services/app/tests/contracts/test_weakspot_service_contract.py` compares the block and the table
with the source. The module may have more public names than the block (helpers, metrics); it may
not lack or change one. A changed constant or signature is an amendment of ADR 0007 and a version
bump here first.

### api.weak-spots v1

HTTP surface of the weak-spot engine (M33-S2, GL#39). Provider: `backend` —
`services/app/app/api/weakspots.py` (one router, both prefixes). Consumers: `frontend`, `qa`.
Every route requires a caller (`get_current_user_or_default`), passes `user_id=user.id` to the
service lookup, and answers a foreign or absent id with `404`. `tz` comes from `get_user_tz`
(ADR 0006).

| Method | Path | Body / query | Result |
|---|---|---|---|
| `GET` | `/api/weak-spots` | `course_id?` | `200` `{local_date, courses: [{course_id, course_code, weeks: [{week, status, weakness, confidence, urgency, priority, evidence: {quiz_attempts, quiz_accuracy, cards_reviewed, avg_ease, lapsed_cards, overdue_cards}, next_exam: {exam_id, days_to_exam} \| null}]}]}`; weeks in the ADR 0007 order; `weakness` and `quiz_accuracy` are `null` when absent |
| `GET` | `/api/weak-spots/diagnostic` | `course_id`, `week` | `200` `{course_id, week, question_ids: [str], needs_generation: bool}` |
| `POST` | `/api/weak-spots/targeted` | `{course_id, week, kind}`, `kind` in `quiz`, `flashcards` | `202` new, or `200` the in-flight one: `TargetedGenerationResponse`; `403 ai_consent_required`; `404`; `429` code `targeted_daily_cap`; the existing quota/ceiling errors |
| `GET` | `/api/weak-spots/targeted/{generation_id}` | none | `200` `TargetedGenerationResponse`; `404` |
| `GET` | `/api/study-plan/tonight` | `minutes?` (10–90; used only when today's plan is built) | `200` `StudyPlanResponse` |
| `POST` | `/api/study-plan/tonight/refresh` | `{minutes?}` | `200` `StudyPlanResponse` (rebuilt, `version` + 1) |

`TargetedGenerationResponse` = `{id, course_id, week, kind, status, requested_count, created_count,
dropped_duplicate_count, dropped_uncited_count, item_ids: [str], error_code: str | null, created_at,
completed_at}`; `item_ids` is empty until `completed`. No `error` text, only the short machine
`error_code`. The `429 targeted_daily_cap` body is `{detail, code, limit, reset_at}` (`reset_at` = next
UTC midnight, ISO) with a `Retry-After` header. Mastery states are exactly `unknown | weak | shaky | solid`.
`GET /api/weak-spots/diagnostic` also returns `items: [{id, course_code, week}]` beside `question_ids`.
Additive, outside the table: `GET /api/study/items?flashcard_ids=..&quiz_question_ids=..` (at most 50 ids
in total) returns `{flashcards, quiz_questions}` for the caller's active items only (foreign, archived and
missing ids are omitted), and flashcard/quiz payloads of `/study/due` and `/assets/*` carry `origin` and
`focus_topic`. The admin `plan_split` is served by `GET /admin/usage/retention` from
`usage_service.plan_split_readout` (`{week_start, with_plan, without_plan}`, each `{signups, d7, d30}`).

`StudyPlanResponse` = `{plan_date, minutes, version, algorithm_version, built_at, total_minutes,
done_count, items: [{item_type, item_id, course_id, course_code, week, reason, minutes, done}],
focus: [{course_id, course_code, week, status, weakness, priority, days_to_exam}], diagnostic:
{course_id, course_code, week} | null}`. `item_type` in `card`, `quiz`; `reason` in `diagnostic`,
`missed`, `review`, `new`, `targeted`. Items are ids; the client runs them through the existing
study flows.

`POST /api/weak-spots/targeted` declares `dependencies=[Depends(require_ai_consent)]`
(`api.ai-consent v1`) and is the only route here that spends AI; it enqueues and never obtains an
adapter. `services/app/tests/contracts/test_weakspot_api_contract.py` checks the route table
against the app and the consent dependency on that route.

### pipeline.targeted_generation v1

Targeted quiz/card generation for one weak unit, run in the worker (M33-S2, GL#39). Provider:
`ai` — `services/app/app/pipeline/targeted_task.py` (the task), `app/agents/base.py`
(`GenerationFocus`, the `focus` keyword), `prompts/generate_targeted_quiz.txt` and
`prompts/generate_targeted_flashcards.txt`. Consumer: `backend` (enqueues from
`app/api/weakspots.py`, after `weakspot_service.request_targeted_generation` committed the row).
Decided in [ADR 0007](adr/0007-weak-spot-engine.md) Decision 5. No new request-time `get_agent`
site: ADR 0003 is unchanged.

```python
TARGETED_TASK_NAME = "app.pipeline.targeted_task.generate_targeted_items"


@dataclass
class GenerationFocus:
    topics: list[str]
    missed_questions: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    page_refs: list[int] = field(default_factory=list)


class AgentAdapter(ABC):
    @abstractmethod
    async def generate_flashcards(
        self,
        summary: str,
        extraction: ExtractionData,
        count: int,
        focus: GenerationFocus | None = None,
    ) -> list[FlashcardData]: ...

    @abstractmethod
    async def generate_quiz(
        self,
        summary: str,
        extraction: ExtractionData,
        count: int,
        focus: GenerationFocus | None = None,
    ) -> list[QuizQuestionData]: ...


def generate_targeted_items(self, generation_id: str) -> dict: ...
```

- The task is registered under `TARGETED_TASK_NAME`, `bind=True`, takes the
  `targeted_generations.id` only, and reads the owner from that row. It returns
  `{generation_id, user_id, status, created_count}`.
- `focus=None` is today's behaviour, byte for byte: same template, same output. A non-`None` focus
  selects the targeted template. Every backend implements the keyword; the ABC change bumped
  **`agents.AgentAdapter` to v2** (additive, M33-S2-ARCH-052), together with the new
  `GenerationFocus` data type and `pipeline/targeted_task.py` in its consumer table.
- Items whose `source_page_ref` is not a page of the target extraction are dropped; duplicates by
  `weakspot_service.is_duplicate` are dropped; kept items are inserted with `origin='targeted'`,
  never replacing or archiving an existing item (floor 4).
- Usage is metered with `billing_service.record_agent_usage`; a failure stores an `error_code`,
  never provider text (floor 2).

`services/app/tests/contracts/test_targeted_generation_contract.py` checks the block against
`app/agents/base.py`, every backend's overrides and the registered Celery task, and that ADR 0003's
allowlist still has exactly its five entries.

### models.weakspot v1

Storage for the weak-spot engine (M33-S2, GL#39). Provider: `data` — `app/models/study_plan.py`,
`app/models/targeted_generation.py`, `app/models/quiz.py`, `app/models/flashcard.py`, one Alembic
revision. Consumers: `backend`, `ai`. Decided in [ADR 0007](adr/0007-weak-spot-engine.md)
Decision 6. Scores are derived on read; there is no mastery table.

| Table | Column | Type | Null | Notes |
|---|---|---|---|---|
| `study_plans` | `user_id` | `String(36)` FK `users.id` | no | unique with `plan_date` |
| `study_plans` | `plan_date` | `Date` | no | user-local date (ADR 0006) |
| `study_plans` | `minutes` | `Integer` | no | |
| `study_plans` | `items` | `JSONB` | no | ADR 0007 Decision 4 item list |
| `study_plans` | `focus` | `JSONB` | no | focus and diagnostic units at build time |
| `study_plans` | `algorithm_version` | `Integer` | no | |
| `study_plans` | `version` | `Integer` | no | 1, then + 1 per refresh |
| `study_plans` | `built_at` | `DateTime(timezone=True)` | no | `done` is "acted on at or after this" |
| `targeted_generations` | `user_id` | `String(36)` FK `users.id` | no | index `(user_id, created_at)` |
| `targeted_generations` | `course_id` | `String(36)` FK `courses.id` | no | |
| `targeted_generations` | `week` | `Integer` | no | |
| `targeted_generations` | `kind` | `String(20)` | no | `quiz` \| `flashcards` |
| `targeted_generations` | `status` | `String(20)` | no | `queued` \| `running` \| `completed` \| `failed`; partial unique `(user_id, course_id, week, kind)` while `queued`/`running` |
| `targeted_generations` | `requested_count` | `Integer` | no | |
| `targeted_generations` | `created_count` | `Integer` | no | default 0 |
| `targeted_generations` | `dropped_duplicate_count` | `Integer` | no | default 0 |
| `targeted_generations` | `dropped_uncited_count` | `Integer` | no | default 0 |
| `targeted_generations` | `topics` | `JSONB` | no | labels only |
| `targeted_generations` | `error_code` | `String(50)` | yes | never provider text |
| `targeted_generations` | `completed_at` | `DateTime(timezone=True)` | yes | |
| `quiz_questions` | `origin` | `String(20)` | no | server default `'pipeline'`; `pipeline` \| `targeted` |
| `quiz_questions` | `targeted_generation_id` | `String(36)` FK `targeted_generations.id` | yes | |
| `quiz_questions` | `focus_topic` | `String(200)` | yes | |
| `flashcards` | `origin` | `String(20)` | no | as on `quiz_questions` |
| `flashcards` | `targeted_generation_id` | `String(36)` FK `targeted_generations.id` | yes | |
| `flashcards` | `focus_topic` | `String(200)` | yes | |

Both new tables also have `id` (`String(36)`, `generate_id`), `created_at` and `updated_at`.
Index `ix_quiz_attempts_question_created` on `quiz_attempts (quiz_question_id, created_at)`.
Account deletion removes both new tables' rows (`backend`, `account_service`).
`services/app/tests/contracts/test_weakspot_storage_contract.py` checks this table against the ORM
metadata.

### api.study-items v2

Owner-scoped create/edit/delete of flashcards and quiz questions (GL#48, audit PROD-05). Lives in
`app/api/assets.py`, logic in `app/services/asset_service.py`. All routes need an authenticated
caller; every lookup joins `courses.user_id`; a foreign, missing or already-archived id is a
plain `404` (no existence oracle).

| Route | Body | Result |
|---|---|---|
| `POST /api/assets/flashcards` | `{course_code, week 1-52, front, back, tags?: [str], source_artifact_id?}` | `201 FlashcardResponse`, `origin="user"` |
| `PATCH /api/assets/flashcards/{id}` | any of `{front, back, tags}` (at least one) | `200 FlashcardResponse` of the **new** copy (new id) |
| `DELETE /api/assets/flashcards/{id}` | none | `204`; the card is archived |
| `POST /api/assets/quiz` | `{course_code, week, question_type, question, options?: [str], correct_answer, explanation?, source_artifact_id?}` | `201 QuizQuestionResponse`, `origin="user"` |
| `PATCH /api/assets/quiz/{id}` | any of `{question, options, correct_answer, explanation}` | `200` of the **new** copy |
| `DELETE /api/assets/quiz/{id}` | none | `204`; the question is archived |

Rules:

* **No silent loss (floor 4).** Nothing here issues a SQL `DELETE`. `DELETE` sets `archived_at`.
  `PATCH` archives the original row and inserts an edited copy (same course, week, source
  artifact, page ref and generation version; unchanged fields carried over; `origin="user"`).
  The original keeps its `flashcard_reviews` / `quiz_attempts`, so study history stays valid.
  For flashcards the SRS schedule (ease, interval, repetitions, next review) is copied onto the
  new card so an edit does not reset progress.
* **User items are protected.** `save_flashcards` / `save_quiz_questions` archive only
  `origin="pipeline"` rows, so a lecture re-run never archives or overwrites `origin="user"`
  (nor `"targeted"`). Targeted dedup reads every non-archived row, so user items count as existing.
* `origin` is now `pipeline | targeted | user` (`String(20)`, no check constraint, no migration).
* Manual items need a `source_artifact_id` (NOT NULL column): the given one (must be the caller's,
  in that course and week) or else the caller's newest artifact in that course and week; with none,
  `409 no_source_artifact`. `source_page_ref=0` marks "no page".
* Quiz validation: `question_type` is `multiple_choice` (2-8 `options`, `correct_answer` must be
  an option or its letter) or `short_answer` (no options). Text fields are stripped, non-empty,
  bounded (front/back/question/explanation 4000 chars). `422` otherwise.
* Unknown `course_code` for the caller is `404`.

**v2 (M34-S3-BACKEND-012, recorded before implementation):** `course_code` on both `POST` routes
is matched the way upload placement matches it (`api.upload-placement v1`), not exactly. In v1
`csit302` was `404` for a caller who owns `CSIT302`; upload placement found it.

* The lookup is `course_service.get_course_by_code_ci(session, code, *, user_id) -> Course | None`:
  `code.strip().upper()` compared with `upper(courses.code)`, filtered on `courses.user_id ==
  user_id` (floor 1). `asset_service` resolves `course_code` through it and through nothing else.
* `uq_courses_code_user` is case-sensitive, so legacy data can hold two codes that differ only in
  case for one user. The exact-case match wins; otherwise the oldest by `created_at`. Never
  `MultipleResultsFound`, never a `500`.
* It never creates a course: unknown for the caller stays `404` (upload placement creates one;
  card add does not). Archived courses resolve as before (v1 did not filter them).
* `get_course_by_code` (exact match) is unchanged: the course routes keyed on `{code}` in the URL
  keep their behaviour.

### api.upload-placement v1

Optional explicit placement on upload (GL#49, audit PROD-07).

* `POST /api/uploads` and `POST /api/uploads/batch` accept query parameters (applied to
  every file) accept optional `course_code` (1-20 chars) and `week` (1-52). `course_code` and
  `week` must be given together; one without the other is `422`.
* When both are given the artifact is created already placed (`course_id`, `week`,
  `status="classified"`) and the pipeline is dispatched from `extract`
  (`resume_pipeline(..., from_stage="extract")`): the classify stage and its AI call are skipped
  and no classification review item is created. The course is the caller's own (matched
  case-insensitively on code); if they have none with that code it is created, subject to the
  plan's course quota (`QuotaExceededError`, same as classify).
* When absent, behaviour is unchanged (AI routing from `ingest`).
* A duplicate upload returns the existing artifact untouched; the placement is ignored.
* Failure to resolve the course (quota) fails before anything is stored. In batch it fails the
  request with the quota error (placement is a single choice for all files).

### models.secrets-at-rest v1

Third-party tokens and the TOTP seed encrypted at rest (M34-S2-SEC-005, R-017, M32 N-7; the seed
added by user decision 2026-10-16). Recorded first as `models.third-party-tokens v1`; renamed
before any implementation, because the TOTP seed is ours, not a third party's. Provider: `backend`
— `services/app/app/core/secret_box.py` (`EncryptedText`), `app/cli.py` (rotation),
`app/services/user_service.py` and `app/api/auth.py` (the unreadable-seed rules below); `data` —
`app/models/oauth_account.py`, `app/models/calendar_sync.py`, `app/models/user.py`, one Alembic
revision. Consumers: `backend` (`user_service`, `gcal_service`, `account_service`), `safety`
(floor-2 pin). The scheme is the one per-user AI credentials already use (SEC-06): `secret_box`,
Fernet under `SETTINGS_ENCRYPTION_KEY`, stored as `enc:v1:<token>`. No second key and no second
format.

**Columns.** These five, and only these, hold a secret this contract covers:

| Table | Column | Type | Null | Notes |
|---|---|---|---|---|
| `oauth_accounts` | `access_token` | `EncryptedText` | yes | was `String(1000)`; widened, since Fernet output is about 1.4x the input plus 57 bytes |
| `oauth_accounts` | `refresh_token` | `EncryptedText` | yes | was `String(1000)` |
| `calendar_syncs` | `access_token` | `EncryptedText` | no | was `Text` |
| `calendar_syncs` | `refresh_token` | `EncryptedText` | yes | was `Text` |
| `users` | `mfa_secret` | `EncryptedText` | yes | was `String(64)`; widened, a 32-character base32 seed encrypts to well over 64 |

Looked at and **not** in scope: `calendar_syncs.sync_token` is Google's incremental-sync cursor, not
a credential (it authorises nothing without the access token); `magic_links.token_hash`,
`invite_codes.token_hash` and `users.backup_codes` are already digests (the backup codes as
`hash_backup_codes` output); `push_subscriptions.p256dh` and `.auth` are the browser's
push-encryption keys, which the push sender needs in the clear.

**Accessor.** Encryption is a column type, so no call site can forget it:

```python
class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None: ...

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None: ...
```

- Write: `None` stays `None`; any `str` goes through `secret_box.encrypt`. Every write produces
  ciphertext, including a value that merely starts with `enc:v1:`. With no key on a single-user
  instance `secret_box.encrypt` stores plaintext, as it does for AI credentials; a multi-user
  instance refuses to start without a key (`secret_box.check_startup`).
- Read: `None` stays `None`; legacy plaintext (no prefix) is returned as is, so rows written
  before the migration still work; ciphertext is decrypted. Ciphertext that fails authentication
  (tampered, or written under a key no longer configured) reads as **`None`**, logs
  `secret_at_rest_undecryptable` with no value in it, and never raises: loading a user, linking
  an account or deleting one must not fail on one bad secret. A `None` calendar access token takes
  the existing "reconnect needed" path in `gcal_service`. A `None` TOTP seed on an account with
  MFA on is **not** "no MFA": see the next block.
- ORM attributes hold plaintext in memory, so `user_service` and `gcal_service` need no change to
  read or write them.
- **An ORM read is not a safe source for a write-back.** An undecryptable value loads as `None`;
  writing that `None` back would destroy the only copy of a value that a restored key could still
  read. So nothing reads one of these attributes in order to re-save it: the rotation command and
  the migration work on the raw column values (Core statements over the table with a plain `Text`
  column, not the ORM attribute), and `users.mfa_secret` is assigned only by
  `user_service.enable_mfa`, `disable_mfa` and `clear_mfa`, each of which sets it from a fresh
  value or to `None` on purpose.
- **Never logged, never returned (floor 2).** No log call passes a token or seed value; no API
  response model has a field named `access_token`, `refresh_token`, `sync_token` or `mfa_secret`.
  `account_service.EXPORT_EXCLUDED_COLUMNS` keeps excluding `access_token`, `refresh_token`,
  `mfa_secret` and `backup_codes` from the data export. `MFASetupResponse.secret` is not an
  exception: it is a freshly generated seed shown to its own user once at enrolment, before
  anything is stored.

**Unreadable TOTP seed: MFA fails closed.** The state is `users.mfa_enabled` true with
`users.mfa_secret` reading `None`. `enable_mfa` sets both and `disable_mfa`/`clear_mfa` clear both,
so on sound data the pair never occurs; when it does, the seed was undecryptable (or the row was
damaged). Rules:

1. `mfa_enabled` is the only switch for whether a second factor is demanded. No code path treats
   a `None` seed as "MFA off", and nothing writes `mfa_enabled = False` because the seed is
   unreadable.
2. **Sign-in** (`POST /api/auth/login`, `POST /api/auth/oauth/mfa`). A `totp_code` is refused
   with the same `AuthorizationError("Invalid MFA code")` as a wrong code (no oracle on the
   account's state), counts as a failed attempt (`login_throttle.record_failure`), and sets no
   cookie. The route logs `mfa_secret_unavailable` at warning with `user_id` and nothing else. A
   missing code is still `"MFA code required"`. The password-less OAuth callback still issues the
   pending-MFA cookie and never full cookies.
3. **Backup codes are the user's way in.** They are hashed in their own column and do not depend
   on the key, so `backup_code` sign-in works unchanged, each code once.
4. **Turning MFA off** (`POST /api/auth/mfa/disable`, `user_service.disable_mfa`) is refused and
   changes nothing (`mfa_enabled`, `mfa_secret`, `backup_codes` and `tokens_valid_from` keep their
   values): `disable_mfa` raises `ValueError("MFA secret unavailable; sign in with a backup code
   and ask an administrator to reset MFA")`, the route answers `400` with that detail, and the
   service logs `mfa_secret_unavailable` with `user_id`. Today it says "MFA is not enabled", which
   is false and is what this rule replaces. Re-enrolment (`POST /api/auth/mfa/verify`) stays
   refused while `mfa_enabled` is true, so a session cannot swap in a seed of its own.
5. **Recovery.** For one account: the user signs in with a backup code, and an administrator,
   after verifying identity out of band, runs `POST /api/admin/users/{id}/mfa-reset`
   (`clear_mfa`), after which the user enrols afresh. A user with no backup codes left goes
   straight to the administrator. For many accounts at once (a key dropped before rotation
   finished): put the old key back at the end of `SETTINGS_ENCRYPTION_KEY`; every seed reads again
   and nothing was lost, because rule 1 and the write-back rule kept the ciphertext in place.
   Deliberately not offered: disabling MFA with a backup code, or any reset reachable by the
   account holder alone (the reasoning in `clear_mfa`'s docstring).

**Key rotation.** Same stance as SEC-06: `SETTINGS_ENCRYPTION_KEY` is a comma-separated list, the
first key encrypts and every key decrypts. `python -m app.cli encrypt-user-secrets --apply`
re-encrypts these five columns as well as the `user_settings` credentials, under the first key,
reading and writing raw column values, and reports counts only. Rotation is therefore: prepend the
new key, run the command, drop the old key only once the command reports `unreadable: 0`. A value
unreadable under every configured key is counted and left exactly as stored.

**Migration.** One Alembic revision, after the current head:

- `upgrade`: widen `oauth_accounts.access_token`/`refresh_token` and `users.mfa_secret` to `Text`;
  then, for every row of the three tables, encrypt each non-NULL value of the five columns that is
  not already `enc:v1:`. Idempotent: a second run changes nothing. Without a key (single-user) it
  leaves the values as they are and says so in its output.
- `downgrade`: decrypt every `enc:v1:` value of the five columns back to plaintext, then narrow the
  two `oauth_accounts` columns to `String(1000)` and `users.mfa_secret` to `String(64)`. A value
  that cannot be decrypted aborts the downgrade (nothing is narrowed or lost) rather than being
  dropped.
- Neither direction prints or logs a value.

`services/app/tests/contracts/test_secrets_at_rest_contract.py` checks the column types, the
accessor's behaviour under the test key, the migration and CLI coverage, the API response models
and the export exclusions, and drives the unreadable-seed rules through `disable_mfa` and the two
sign-in routes.

### models.stripe-webhook-events v1

Stripe webhook dedupe and ordering state in Postgres (M34-S2-SEC-008, M32 N-8). Provider: `data` —
`app/models/stripe_webhook_event.py`, one Alembic revision; `backend` —
`app/services/billing_service.py` (`handle_webhook_event`). Replaces the Redis keys
`stripe:event:<id>` (dedupe, 30-day TTL) and `stripe:last_created:<customer>` (ordering watermark,
90-day TTL). With this, `billing_service` does not touch Redis at all, so a Redis flush or outage
can no longer re-apply a delivered event or let a stale one undo a newer state.

| Table | Column | Type | Null | Notes |
|---|---|---|---|---|
| `stripe_webhook_events` | `stripe_event_id` | `String(255)` | no | unique |
| `stripe_webhook_events` | `event_type` | `String(100)` | no | |
| `stripe_webhook_events` | `stripe_customer_id` | `String(255)` | yes | index `(stripe_customer_id, stripe_created)` |
| `stripe_webhook_events` | `stripe_created` | `DateTime(timezone=True)` | yes | the event's `created` |
| `stripe_webhook_events` | `outcome` | `String(20)` | no | `applied` \| `stale` |

Plus `id` (`String(36)`, `generate_id`) and `created_at`. No payload, no user id, no email: the
row is Stripe's ids and our decision, nothing else.

`handle_webhook_event(session, event_type, data, *, event_id=None, created=None) -> None` keeps its
signature. For the three `customer.subscription.*` types (every other type is still ignored and
records nothing):

1. **Claim.** `INSERT … ON CONFLICT (stripe_event_id) DO NOTHING RETURNING id` in the request's
   transaction. No row back means the event was already processed: log `webhook_replay_ignored`,
   change nothing, return. An event without an id is processed without a claim, as today.
2. **Order.** If `created` is given and an `applied` row for the same customer has a later
   `stripe_created`, mark the claimed row `stale`, commit, log `webhook_stale_ignored`, return.
3. **Apply.** Run the subscription handler and mark the row `applied`; one commit covers the claim
   and the effect.
4. **Failure.** Any exception rolls the transaction back, claim included, so Stripe's retry is
   processed afresh. The exception propagates (the route answers `500`, Stripe retries).

**Concurrent duplicate delivery.** Two requests carrying one event id race on the unique index:
the second `INSERT` waits for the first transaction. If the first commits, the second gets no row
and is a replay (step 1). If the first rolls back, the second claims and applies. The effect is
applied exactly once either way, with no lock beyond the index.

**Retention: kept indefinitely, by decision (user, 2026-10-16).** No beat task, CLI command or
migration deletes rows from this table, and that is the design, not a gap to fill later. Volume is a
handful per subscriber per month, the table is the only record of which Stripe events changed a
plan, and the ordering watermark is read from it, so pruning would also weaken the stale-event
check. Changing this needs a new version of this entry. The table has no `user_id`, so account deletion leaves it; it holds only
Stripe's opaque ids. `account_service` lists it among the tables that belong to nobody.

Required behaviour tests (`backend` unit, `qa` integration on Postgres): replay of an applied event
is a no-op; replay after a failed first attempt applies; a stale `updated` after a newer one is
ignored and recorded `stale`; two concurrent deliveries of one id apply once; no Redis call on any
path. `services/app/tests/contracts/test_stripe_webhook_events_contract.py` pins the table and the
Redis-free service.

### core.login-throttle-metrics v1

A counter for the auth throttle's Redis being unreachable (M34-S3-BACKEND-012). Provider:
`backend` — `app/core/login_throttle.py` (defines it) and `app/core/rate_limit.py` (also
increments it). Consumer: whoever reads `/metrics` (alert rules are `devops`').

```python
LOGIN_THROTTLE_UNAVAILABLE = Counter(
    "studyaio_login_throttle_unavailable_total",
    "Auth throttle store unreachable, by operation.",
    ["action"],
)
```

`action` is exactly one of four values; never an email, a key or a path:

| `action` | Where | What the caller gets |
|---|---|---|
| `read` | `login_throttle.apply_delay` could not read the failure count | login proceeds with no delay (fails open) |
| `record` | `login_throttle.record_failure` could not count a failure | the failure is not counted (fails open) |
| `clear` | `login_throttle.clear` could not reset the count | nothing visible |
| `limit` | the rate limiter's store failed on an `/api/auth/` path | `503` with `Retry-After: 5` (fails closed) |

Incremented once per occurrence, next to the existing `login_throttle_unavailable` and
`rate_limit_store_down_failing_closed` log lines, which stay. The limiter's fail-open branch on
non-auth paths is not counted here. Exported on `/metrics` from the default registry.
`services/app/tests/contracts/test_login_throttle_metrics_contract.py` checks the definition and
drives each `action` against a store that raises.

### api.onboarding v1

Server-side first-run status, the source the dashboard checklist reads (M34-S3-BACKEND-012).
Provider: `backend` — `app/services/onboarding_service.py`, `app/api/onboarding.py`; `data` — one
column on `users`, one Alembic revision. Consumer: `frontend` (`FirstRunChecklist`, which today
derives the same steps from three queries and keeps dismissal in `localStorage`).

| Method | Path | Body / query | Result |
|---|---|---|---|
| `GET` | `/api/onboarding` | none | `200` `OnboardingResponse` |
| `PATCH` | `/api/onboarding` | `{checklist}` | `200` `OnboardingResponse`; `422` for a value outside `ONBOARDING_CHECKLIST_STATES` |

`OnboardingResponse` = `{phase, steps: {upload, summary, check_in}, summary_target: {course_id,
course_code, week} | null, checklist, visible}`. Both routes require a caller
(`get_current_user_or_default`); neither spends AI or takes an id.

Storage: `users.onboarding_checklist` `String(20)`, NOT NULL, server default `'auto'`, so existing
users backfill to `auto` without a data migration. It is the only stored state; everything else is
derived on read, per caller, with every query filtered on the caller (floor 1):

- `uploaded`: the caller has at least one `lecture_artifacts` row, any status.
- `summary_target`: the caller's first summary in a non-archived course, ordered by course code
  then week (`summaries` joined to `courses` on `courses.user_id`).
- `summary_read`: the caller has a `summary_viewed` usage event (`services.usage v1`, already sent
  by the summary view).
- `check_in_done`: the caller has a `flashcard_reviews` row, or a `quiz_attempts` row on a quiz
  question in a course they own.

```python
ONBOARDING_CHECKLIST_STATES = ("auto", "dismissed", "pinned")
ONBOARDING_PHASES = ("new", "processing", "has_summary", "done")
ONBOARDING_STEP_STATUSES = ("done", "active", "locked")


@dataclass(frozen=True)
class SummaryTarget:
    course_id: str
    course_code: str
    week: int


@dataclass(frozen=True)
class OnboardingStatus:
    phase: str
    upload: str
    summary: str
    check_in: str
    summary_target: SummaryTarget | None
    checklist: str
    visible: bool


def derive_status(
    *,
    uploaded: bool,
    summary_target: SummaryTarget | None,
    summary_read: bool,
    check_in_done: bool,
    checklist: str,
) -> OnboardingStatus: ...


async def get_status(session: AsyncSession, *, user_id: str) -> OnboardingStatus: ...


async def set_checklist(
    session: AsyncSession, *, user_id: str, checklist: str
) -> OnboardingStatus: ...
```

`derive_status` is the UI's `deriveOnboarding` moved server-side: a check-in finishes the checklist
whichever door the user came through, and a summary target unlocks both later steps. `visible` is
`checklist != "dismissed" and (phase != "done" or checklist == "pinned")`: `pinned` is the "show it
again" choice in settings, `dismissed` hides it. Worked examples (`set` is any `SummaryTarget`):

| uploaded | target | summary_read | check_in_done | checklist | phase | upload | summary | check_in | visible |
|---|---|---|---|---|---|---|---|---|---|
| no | none | no | no | auto | new | active | locked | locked | yes |
| yes | none | no | no | auto | processing | done | locked | locked | yes |
| yes | set | no | no | auto | has_summary | done | active | active | yes |
| yes | set | yes | no | auto | has_summary | done | done | active | yes |
| yes | set | no | yes | auto | done | done | done | done | no |
| yes | set | no | yes | pinned | done | done | done | done | yes |
| no | none | no | no | dismissed | new | active | locked | locked | no |
| no | none | no | yes | auto | done | done | done | done | no |

`services/app/tests/contracts/test_onboarding_contract.py` compares the block with the source, runs
the table through `derive_status`, and checks the routes and the column.

## Change log

The `Contract` column holds the name from that contract's `###` heading in Current.

| Date | Contract | Version | Change | Task |
|---|---|---|---|---|
| 2026-10-04 | agents.AgentAdapter | v1 | Recorded as-built: 7 abstract methods, `stream_answer`, metering and output-language members, `get_agent`, 13 data types, 5 backends, 12 direct consumers. No code changed. | M31-S1-ARCH-001 |
| 2026-10-04 | agents.AgentAdapter | v1 | Floor-3 open question closed by reference to ADR 0003, which enumerates the five request-time `get_agent` call sites. Interface unchanged, so no version bump. | M31-S1-ARCH-006 |
| 2026-10-09 | core.clock | v1 | New contract, recorded before implementation: five functions, `user_settings.timezone` as the zone source, `None`/invalid → UTC. Contract test committed red. | M32-S2-ARCH-033 |
| 2026-10-11 | api.ai-consent | v1 | New contract, recorded before implementation: consent endpoint, `ai_consent_required` on the profile, 403 `ai_consent_required` gate, email-free logs. | M33-S1-BACKEND-017 |
| 2026-10-11 | api.ai-consent | v1 | Additive: `ai_consent_version` (current required version) on `UserProfileResponse`. | M33-S1-BACKEND-036 |
| 2026-10-11 | api.ai_feedback | v1 | New contract, recorded before implementation: vote upsert/delete/list, admin aggregate at `/admin/ai-feedback`. | M33-S1-BACKEND-015 |
| 2026-10-11 | services.usage | v1 | New contract, recorded before implementation: allowlisted never-raising `record`, view-event endpoint, admin retention readout. | M33-S1-BACKEND-016 |
| 2026-10-12 | services.usage | v1 | Pending additive: `study_plan_built` and `targeted_generation_requested` server events; `plan_split` in the admin retention readout. | M33-S2-ARCH-018 |
| 2026-10-12 | services.weakspot | v1 | New contract, recorded before implementation (ADR 0007, Proposed): scoring formula and constants, plan, diagnostic, targeted-generation request. Contract test written red. | M33-S2-ARCH-018 |
| 2026-10-12 | api.weak-spots | v1 | New contract, recorded before implementation: heatmap, diagnostic, targeted request/status, tonight's plan and refresh. Contract test written red. | M33-S2-ARCH-018 |
| 2026-10-12 | pipeline.targeted_generation | v1 | New contract, recorded before implementation: worker task, `GenerationFocus`, additive `focus` keyword (bumps `agents.AgentAdapter` to v2 on implementation). Contract test written red. | M33-S2-ARCH-018 |
| 2026-10-12 | models.weakspot | v1 | New contract, recorded before implementation: `study_plans`, `targeted_generations`, provenance columns, attempts index. Contract test written red. | M33-S2-ARCH-018 |
| 2026-10-15 | agents.AgentAdapter | v2 | Additive: trailing `focus: GenerationFocus \| None = None` on `generate_flashcards` and `generate_quiz`, new `GenerationFocus` data type (14 types), `pipeline/targeted_task.py` added as a consumer (13 direct). v1 callers unaffected: `focus` defaults to `None`, which is v1 behaviour. No new request-time `get_agent` site; ADR 0003 unchanged. | M33-S2-ARCH-052 |
| 2026-10-15 | api.weak-spots | v1 | Additive as built: `error_code` on `TargetedGenerationResponse`, `items` on the diagnostic, `GET /api/study/items`, `origin`/`focus_topic` on card and quiz payloads, `plan_split` on the retention readout. | M33-S2-BACKEND-020 |
| 2026-10-15 | api.study-items | v1 | New contract, recorded before implementation: manual create, archive-and-copy edit, soft delete of flashcards and quiz questions; `origin="user"`. | M33-S3-BACKEND-027 |
| 2026-10-15 | api.upload-placement | v1 | New contract, recorded before implementation: optional `course_code` + `week` on single and batch upload skip classification. | M33-S3-FRONTEND-028 |
| 2026-10-16 | models.third-party-tokens | v1 | New contract, recorded before implementation: `EncryptedText` column type over `secret_box` on the four OAuth/calendar token columns, read failure is `None`, rotation through `encrypt-user-secrets`, reversible re-encrypting migration. Contract test written red. | M34-S2-SEC-005 |
| 2026-10-16 | models.stripe-webhook-events | v1 | New contract, recorded before implementation: `stripe_webhook_events` (unique event id) replaces the Redis dedupe and ordering keys; claim, apply and commit in one transaction. Contract test written red. | M34-S2-SEC-008 |
| 2026-10-16 | api.study-items | v2 | `course_code` on card and quiz create is matched case-insensitively through `course_service.get_course_by_code_ci`, as upload placement does; exact case wins a tie; still never creates. Contract test written red. | M34-S3-BACKEND-012 |
| 2026-10-16 | core.login-throttle-metrics | v1 | New contract, recorded before implementation: `studyaio_login_throttle_unavailable_total{action}`, `read`/`record`/`clear` (fail open) and `limit` (fail closed). Contract test written red. | M34-S3-BACKEND-012 |
| 2026-10-16 | api.onboarding | v1 | New contract, recorded before implementation: `GET`/`PATCH /api/onboarding`, `users.onboarding_checklist`, pure `derive_status` with worked examples. Contract test written red. | M34-S3-BACKEND-012 |
| 2026-10-16 | api.ai_feedback | v2 | Additive: `qa_answer` target type, `qa_answers` table (no text), `answer_id` on `QAResponse`; study cards use the existing `flashcard`/`quiz_question` types. Contract test written red. | M34-S3-BACKEND-012 |
| 2026-10-16 | models.secrets-at-rest | v1 | Renamed from `models.third-party-tokens` before implementation and widened by user decision: `users.mfa_secret` (TOTP seed) joins the four token columns under the same `EncryptedText`, migration and rotation. An unreadable seed fails closed (refused like a wrong code, throttled, valueless `mfa_secret_unavailable` log, disable refused, recovery by backup code plus admin reset or by restoring the key). No ORM write-back of an unreadable value. Undecryptable log event renamed `secret_at_rest_undecryptable`. Contract test renamed and extended, red. | M34-S2-SEC-005 |
| 2026-10-16 | api.ai_feedback | v1 | The v2 recorded earlier today is withdrawn before implementation, by user decision: no `qa_answer` target type, no `qa_answers` table, no `QAResponse.answer_id` (no UI calls `/api/qa/ask`). Nothing in the interface changes, so the entry returns to v1 with a note that study cards use the existing `flashcard`/`quiz_question` types. Contract test reduced to green pins. | M34-S3-BACKEND-012 |
| 2026-10-16 | models.stripe-webhook-events | v1 | Retention made an explicit decision (user): rows are kept indefinitely; nothing prunes the table. No interface change. | M34-S2-SEC-008 |
