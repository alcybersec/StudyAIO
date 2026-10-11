# Contracts

Every interface crossing a role boundary is recorded here **before** it is implemented: shape,
version, and what changed.

## Current

### agents.AgentAdapter v1

The single interface every AI call in StudyAIO goes through (floor 3, `docs/strategy.md` §6).
Provider: `ai` — `services/app/app/agents/base.py` (the ABC and its data types) and
`services/app/app/agents/factory.py` (`get_agent`, the only sanctioned way to obtain an instance).
Recorded as-built on 2026-10-04: v1 is the interface that already shipped with M1–M30, not a new
design. Decided in [ADR 0002](adr/0002-module-boundaries.md).

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
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[FlashcardData]: ...

    @abstractmethod
    async def generate_quiz(
        self, summary: str, extraction: ExtractionData, count: int
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
- `refreshed_credentials` is **not** part of v1. Only `ClaudeCodeAdapter` sets it, and consumers
  read it with `hasattr`. Promoting it to the ABC is a v2 change.

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
