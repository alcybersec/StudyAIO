"""Targeted (weak-spot) quiz/card generation, run in the worker (ADR 0007 Decision 5).

``POST /api/weak-spots/targeted`` validates, records a ``targeted_generations`` row
and enqueues :func:`generate_targeted_items` with the row id only. The request
handler never obtains an adapter (ADR 0003 is unchanged); this task is the only
new ``get_agent`` call site.

Rules this module owns:

* **Owner.** The row names its owner; everything after the row is loaded acts as
  ``row.user_id`` (credentials, billing, reads), never as anything the payload says.
* **Insert-only.** Kept items are inserted with ``origin='targeted'``; no existing
  question or card is updated, archived or deleted (floor 4).
* **Citation and dedup.** Items citing a page the target extraction lacks, and
  duplicates of the unit's active items, are dropped and counted
  (:mod:`app.pipeline.targeted_items`).
* **No provider text.** A failure stores a short ``error_code``; the exception
  message goes nowhere a client can read it (floor 2).
* **No stuck unit.** A beat job fails rows left ``queued``/``running`` past
  ``STUCK_GENERATION_SECONDS`` so the in-flight unique index cannot block a unit.
"""

import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import Select, select, update

from app.agents.base import ExtractionData, GenerationFocus
from app.agents.factory import get_agent
from app.agents.transient import TransientAgentError
from app.core.database import async_session_factory, run_async
from app.core.exceptions import AgentError
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.concept import Concept
from app.models.course import Course
from app.models.extraction import Extraction
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.summary import Summary
from app.models.targeted_generation import TargetedGeneration
from app.pipeline import metrics
from app.pipeline.resilience import backoff_countdown
from app.pipeline.targeted_items import (
    AVOID_LIMIT,
    MISSED_LIMIT,
    MISSED_WINDOW_DAYS,
    Attempt,
    Selection,
    TargetCandidate,
    build_topics,
    choose_target,
    focus_topic_for,
    latest_missed,
    select_items,
)
from app.services.billing_service import record_agent_usage
from app.services.settings_service import get_user_ai_context
from app.services.summary_service import merge_extractions
from app.worker import celery_app

logger = structlog.get_logger()

TARGETED_TASK_NAME = "app.pipeline.targeted_task.generate_targeted_items"
RECOVERY_TASK_NAME = "app.pipeline.targeted_task.recover_stuck_generations"

#: Transient provider errors retry once. Worst case before the row is final is
#: (MAX_RETRIES + 1) hard limits plus MAX_RETRIES back-offs, and
#: ``STUCK_GENERATION_SECONDS`` is above that (see the unit test).
MAX_RETRIES = 1
STUCK_GENERATION_SECONDS = 40 * 60
IN_FLIGHT = ("queued", "running")
CONCEPT_LIMIT = 20


