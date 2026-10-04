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

**Open question against floor 3.** Floor 3 says no AI call is made from an API route, only from the
Celery worker. As built, four request paths call the adapter in the API process: `POST /api/qa/ask`
(`api/qa.py`), `POST /api/settings/test-ai` (`api/settings.py`), chat send and stream
(`api/chat.py` → `chat_service`) and `POST /api/concepts/extract/{artifact_id}`
(`api/concepts.py` → `concept_service`). Every one of them still goes through `get_agent`, so the
first clause of the floor holds; the second does not describe the code. This entry records the code
as it is. Whether the floor or the code changes is for `safety` and the user, not this contract.

## Change log

The `Contract` column holds the name from that contract's `###` heading in Current.

| Date | Contract | Version | Change | Task |
|---|---|---|---|---|
| 2026-10-04 | agents.AgentAdapter | v1 | Recorded as-built: 7 abstract methods, `stream_answer`, metering and output-language members, `get_agent`, 13 data types, 5 backends, 12 direct consumers. No code changed. | M31-S1-ARCH-001 |
