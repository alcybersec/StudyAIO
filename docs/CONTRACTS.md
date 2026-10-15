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
inbox. `answer` resolves to an assistant `chat_message`; `/qa/ask` answers are not persisted and
carry no id, so they cannot be rated. Account deletion removes the rows (`user_id` column).

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

### api.study-items v1

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