class TargetedError(Exception):
    """A generation failed for a reason that has a stable ``code`` (never provider text)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class TargetContext:
    """Everything read from the database before the model is called."""

    owner_id: str
    course_code: str
    artifact_id: str
    extraction: ExtractionData
    summary_md: str
    valid_pages: set[int]
    focus: GenerationFocus
    existing_stems: list[str]
    next_version: int


# ── owner-scoped statements (each carries the row's owner) ─────────────


def _course_stmt(owner_id: str, course_id: str) -> Select:
    return select(Course.code).where(Course.id == course_id, Course.user_id == owner_id)


def _artifacts_stmt(owner_id: str, course_id: str, week: int) -> Select:
    return select(LectureArtifact.id, LectureArtifact.created_at).where(
        LectureArtifact.user_id == owner_id,
        LectureArtifact.course_id == course_id,
        LectureArtifact.week == week,
        LectureArtifact.status == "processed",
    )


def _attempts_stmt(owner_id: str, course_id: str, week: int, since: datetime) -> Select:
    # Archived questions stay: an answer is history of what the student knows.
    return (
        select(
            QuizQuestion.id,
            QuizQuestion.source_artifact_id,
            QuizQuestion.question,
            QuizQuestion.source_page_ref,
            QuizAttempt.is_correct,
            QuizAttempt.created_at,
        )
        .join(QuizAttempt, QuizAttempt.quiz_question_id == QuizQuestion.id)
        .join(Course, Course.id == QuizQuestion.course_id)
        .where(
            Course.user_id == owner_id,
            QuizQuestion.course_id == course_id,
            QuizQuestion.week == week,
            QuizAttempt.created_at >= since,
        )
    )


def _titles_stmt(owner_id: str, artifact_id: str, pages: list[int] | None) -> Select:
    stmt = (
        select(Chunk.page_ref, Chunk.slide_title)
        .join(LectureArtifact, LectureArtifact.id == Chunk.artifact_id)
        .where(
            LectureArtifact.user_id == owner_id,
            Chunk.artifact_id == artifact_id,
            Chunk.slide_title.is_not(None),
        )
        .order_by(Chunk.page_ref, Chunk.id)
    )
    if pages is not None:
        stmt = stmt.where(Chunk.page_ref.in_(pages))
    return stmt


def _concepts_stmt(owner_id: str, course_id: str, week: int) -> Select:
    return (
        select(Concept.name)
        .where(
            Concept.user_id == owner_id,
            Concept.course_id == course_id,
            Concept.source_weeks.contains([week]),
        )
        .order_by(Concept.mention_count.desc(), Concept.name)
        .limit(CONCEPT_LIMIT)
    )


def _existing_stmt(kind: str, owner_id: str, course_id: str, week: int) -> Select:
    model, column = (QuizQuestion, QuizQuestion.question)
    if kind == "flashcards":
        model, column = (Flashcard, Flashcard.front)
    return (
        select(column, model.generation_version)
        .join(Course, Course.id == model.course_id)
        .where(
            Course.user_id == owner_id,
            model.course_id == course_id,
            model.week == week,
            model.archived_at.is_(None),
        )
        .order_by(model.created_at.desc(), model.id.desc())
    )


def _summary_stmt(owner_id: str, course_id: str, week: int) -> Select:
    return (
        select(Summary.content_md)
        .join(Course, Course.id == Summary.course_id)
        .where(Course.user_id == owner_id, Summary.course_id == course_id, Summary.week == week)
    )


def _extraction_stmt(owner_id: str, artifact_id: str) -> Select:
    return (
        select(Extraction)
        .join(LectureArtifact, LectureArtifact.id == Extraction.artifact_id)
        .where(LectureArtifact.user_id == owner_id, Extraction.artifact_id == artifact_id)
    )


# ── database steps ─────────────────────────────────────────────────────


async def _claim(session, generation_id: str) -> TargetedGeneration | None:
    """Lock the row and mark it running; None when it is not (or no longer) in flight.

    The id was minted by the owner's own request; the owner for everything that
    follows is read from the row.
    """
    result = await session.execute(
        select(TargetedGeneration)
        .where(TargetedGeneration.id == generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = result.scalar_one_or_none()
    if row is None or row.status not in IN_FLIGHT:
        return None
    row.status = "running"
    await session.commit()
    return row


async def _load_context(session, gen: TargetedGeneration) -> TargetContext:
    """Read the unit's target artifact, text, topics and existing items (all owner-scoped)."""
    owner = gen.user_id
    code = (await session.execute(_course_stmt(owner, gen.course_id))).scalar_one_or_none()
    if code is None:
        raise TargetedError("no_source")
    artifacts = (await session.execute(_artifacts_stmt(owner, gen.course_id, gen.week))).all()
    if not artifacts:
        raise TargetedError("no_source")

    since = datetime.now(UTC) - timedelta(days=MISSED_WINDOW_DAYS)
    rows = (await session.execute(_attempts_stmt(owner, gen.course_id, gen.week, since))).all()
    missed = latest_missed(
        [
            Attempt(
                question_id=r[0],
                artifact_id=r[1],
                stem=r[2],
                page_ref=r[3],
                is_correct=r[4],
                created_at=r[5],
            )
            for r in rows
        ]
    )
    counts = Counter(m.artifact_id for m in missed)
    target = choose_target(
        [TargetCandidate(a_id, created, counts.get(a_id, 0)) for a_id, created in artifacts]
    )
    if target is None:
        raise TargetedError("no_source")
    artifact_id = target.artifact_id

    extraction = (await session.execute(_extraction_stmt(owner, artifact_id))).scalar_one_or_none()
    if extraction is None:
        raise TargetedError("no_source")
    data = merge_extractions([extraction])
    data.metadata["course_code"] = code
    data.metadata["week"] = gen.week
    valid_pages = {
        int(p["page_number"])
        for p in data.pages
        if isinstance(p, dict) and isinstance(p.get("page_number"), int)
    }
    if not valid_pages:
        raise TargetedError("no_source")

    summary_md = (
        await session.execute(_summary_stmt(owner, gen.course_id, gen.week))
    ).scalar_one_or_none() or ""

    page_refs = sorted({m.page_ref for m in missed if m.artifact_id == artifact_id} & valid_pages)
    titles: list[str] = []
    if page_refs:
        title_rows = (await session.execute(_titles_stmt(owner, artifact_id, page_refs))).all()
        titles = [t for _, t in title_rows]
    concepts = list(
        (await session.execute(_concepts_stmt(owner, gen.course_id, gen.week))).scalars()
    )
    topics = build_topics(titles, concepts)
    if not topics:
        every = (await session.execute(_titles_stmt(owner, artifact_id, None))).all()
        topics = build_topics([t for _, t in every], [])
    if not topics:
        topics = [f"Week {gen.week} key ideas"]

    existing = (
        await session.execute(_existing_stmt(gen.kind, owner, gen.course_id, gen.week))
    ).all()
    stems = [r[0] for r in existing]
    next_version = max((r[1] for r in existing), default=1)

    focus = GenerationFocus(
        topics=topics,
        missed_questions=[m.stem for m in missed[:MISSED_LIMIT]],
        avoid=stems[:AVOID_LIMIT],
        page_refs=page_refs,
    )
    return TargetContext(
        owner_id=owner,
        course_code=code,
        artifact_id=artifact_id,
        extraction=data,
        summary_md=summary_md,
        valid_pages=valid_pages,
        focus=focus,
        existing_stems=stems,
        next_version=next_version,
    )


