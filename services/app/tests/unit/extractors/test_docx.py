"""Tests for DocxExtractor."""

import pytest

from app.core.exceptions import ExtractionError
from app.extractors.docx import DocxExtractor


class TestDocxExtractor:
    """Tests for DOCX extraction."""

    def test_extract_basic(self, simple_docx, tmp_path):
        """Extract text from a simple DOCX."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = DocxExtractor()
        result = extractor.extract(simple_docx, output_dir)

        assert result.page_count >= 1
        assert len(result.pages) >= 1
        # Find text across all pages
        all_text = " ".join(p.text for p in result.pages)
        assert "CSIT302" in all_text
        assert "firewall" in all_text.lower()

    def test_extract_splits_by_headings(self, simple_docx, tmp_path):
        """DOCX is split into sections by headings."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = DocxExtractor()
        result = extractor.extract(simple_docx, output_dir)

        # simple_docx has 2 heading-separated sections
        assert result.page_count >= 2

    def test_extract_manifest_format(self, simple_docx, tmp_path):
        """to_manifest() produces correct structure."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = DocxExtractor()
        result = extractor.extract(simple_docx, output_dir)
        manifest = result.to_manifest()

        assert manifest["metadata"]["source_type"] == "docx"
        assert "pages" in manifest

    def test_extract_corrupt_file(self, tmp_path):
        """Corrupt file raises ExtractionError."""
        corrupt = tmp_path / "bad.docx"
        corrupt.write_bytes(b"not a docx")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = DocxExtractor()
        with pytest.raises(ExtractionError, match="Failed to open DOCX"):
            extractor.extract(corrupt, output_dir)

    def test_extract_empty_docx(self, tmp_path):
        """Empty DOCX returns at least one page."""
        import docx

        docx_path = tmp_path / "empty.docx"
        document = docx.Document()
        document.save(str(docx_path))

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = DocxExtractor()
        result = extractor.extract(docx_path, output_dir)

        # Even an empty document should produce at least one page
        assert result.page_count >= 1
