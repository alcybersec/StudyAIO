"""Floor 4: re-summarizing never overwrites a prior version's blob."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ExtractionData, SummaryResult
from app.core.storage import LocalStorageBackend


async def _run(tmp_path, existing_version):
    from app.pipeline.summarize import _summarize
    from app.services import summary_service as real

    course = MagicMock()
    course.id = "course-001"
    course.code = "CSIT302"
    artifact = MagicMock()
    artifact.id = "art-001"
    artifact.course_id = "course-001"
    artifact.week = 5
    artifact.course = course
    session = AsyncMock()
    session.add = MagicMock()
    res = MagicMock()
    res.unique.return_value = res
    res.scalar_one_or_none.return_value = artifact
    session.execute.return_value = res

    svc = MagicMock()
    svc.get_week_extractions = AsyncMock(return_value=[MagicMock(artifact_id="art-001")])
    svc.merge_extractions.return_value = ExtractionData(
        pages=[{"page_number": 1, "text": "x", "images": []}],
        metadata={"artifact_ids": ["art-001"]},
    )
    existing = None
    if existing_version:
        existing = MagicMock()
        existing.version = existing_version
        existing.content_md = "old"
    svc.get_existing_summary = AsyncMock(return_value=existing)
    svc.build_summary_storage_key.side_effect = real.build_summary_storage_key
    svc.create_or_update_summary = AsyncMock(
        return_value=MagicMock(id="s", version=(existing_version or 0) + 1)
    )
    agent = AsyncMock()
    agent.generate_summary.return_value = SummaryResult(content_md="NEW", embedded_images=[])
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    with (
        patch("app.pipeline.summarize.async_session_factory") as factory,
        patch("app.pipeline.summarize.summary_service", svc),
        patch("app.pipeline.summarize.get_agent", return_value=agent),
        patch("app.pipeline.summarize.get_storage", return_value=storage),
    ):
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await _summarize("art-001")
    return svc


@pytest.mark.asyncio
class TestSummarizeVersionedBlob:
    async def test_first_summary_written_to_v1_key(self, tmp_path):
        svc = await _run(tmp_path, None)
        d = tmp_path / "summaries" / "course-001"
        assert (d / "Week5.v1.md").read_bytes() == b"NEW"
        assert svc.create_or_update_summary.await_args.kwargs["file_path"].endswith("Week5.v1.md")

    async def test_second_summary_writes_v2_and_leaves_v1_intact(self, tmp_path):
        d = tmp_path / "summaries" / "course-001"
        d.mkdir(parents=True)
        (d / "Week5.v1.md").write_bytes(b"V1-BYTES")
        svc = await _run(tmp_path, 1)
        assert (d / "Week5.v1.md").read_bytes() == b"V1-BYTES"
        assert (d / "Week5.v2.md").read_bytes() == b"NEW"
        assert svc.create_or_update_summary.await_args.kwargs["file_path"].endswith("Week5.v2.md")

    async def test_existing_target_key_fails_loudly_without_overwrite(self, tmp_path):
        d = tmp_path / "summaries" / "course-001"
        d.mkdir(parents=True)
        (d / "Week5.v2.md").write_bytes(b"PRECIOUS")
        with pytest.raises(Exception):  # noqa: B017, PT011
            await _run(tmp_path, 1)
        assert (d / "Week5.v2.md").read_bytes() == b"PRECIOUS"