async def _persist(
    session, gen: TargetedGeneration, ctx: TargetContext, selection: Selection
) -> None:
    """Insert the kept items and complete the row, in one transaction (insert-only)."""
    locked = await session.execute(
        select(TargetedGeneration)
        .where(TargetedGeneration.id == gen.id, TargetedGeneration.user_id == ctx.owner_id)
        .with_for_update()
        # expire_on_commit=False keeps the stale in-memory ``running`` object in the
        # identity map; refresh it so a row recovered meanwhile is seen as such.
        .execution_options(populate_existing=True)
    )
    row = locked.scalar_one_or_none()
    if row is None or row.status != "running":
        # Recovered or finished by another worker: add nothing.
        raise TargetedError("superseded")
    for item in selection.kept:
        topic = focus_topic_for(gen.kind, item, ctx.focus.topics)
        common = {
            "course_id": gen.course_id,
            "week": gen.week,
            "source_artifact_id": ctx.artifact_id,
            "source_page_ref": item.source_page_ref,
            "generation_version": ctx.next_version,
            "origin": "targeted",
            "targeted_generation_id": gen.id,
            "focus_topic": topic,
        }
        if gen.kind == "quiz":
            session.add(
                QuizQuestion(
                    question_type=item.question_type,
                    question=item.question,
                    options_json=item.options,
                    correct_answer=item.correct_answer,
                    explanation=item.explanation,
                    **common,
                )
            )
        else:
            session.add(Flashcard(front=item.front, back=item.back, tags=item.tags, **common))
    row.status = "completed"
    row.created_count = len(selection.kept)
    row.dropped_duplicate_count = selection.dropped_duplicate
    row.dropped_uncited_count = selection.dropped_uncited
    row.topics = list(ctx.focus.topics)
    row.error_code = None
    row.completed_at = datetime.now(UTC)
    await session.commit()


