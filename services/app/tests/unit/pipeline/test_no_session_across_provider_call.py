"""No DB transaction is open while a provider call is in flight (GL#50, audit TECH-07).

A Celery stage that reads, calls the AI provider (seconds to minutes), then writes
used to keep its pooled connection idle-in-transaction for the whole call: with a
handful of concurrent stages the pool, and Postgres's `max_connections`, run dry
while every connection is doing nothing. The rule pinned here: at the instant any
provider method (`classify_lecture`, `generate_*`, `extract_*`, `answer_*`,
`stream_answer`, `embed_texts`) is entered, no session built by the app's session
factory has an open transaction.

The fake session below models SQLAlchemy's autobegin: `execute`, `flush`, `get`
open a transaction; `commit`, `rollback`, `close` end it. The fake adapter records
a violation (rather than raising, since stages swallow exceptions) whenever it is
entered with one open. Each test also asserts the adapter *was* called, so a stage
that silently stops reaching the provider cannot pass vacuously.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import (
    ClassificationResult,
    ConceptExtractionResult,
    CourseOpsResult,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
    TokenUsage,
)


class Res:
    """A result object that answers every accessor a stage uses."""

    def __init__(self, value=None):
        self.value = value

    def unique(self):
        return self

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalar(self):
        return self.value

    def first(self):
        return self.value

    def all(self):
        return [] if self.value is None else [self.value]


class TxnSession:
    """Fake AsyncSession that tracks whether a transaction is open."""

    def __init__(self, registry: list["TxnSession"], tables: dict[str, object]):
        registry.append(self)
        self.open = False
        self.tables = tables
        self.add = MagicMock()
        self.refresh = AsyncMock()
        self.delete = AsyncMock()

    def in_transaction(self) -> bool:
        return self.open

    async def execute(self, stmt, *args, **kwargs):
        self.open = True
        text = str(stmt)
        for table, value in self.tables.items():
            if f"FROM {table}" in text:
                return Res(value)
        return Res(None)

    async def get(self, model, ident, *args, **kwargs):
        self.open = True
        return self.tables.get(model.__tablename__)

    async def flush(self, *args, **kwargs):
        self.open = True

    async def commit(self):
        self.open = False

    async def rollback(self):
        self.open = False

    async def close(self):
        self.open = False


class Harness:
    """Session factory + recording agent sharing one registry."""

    def __init__(self, tables: dict[str, object] | None = None):
        self.sessions: list[TxnSession] = []
        self.tables = tables or {}
        self.calls: list[str] = []
        self.violations: list[str] = []

    def factory(self):
        @contextlib.asynccontextmanager
        async def _cm():
            yield TxnSession(self.sessions, self.tables)

        return MagicMock(side_effect=lambda: _cm())

    def _enter(self, name: str) -> None:
        self.calls.append(name)
        if any(s.open for s in self.sessions):
            self.violations.append(name)

    def agent(self, **returns):
        harness = self
        agent = MagicMock()
        agent.usage = TokenUsage()
        agent.refreshed_credentials = None

        def make(name, value):
            async def _call(*args, **kwargs):
                harness._enter(name)
                return value

            return _call

        for name, value in returns.items():
            setattr(agent, name, make(name, value))
        return agent

    def assert_clean(self) -> None:
        assert self.calls, "the stage never reached the provider (vacuous pass)"
        assert not self.violations, (
            f"provider called with a DB transaction open: {self.violations}. "
            "Commit/close the session before the call and persist in a fresh transaction."
        )


async def _read(session, value=None):
    """Stand-in for a service helper that reads (and so autobegins) on the session."""
    await session.execute("SELECT 1")
    return value


def reading(value=None):
    """An async service replacement whose first arg is the session and which reads."""

    async def _fn(session, *args, **kwargs):
        return await _read(session, value)

    return _fn


def _artifact(**extra):
    course = MagicMock()
    course.code = "CSIT302"
    course.id = "course-1"
    base = dict(
        id="art-1",
        user_id="user-1",
        course_id="course-1",
        week=3,
        course=course,
        file_path="uploads/a.pdf",
        file_type="pdf",
        original_filename="a.pdf",
        title="t",
    )
    base.update(extra)
    return MagicMock(**base)


def _extraction():
    ext = MagicMock()
    ext.artifact_id = "art-1"
    ext.manifest_json = {"pages": [{"page_number": 1, "text": "Content", "images": []}]}
    return ext


def _summary_row():
    s = MagicMock()
    s.content_md = "# Summary"
    return s


@pytest.mark.asyncio
async def test_classify_releases_the_session_before_the_provider_call():
    from app.pipeline import classify

    h = Harness({"lecture_artifacts": _artifact()})
    agent = h.agent(
        classify_lecture=ClassificationResult(
            course_code="CSIT302", week=3, title="T", confidence=0.99
        )
    )
    course = MagicMock(id="course-1")
    with (
        patch.object(classify, "async_session_factory", h.factory()),
        patch.object(classify, "_extract_text_preview", return_value="preview"),
        patch.object(classify, "_get_known_courses", reading([])),
        patch.object(classify, "_get_or_create_course", AsyncMock(return_value=course)),
        patch.object(classify, "get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_agent_config", reading(None)),
        patch("app.services.billing_service.record_agent_usage", AsyncMock()),
    ):
        result = await classify._classify("art-1")

    assert result["status"] == "classified"
    h.assert_clean()


@pytest.mark.asyncio
async def test_summarize_releases_the_session_before_the_provider_call():
    from app.pipeline import summarize

    h = Harness({"lecture_artifacts": _artifact()})
    agent = h.agent(generate_summary=SummaryResult(content_md="# S"))
    svc = MagicMock()
    svc.get_week_extractions = reading([_extraction()])
    svc.get_existing_summary = reading(None)
    svc.merge_extractions = MagicMock(
        return_value=SimpleNamespace(pages=[], metadata={"artifact_ids": ["art-1"]})
    )
    svc.build_summary_storage_key = MagicMock(return_value="summaries/k")
    svc.create_or_update_summary = AsyncMock(return_value=SimpleNamespace(id="s1", version=1))
    storage = MagicMock()
    storage.exists = AsyncMock(return_value=False)
    storage.put = AsyncMock()
    with (
        patch.object(summarize, "async_session_factory", h.factory()),
        patch.object(summarize, "summary_service", svc),
        patch.object(summarize, "get_storage", return_value=storage),
        patch.object(summarize, "get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_ai_context", reading((None, None))),
        patch("app.services.billing_service.record_agent_usage", AsyncMock()),
    ):
        result = await summarize._summarize("art-1")

    assert result["status"] == "summarized"
    h.assert_clean()


@pytest.mark.asyncio
async def test_assets_releases_the_session_before_each_provider_call():
    from app.pipeline import assets

    h = Harness(
        {
            "lecture_artifacts": _artifact(),
            "extractions": _extraction(),
            "summaries": _summary_row(),
        }
    )
    agent = h.agent(
        generate_flashcards=[FlashcardData(front="q", back="a")],
        generate_quiz=[QuizQuestionData(question_type="short_answer", question="q?")],
    )

    async def save(session, **kwargs):
        await session.flush()
        return [MagicMock()]

    asset_service = MagicMock(save_flashcards=save, save_quiz_questions=save)
    with (
        patch.object(assets, "async_session_factory", h.factory()),
        patch.object(assets, "asset_service", asset_service),
        patch.object(assets, "get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_ai_context", reading((None, None))),
        patch("app.services.billing_service.record_agent_usage", AsyncMock()),
        patch("app.services.concept_service.extract_and_save_concepts", AsyncMock()),
        patch("app.services.notification_service.notify_pipeline_complete", AsyncMock()),
    ):
        result = await assets._generate_assets("art-1")

    assert result["status"] == "processed"
    assert h.calls == ["generate_flashcards", "generate_quiz"]
    h.assert_clean()


@pytest.mark.asyncio
async def test_courseops_releases_the_session_before_the_provider_call(tmp_path):
    from app.pipeline import courseops_task

    doc = MagicMock(
        id="doc-1",
        user_id="user-1",
        course_id="course-1",
        file_path="docs/x.pdf",
        file_type="pdf",
        document_type="syllabus",
    )
    course = MagicMock(code="CSIT302", user_id="user-1")
    h = Harness({"course_documents": doc, "courses": course})
    agent = h.agent(extract_course_ops=CourseOpsResult())

    local = tmp_path / "x.pdf"
    local.write_bytes(b"%PDF")
    storage = MagicMock()
    storage.resolve_path = MagicMock(return_value=local)
    extractor = MagicMock()
    extractor.extract = MagicMock(
        return_value=SimpleNamespace(pages=[SimpleNamespace(text="Syllabus text")])
    )
    with (
        patch.object(courseops_task, "async_session_factory", h.factory()),
        patch.object(courseops_task, "get_storage", return_value=storage),
        patch.object(courseops_task, "LocalStorageBackend", type(storage)),
        patch.object(courseops_task, "get_extractor", return_value=extractor),
        patch.object(courseops_task, "get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_agent_config", reading(None)),
        patch("app.services.billing_service.record_agent_usage", AsyncMock()),
        patch.object(
            courseops_task.courseops_service,
            "process_course_document",
            AsyncMock(return_value={"document_id": "doc-1"}),
        ),
    ):
        result = await courseops_task._process_document("doc-1")

    assert result["document_id"] == "doc-1"
    h.assert_clean()


@pytest.mark.asyncio
async def test_targeted_releases_the_session_before_the_provider_call():
    from app.pipeline import targeted_task

    gen = MagicMock(
        id="gen-1",
        user_id="user-1",
        kind="quiz",
        status="queued",
        course_id="course-1",
        week=3,
        requested_count=2,
    )
    h = Harness({"targeted_generations": gen})
    agent = h.agent(generate_quiz=[QuizQuestionData(question_type="short_answer", question="q?")])
    ctx = SimpleNamespace(
        owner_id="user-1",
        summary_md="s",
        extraction=SimpleNamespace(pages=[], metadata={}),
        focus=None,
        valid_pages={1},
        existing_stems=[],
    )

    async def load(session, g):
        await session.execute("SELECT 1")
        return ctx

    with (
        patch.object(targeted_task, "async_session_factory", h.factory()),
        patch.object(targeted_task, "_load_context", load),
        patch.object(targeted_task, "_persist", AsyncMock()),
        patch.object(targeted_task, "get_user_ai_context", reading((None, None))),
        patch.object(targeted_task, "get_agent", return_value=agent),
        patch.object(targeted_task, "record_agent_usage", AsyncMock()),
        patch.object(
            targeted_task,
            "select_items",
            return_value=SimpleNamespace(kept=[1], dropped_uncited=0, dropped_duplicate=0),
        ),
    ):
        result = await targeted_task._run("gen-1")

    assert result["status"] == "completed"
    h.assert_clean()


@pytest.mark.asyncio
async def test_index_releases_the_session_before_embedding():
    from app.pipeline import index

    artifact = _artifact(status="classified")
    h = Harness({"lecture_artifacts": artifact, "extractions": _extraction()})

    provider = MagicMock()
    provider.dimensions = 3

    def embed(texts):
        h._enter("embed_texts")
        return [[0.0, 0.0, 0.0] for _ in texts]

    provider.embed_texts = embed
    store = AsyncMock(return_value=[MagicMock()])
    with (
        patch.object(index, "async_session_factory", h.factory()),
        patch.object(index, "get_embedding_provider", return_value=provider),
        patch.object(
            index.index_service,
            "chunk_pages",
            return_value=[{"text": "Content", "page_ref": 1, "chunk_idx": 0}],
        ),
        patch.object(index.index_service, "store_artifact_chunks", store),
    ):
        result = await index._index("art-1")

    assert result["status"] == "indexed"
    h.assert_clean()
    # The vectors computed off-session are the ones that get stored.
    assert store.await_args.args[2].vectors == [[0.0, 0.0, 0.0]]


@pytest.mark.asyncio
async def test_reembed_refresh_releases_the_session_before_embedding():
    """The refresh path reads the stored chunks, so a transaction really is open."""
    from app.pipeline import index

    h = Harness(
        {
            "lecture_artifacts": _artifact(status="indexed"),
            "extractions": _extraction(),
            "chunks": "w " * 40,
        }
    )
    provider = MagicMock()
    provider.dimensions = 3
    provider._input_window.return_value = 20
    provider._word_tokens.side_effect = lambda words: [1 for _ in words]

    def embed(texts):
        h._enter("embed_texts")
        return [[0.0, 0.0, 0.0] for _ in texts]

    provider.embed_texts = embed
    store = AsyncMock(return_value=[MagicMock()])
    with (
        patch.object(index, "async_session_factory", h.factory()),
        patch.object(index, "get_embedding_provider", return_value=provider),
        patch.object(index.index_service, "store_artifact_chunks", store),
    ):
        result = await index._index("art-1", refresh="apply")

    assert result["status"] == "reembedded"
    assert "embed_texts" in h.calls
    h.assert_clean()


@pytest.mark.asyncio
async def test_concepts_service_releases_the_session_before_the_provider_call():
    from app.pipeline import concepts_task

    h = Harness({"lecture_artifacts": _artifact(), "extractions": _extraction()})
    agent = h.agent(extract_concepts=ConceptExtractionResult())
    with (
        patch.object(concepts_task, "async_session_factory", h.factory()),
        patch("app.agents.factory.get_agent", return_value=agent),
        patch("app.services.settings_service.get_user_agent_config", reading(None)),
        patch("app.services.billing_service.record_ai_call", AsyncMock()),
    ):
        await concepts_task._extract_concepts_for_artifact("art-1", "user-1")

    h.assert_clean()


def test_every_pipeline_module_that_calls_a_provider_imports_the_release_helper():
    """Static guard for stages nobody has written yet."""
    import ast
    from pathlib import Path

    import app.pipeline as pkg

    root = Path(pkg.__file__).parent
    missing = []
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls_provider = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "get_agent"
            or isinstance(n, ast.Attribute)
            and n.attr == "embed_texts"
            or isinstance(n, ast.Name)
            and n.id == "aembed_texts"
            for n in ast.walk(tree)
        )
        uses_helper = any(
            isinstance(n, ast.Name) and n.id == "release_connection" for n in ast.walk(tree)
        )
        if calls_provider and not uses_helper:
            missing.append(path.name)
    assert not missing, f"call a provider without release_connection(): {missing}"
