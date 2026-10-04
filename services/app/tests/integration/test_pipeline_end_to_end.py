"""The six pipeline stages, run against real Postgres, real files and real extractors.

Only the AI agent and the embedding model are replaced (`FakeAgent`,
`FixedEmbeddings`); everything between them is the production code path: the
upload artifact row, storage, the PDF/DOCX/PPTX extractors, chunking and
pgvector writes, summary versioning, flashcard/quiz persistence, usage metering
and notifications.

Stages open their own sessions from `async_session_factory` and commit, exactly
as the Celery worker does, so these tests cannot use the SAVEPOINT `db_session`.
They create a real user and delete it (and everything it owns) in teardown.
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.core.exceptions import ClassificationError, ExtractionError, SummarizationError
from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.extraction import Extraction
from app.models.flashcard import Flashcard
from app.models.notification import Notification
from app.models.pipeline_run import PipelineRun
from app.models.quiz import QuizQuestion
from app.models.review_item import ReviewItem
from app.models.summary import Summary
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.pipeline.assets import _generate_assets
from app.pipeline.classify import _classify
from app.pipeline.extract import _extract
from app.pipeline.index import _index
from app.pipeline.summarize import _summarize
from app.services import account_service, artifact_service

from ._support import FakeAgent, make_docx, make_pdf, make_pptx

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def owner():
    """A committed user; removed with all of its data afterwards."""
    uid = generate_id()
    async with async_session_factory() as session:
        session.add(
            User(
                id=uid,
                email=f"pipe-{uid[-10:]}@example.com",
                username=f"pipe_{uid[-10:]}",
                role="user",
                tier="pro",
                is_active=True,
                email_verified=True,
                mfa_enabled=False,
            )
        )
        await session.commit()
    yield uid
    async with async_session_factory() as session:
        await account_service.delete_user_account(session, uid)
        await session.commit()


@pytest.fixture
def agent():
    fake = FakeAgent()
    targets = [
        "app.pipeline.classify.get_agent",
        "app.pipeline.summarize.get_agent",
        "app.pipeline.assets.get_agent",
        "app.agents.factory.get_agent",
    ]
    patches = [patch(t, return_value=fake) for t in targets]
    for p in patches:
        p.start()
    yield fake
    for p in patches:
        p.stop()


async def _upload(owner: str, filename: str, content: bytes) -> str:
    async with async_session_factory() as session:
        artifact = await artifact_service.create_upload_artifact(
            session,
            content=content,
            original_filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
            user_id=owner,
        )
        return artifact.id


async def _run_all(owner: str, artifact_id: str) -> dict:
    results = {}
    results["classify"] = await _classify(artifact_id, user_id=owner)
    results["extract"] = await _extract(artifact_id, user_id=owner)
    results["summarize"] = await _summarize(artifact_id, user_id=owner)
    results["index"] = await _index(artifact_id, user_id=owner)
    results["assets"] = await _generate_assets(artifact_id, user_id=owner)
    return results


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    return (await session.execute(stmt)).scalar_one()


@pytest.mark.parametrize(
    ("filename", "builder"),
    [("net-w3.pdf", make_pdf), ("net-w3.docx", make_docx), ("net-w3.pptx", make_pptx)],
)
async def test_full_pipeline_produces_every_artifact_type(owner, agent, filename, builder):
    artifact_id = await _upload(owner, filename, builder())

    results = await _run_all(owner, artifact_id)

    assert results["classify"]["status"] == "classified"
    assert results["classify"]["course_code"] == "NET101"
    assert results["extract"]["status"] == "extracted"
    assert results["extract"]["page_count"] >= 1
    assert results["summarize"]["version"] == 1
    assert results["index"]["chunk_count"] >= 1
    assert results["assets"] == {
        "artifact_id": artifact_id,
        "user_id": owner,
        "status": "processed",
        "flashcard_count": 2,
        "quiz_count": 2,
    }

    async with async_session_factory() as session:
        artifact = await session.get(LectureArtifact, artifact_id)
        assert artifact.status == "processed"
        assert artifact.week == 3
        course = await session.get(Course, artifact.course_id)
        assert course.code == "NET101" and course.user_id == owner

        extraction = (
            await session.execute(select(Extraction).where(Extraction.artifact_id == artifact_id))
        ).scalar_one()
        assert extraction.manifest_json["pages"]

        summary = (
            await session.execute(select(Summary).where(Summary.course_id == course.id))
        ).scalar_one()
        assert summary.version == 1 and "summary" in summary.content_md
        stored = await get_storage().get(summary.file_path)
        assert stored.decode() == summary.content_md

        chunks = (
            (await session.execute(select(Chunk).where(Chunk.artifact_id == artifact_id)))
            .scalars()
            .all()
        )
        assert len(chunks) == results["index"]["chunk_count"]
        assert all(c.embedding is not None for c in chunks)
        assert len({c.stable_id for c in chunks}) == len(chunks)

        assert await _count(session, Flashcard, source_artifact_id=artifact_id) == 2
        assert await _count(session, QuizQuestion, source_artifact_id=artifact_id) == 2

        runs = (
            (
                await session.execute(
                    select(PipelineRun).where(PipelineRun.artifact_id == artifact_id)
                )
            )
            .scalars()
            .all()
        )
        by_stage = {r.stage: r for r in runs}
        assert {"classify", "extract", "summarize", "index", "assets"} <= set(by_stage)
        assert all(r.status == "completed" for r in runs)

        usage = (
            (await session.execute(select(UsageRecord).where(UsageRecord.user_id == owner)))
            .scalars()
            .all()
        )
        # classify(1) + summarize(1) + flashcards/quiz(2) + concepts(1) calls metered.
        assert sum(u.ai_calls_count for u in usage) >= 4
        assert sum(u.ai_tokens_input for u in usage) > 0
        assert await _count(session, Notification, user_id=owner) >= 1

    assert [name for name, _ in agent.calls][:4] == ["classify", "summary", "flashcards", "quiz"]


async def test_classify_sends_the_document_text_to_the_agent(owner, agent):
    artifact_id = await _upload(owner, "net-w3.pdf", make_pdf())
    await _classify(artifact_id, user_id=owner)
    call = dict(agent.calls)["classify"]
    assert "three way handshake" in call["preview"]
    assert call["filename"] == "net-w3.pdf"


async def test_low_confidence_classification_creates_review_item_and_stops(owner, agent):
    agent.confidence = 0.2
    artifact_id = await _upload(owner, "mystery.pdf", make_pdf(["unlabelled text one", "two"]))

    result = await _classify(artifact_id, user_id=owner)

    assert result["status"] == "waiting_review"
    async with async_session_factory() as session:
        artifact = await session.get(LectureArtifact, artifact_id)
        assert artifact.status == "waiting_review"
        assert artifact.course_id is None  # never silently guessed
        items = (
            (await session.execute(select(ReviewItem).where(ReviewItem.entity_id == artifact_id)))
            .scalars()
            .all()
        )
        assert len(items) == 1
        assert items[0].entity_type == "lecture_artifact"
        assert items[0].suggested_values["course_code"] == "NET101"


async def test_extract_is_idempotent(owner, agent):
    artifact_id = await _upload(owner, "net-w3.pdf", make_pdf())
    await _classify(artifact_id, user_id=owner)
    first = await _extract(artifact_id, user_id=owner)
    second = await _extract(artifact_id, user_id=owner)
    assert first["status"] == "extracted"
    assert second["status"] == "already_extracted"
    async with async_session_factory() as session:
        assert await _count(session, Extraction, artifact_id=artifact_id) == 1


async def test_extract_of_corrupt_file_marks_artifact_failed(owner, agent):
    artifact_id = await _upload(owner, "broken.pdf", b"%PDF-1.4 definitely not a pdf")
    with pytest.raises(ExtractionError):
        await _extract(artifact_id, user_id=owner)
    async with async_session_factory() as session:
        artifact = await session.get(LectureArtifact, artifact_id)
        assert artifact.status == "failed"
        run = (
            await session.execute(
                select(PipelineRun).where(
                    PipelineRun.artifact_id == artifact_id, PipelineRun.stage == "extract"
                )
            )
        ).scalar_one()
        assert run.status == "failed" and run.error_message


async def test_stages_reject_unknown_and_unclassified_artifacts(owner, agent):
    with pytest.raises(ClassificationError):
        await _classify("missing-artifact", user_id=owner)
    with pytest.raises(ExtractionError):
        await _extract("missing-artifact", user_id=owner)
    artifact_id = await _upload(owner, "net-w3.pdf", make_pdf())
    with pytest.raises(SummarizationError):
        await _summarize(artifact_id, user_id=owner)  # not classified yet


async def test_second_lecture_same_week_increments_summary_version(owner, agent):
    first_id = await _upload(owner, "net-w3-a.pdf", make_pdf())
    await _run_all(owner, first_id)
    second_id = await _upload(owner, "net-w3-b.pdf", make_pdf(["A different second lecture"]))
    await _classify(second_id, user_id=owner)
    await _extract(second_id, user_id=owner)
    result = await _summarize(second_id, user_id=owner)

    assert result["version"] == 2
    # The agent was handed the previous summary so it could update it.
    assert dict(agent.calls[-1:])["summary"]["existing"] is not None
    async with async_session_factory() as session:
        summaries = (
            (await session.execute(select(Summary).where(Summary.id == result["summary_id"])))
            .scalars()
            .all()
        )
        assert len(summaries) == 1  # one row per course+week, versioned
        assert set(summaries[0].source_artifacts) == {first_id, second_id}


@pytest.mark.xfail(
    strict=True,
    reason="BUG (floor 4): re-summarizing overwrites the prior summary in place (DB content_md and "
    "the storage file at the same key); only the version integer is kept, so the prior version's "
    "content is destroyed",
)
async def test_resummarize_retains_prior_version_content(owner, agent):
    first_id = await _upload(owner, "net-w3-a.pdf", make_pdf())
    await _run_all(owner, first_id)
    async with async_session_factory() as session:
        v1_text = (
            await session.execute(
                select(Summary.content_md).join(Course).where(Course.user_id == owner)
            )
        ).scalar_one()
    assert "new summary" in v1_text

    second_id = await _upload(owner, "net-w3-b.pdf", make_pdf(["Another lecture"]))
    await _classify(second_id, user_id=owner)
    await _extract(second_id, user_id=owner)
    await _summarize(second_id, user_id=owner)

    root = Path(get_storage().resolve_path("summaries")).parent
    retained = [
        p for p in root.rglob("*") if p.is_file() and "new summary" in p.read_text(errors="ignore")
    ]
    assert retained, "no stored copy of the version-1 summary remains"


async def test_index_without_extraction_fails_cleanly(owner, agent):
    from app.core.exceptions import IndexingError

    artifact_id = await _upload(owner, "net-w3.pdf", make_pdf())
    with pytest.raises(IndexingError):
        await _index(artifact_id, user_id=owner)


async def test_classify_does_not_leak_other_users_course_codes(owner, agent):
    other = generate_id()
    async with async_session_factory() as session:
        session.add(
            User(
                id=other,
                email=f"other-{other[-10:]}@example.com",
                username=f"other_{other[-10:]}",
                role="user",
                tier="free",
                is_active=True,
                email_verified=True,
                mfa_enabled=False,
            )
        )
        await session.flush()
        session.add(Course(id=generate_id(), code="SECRET999", user_id=other))
        await session.commit()
    try:
        artifact_id = await _upload(owner, "net-w3.pdf", make_pdf())
        await _classify(artifact_id, user_id=owner)
        known = dict(agent.calls)["classify"]["known_courses"]
        assert "SECRET999" not in known
    finally:
        async with async_session_factory() as session:
            await account_service.delete_user_account(session, other)
            await session.commit()