async def _fail(generation_id: str, user_id: str, code: str) -> None:
    """Mark an in-flight row of ``user_id`` failed with a short code (no-op once finished)."""
    async with async_session_factory() as session:
        await session.execute(
            update(TargetedGeneration)
            .where(
                TargetedGeneration.id == generation_id,
                TargetedGeneration.user_id == user_id,
                TargetedGeneration.status.in_(IN_FLIGHT),
            )
            .values(status="failed", error_code=code, completed_at=datetime.now(UTC))
        )
        await session.commit()


# ── the run ────────────────────────────────────────────────────────────


def _count(stage: str, started: float, outcome: str) -> None:
    if outcome == "completed":
        metrics.TARGETED_GENERATIONS.labels(stage=stage, outcome="completed").inc()
        metrics.TARGETED_SECONDS.labels(stage=stage, outcome="completed").observe(
            time.monotonic() - started
        )
    elif outcome == "retry":
        metrics.TARGETED_GENERATIONS.labels(stage=stage, outcome="retry").inc()
    else:
        metrics.TARGETED_GENERATIONS.labels(stage=stage, outcome="failed").inc()
        metrics.TARGETED_SECONDS.labels(stage=stage, outcome="failed").observe(
            time.monotonic() - started
        )


def _count_failure(stage: str, exc: BaseException) -> None:
    metrics.TARGETED_FAILURES.labels(stage=stage, error_class=type(exc).__name__).inc()


def _result(gen_id: str, owner: str | None, status: str, created: int = 0) -> dict:
    return {
        "generation_id": gen_id,
        "user_id": owner,
        "status": status,
        "created_count": created,
    }


async def _generate(session, gen: TargetedGeneration, ctx: TargetContext) -> list:
    """One adapter call as the owner, metered; returns the model's items."""
    owner = gen.user_id
    user_config, language = await get_user_ai_context(session, owner)
    agent = get_agent(user_settings=user_config, output_language=language)
    kwargs = {
        "summary": ctx.summary_md,
        "extraction": ctx.extraction,
        "count": gen.requested_count,
        "focus": ctx.focus,
    }
    try:
        if gen.kind == "quiz":
            items = await agent.generate_quiz(**kwargs)
        else:
            items = await agent.generate_flashcards(**kwargs)
    finally:
        # A failed call may still have been billed by the provider: meter what ran.
        await record_agent_usage(session, owner, agent)
        await session.commit()
    return list(items)


