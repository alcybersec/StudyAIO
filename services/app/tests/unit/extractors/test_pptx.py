"""Tests for PptxExtractor."""

import pytest

from app.core.exceptions import ExtractionError
from app.extractors.pptx import PptxExtractor


class TestPptxExtractor:
    """Tests for PPTX extraction."""

    def test_extract_basic(self, simple_pptx, tmp_path):
        """Extract text from a simple PPTX."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        result = extractor.extract(simple_pptx, output_dir)

        assert result.page_count == 3
        assert len(result.pages) == 3
        # Slide 1
        assert "CSIT302" in result.pages[0].text
        # Slide 2
        assert "Firewalls" in result.pages[1].text

    def test_extract_speaker_notes(self, simple_pptx, tmp_path):
        """Speaker notes are included in slide text."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        result = extractor.extract(simple_pptx, output_dir)

        # Slide 3 has speaker notes
        slide3_text = result.pages[2].text
        assert "Speaker Notes" in slide3_text
        assert "IDS and IPS" in slide3_text

    def test_extract_page_numbers_match_slides(self, simple_pptx, tmp_path):
        """Page numbers correspond to slide numbers."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        result = extractor.extract(simple_pptx, output_dir)

        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2
        assert result.pages[2].page_number == 3

    def test_extract_manifest_format(self, simple_pptx, tmp_path):
        """to_manifest() produces correct structure."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        result = extractor.extract(simple_pptx, output_dir)
        manifest = result.to_manifest()

        assert manifest["metadata"]["source_type"] == "pptx"
        assert len(manifest["pages"]) == 3

    def test_extract_corrupt_file(self, tmp_path):
        """Corrupt file raises ExtractionError."""
        corrupt = tmp_path / "bad.pptx"
        corrupt.write_bytes(b"not a pptx")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        with pytest.raises(ExtractionError, match="Failed to open PPTX"):
            extractor.extract(corrupt, output_dir)

    def test_extract_empty_pptx(self, tmp_path):
        """Empty PPTX returns zero pages."""
        from pptx import Presentation

        pptx_path = tmp_path / "empty.pptx"
        prs = Presentation()
        prs.save(str(pptx_path))

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PptxExtractor()
        result = extractor.extract(pptx_path, output_dir)

        assert result.page_count == 0
        assert result.pages == []
