"""Tests for summary_service."""

from unittest.mock import MagicMock, patch

from app.services import summary_service


class TestMergeExtractions:
    """Tests for merge_extractions()."""

    def test_merge_single_extraction(self):
        """Single extraction merges correctly."""
        extraction = MagicMock()
        extraction.artifact_id = "art-1"
        extraction.manifest_json = {
            "pages": [
                {"page_number": 1, "text": "Page 1 text", "images": []},
                {"page_number": 2, "text": "Page 2 text", "images": []},
            ],
            "metadata": {"source_type": "pdf"},
        }

        result = summary_service.merge_extractions([extraction])

        assert len(result.pages) == 2
        assert result.metadata["artifact_ids"] == ["art-1"]
        assert result.metadata["extraction_count"] == 1

    def test_merge_multiple_extractions(self):
        """Multiple extractions concatenate pages."""
        ext1 = MagicMock()
        ext1.artifact_id = "art-1"
        ext1.manifest_json = {
            "pages": [{"page_number": 1, "text": "First file page 1", "images": []}],
            "metadata": {},
        }

        ext2 = MagicMock()
        ext2.artifact_id = "art-2"
        ext2.manifest_json = {
            "pages": [{"page_number": 1, "text": "Second file page 1", "images": []}],
            "metadata": {},
        }

        result = summary_service.merge_extractions([ext1, ext2])

        assert len(result.pages) == 2
        assert result.metadata["artifact_ids"] == ["art-1", "art-2"]
        assert result.metadata["extraction_count"] == 2

    def test_merge_empty_list(self):
        """Empty list returns empty ExtractionData."""
        result = summary_service.merge_extractions([])

        assert result.pages == []
        assert result.metadata["extraction_count"] == 0


class TestGetExistingSummary:
    """Tests for get_existing_summary()."""

    async def test_returns_none_when_no_match(self, mock_session):
        """No existing summary returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await summary_service.get_existing_summary(mock_session, "course-1", 5)
        assert result is None

    async def test_returns_summary_when_exists(self, mock_session):
        """Existing summary is returned."""
        existing = MagicMock()
        existing.id = "summary-1"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        result = await summary_service.get_existing_summary(mock_session, "course-1", 5)
        assert result.id == "summary-1"


class TestCreateOrUpdateSummary:
    """Tests for create_or_update_summary()."""

    @patch("app.services.summary_service.get_existing_summary")
    async def test_create_new_summary(self, mock_get_existing, mock_session):
        """Creates new summary when none exists."""
        mock_get_existing.return_value = None

        result = await summary_service.create_or_update_summary(
            session=mock_session,
            course_id="course-1",
            week=5,
            content_md="# Summary",
            file_path="/app/data/summaries/CSIT302/CSIT302_Week5.md",
            source_artifact_ids=["art-1"],
        )

        assert result.course_id == "course-1"
        assert result.week == 5
        assert result.version == 1
        assert result.content_md == "# Summary"
        mock_session.add.assert_called_once()

    @patch("app.services.summary_service.get_existing_summary")
    async def test_update_increments_version(self, mock_get_existing, mock_session):
        """Updating existing summary increments version."""
        existing = MagicMock()
        existing.version = 2
        existing.source_artifacts = ["art-1"]
        mock_get_existing.return_value = existing

        result = await summary_service.create_or_update_summary(
            session=mock_session,
            course_id="course-1",
            week=5,
            content_md="# Updated Summary",
            file_path="/path/to/file.md",
            source_artifact_ids=["art-2"],
        )

        assert result.version == 3
        assert result.content_md == "# Updated Summary"
        assert "art-1" in result.source_artifacts
        assert "art-2" in result.source_artifacts


class TestBuildSummaryFilePath:
    """Tests for build_summary_file_path()."""

    def test_builds_correct_path(self, tmp_path):
        """Path follows <dir>/<course>/<course>_Week<N>.md pattern."""
        result = summary_service.build_summary_file_path(str(tmp_path), "CSIT302", 5)

        assert result.name == "CSIT302_Week5.md"
        assert result.parent.name == "CSIT302"

    def test_creates_directory(self, tmp_path):
        """Creates course directory if it doesn't exist."""
        summary_service.build_summary_file_path(str(tmp_path), "CSIT302", 5)

        assert (tmp_path / "CSIT302").is_dir()