async def _run(generation_id: str, *, final: bool = True) -> dict:
    """Run one targeted generation end to end.

    Args:
        generation_id: ``targeted_generations.id``.
        final: True on the last attempt: a transient error then fails the row instead
            of being re-raised for another retry.

    Returns:
        ``{generation_id, user_id, status, created_count}``; ``status`` is
        ``completed``, ``failed`` or ``skipped`` (not in flight).

    Raises:
        TransientAgentError: Transient provider error and not ``final``; the task retries.
        SoftTimeLimitExceeded: The soft time limit hit and not ``final``; the task retries.
    """
    started = time.monotonic()
    async with async_session_factory() as session:
        gen = await _claim(session, generation_id)
        if gen is None:
            metrics.TARGETED_GENERATIONS.labels(stage="unknown", outcome="skipped").inc()
            logger.info("targeted_generation_skipped", generation_id=generation_id)
            return _result(generation_id, None, "skipped")
        stage, owner = gen.kind, gen.user_id
        try:
            ctx = await _load_context(session, gen)
            items = await _generate(session, gen, ctx)
            if not items:
                raise TargetedError("empty_output")
            selection = select_items(
                gen.kind, items, valid_pages=ctx.valid_pages, existing=ctx.existing_stems
            )
            await _persist(session, gen, ctx, selection)
        except (TransientAgentError, SoftTimeLimitExceeded) as exc:
            _count_failure(stage, exc)
            if not final:
                _count(stage, started, "retry")
                raise
            code = "timeout" if isinstance(exc, SoftTimeLimitExceeded) else "ai_unavailable"
            await _fail(generation_id, owner, code)
            _count(stage, started, "failed")
            logger.warning(
                "targeted_generation_failed",
                generation_id=generation_id,
                user_id=owner,
                kind=stage,
                error_code=code,
                error_class=type(exc).__name__,
            )
            return _result(generation_id, owner, "failed")
        except Exception as exc:
            code = exc.code if isinstance(exc, TargetedError) else None
            if code is None:
                code = "ai_error" if isinstance(exc, AgentError) else "internal_error"
            await _fail(generation_id, owner, code)
            _count(stage, started, "failed")
            _count_failure(stage, exc)
            logger.warning(
                "targeted_generation_failed",
                generation_id=generation_id,
                user_id=owner,
                kind=stage,
                error_code=code,
                error_class=type(exc).__name__,
            )
            return _result(generation_id, owner, "failed")

    _count(stage, started, "completed")
    metrics.TARGETED_ITEMS.labels(stage=stage, outcome="created").inc(len(selection.kept))
    metrics.TARGETED_ITEMS.labels(stage=stage, outcome="dropped_uncited").inc(
        selection.dropped_uncited
    )
    metrics.TARGETED_ITEMS.labels(stage=stage, outcome="dropped_duplicate").inc(
        selection.dropped_duplicate
    )
    logger.info(
        "targeted_generation_completed",
        generation_id=generation_id,
        user_id=owner,
        kind=stage,
        created=len(selection.kept),
        dropped_uncited=selection.dropped_uncited,
        dropped_duplicate=selection.dropped_duplicate,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return _result(generation_id, owner, "completed", len(selection.kept))


@celery_app.task(
    name=TARGETED_TASK_NAME,
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=30,
)
def generate_targeted_items(self, generation_id: str) -> dict:
    """Celery task: generate targeted quiz questions or flashcards for one weak unit.

    Args:
        generation_id: ``targeted_generations.id`` (the owner is read from the row).

    Returns:
        ``{generation_id, user_id, status, created_count}``.
    """
    final = self.request.retries >= self.max_retries
    try:
        return run_async(_run(generation_id, final=final))
    except (TransientAgentError, SoftTimeLimitExceeded) as exc:
        if final:
            # Raised outside the run's own handling (e.g. while claiming): the stuck-row
            # recovery job fails the row if it is left in flight.
            raise
        raise self.retry(exc=exc, countdown=backoff_countdown(self.request.retries)) from exc


# ── stuck-row recovery (worker-only, beat) ─────────────────────────────


async def _recover_stuck(now: datetime | None = None) -> list[str]:
    """Fail rows left in flight past the threshold; touches no item (floor 4).

    Args:
        now: Clock override for tests.

    Returns:
        Ids of the rows marked failed (``error_code='timeout'``).
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=STUCK_GENERATION_SECONDS)
    async with async_session_factory() as session:
        result = await session.execute(
            update(TargetedGeneration)
            .where(TargetedGeneration.status.in_(IN_FLIGHT), TargetedGeneration.updated_at < cutoff)
            .values(status="failed", error_code="timeout", completed_at=now)
            .returning(TargetedGeneration.id)
        )
        ids = list(result.scalars().all())
        await session.commit()
    return ids


@celery_app.task(name=RECOVERY_TASK_NAME)
def recover_stuck_generations() -> dict:
    """Celery beat task: fail targeted generations stuck in ``queued``/``running``."""
    failed = run_async(_recover_stuck())
    if failed:
        metrics.TARGETED_GENERATIONS.labels(stage="unknown", outcome="recovered").inc(len(failed))
        logger.warning("targeted_generation_recovered", count=len(failed))
    return {"failed": len(failed)}


__all__ = [
    "TARGETED_TASK_NAME",
    "TargetContext",
    "TargetedError",
    "generate_targeted_items",
    "recover_stuck_generations",
]
