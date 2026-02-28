"""Tests for PdfExtractor."""

import pytest

from app.core.exceptions import ExtractionError
from app.extractors.pdf import PdfExtractor


class TestPdfExtractor:
    """Tests for PDF extraction."""

    def test_extract_basic(self, simple_pdf, tmp_path):
        """Extract text and pages from a simple PDF."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        result = extractor.extract(simple_pdf, output_dir)

        assert result.page_count == 2
        assert len(result.pages) == 2
        assert "CSIT302" in result.pages[0].text
        assert "Network Security" in result.pages[0].text
        assert "Firewalls" in result.pages[1].text

    def test_extract_page_numbers(self, simple_pdf, tmp_path):
        """Verify page numbering starts at 1."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        result = extractor.extract(simple_pdf, output_dir)

        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2

    def test_extract_creates_images_dir(self, simple_pdf, tmp_path):
        """Images directory is created even with no images."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        extractor.extract(simple_pdf, output_dir)

        assert (output_dir / "images").exists()

    def test_extract_manifest_format(self, simple_pdf, tmp_path):
        """to_manifest() produces correct structure."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        result = extractor.extract(simple_pdf, output_dir)
        manifest = result.to_manifest()

        assert "pages" in manifest
        assert "metadata" in manifest
        assert manifest["metadata"]["source_type"] == "pdf"
        assert len(manifest["pages"]) == 2
        assert "text" in manifest["pages"][0]
        assert "images" in manifest["pages"][0]
        assert "page_number" in manifest["pages"][0]

    def test_extract_corrupt_file(self, tmp_path):
        """Corrupt file raises ExtractionError."""
        corrupt = tmp_path / "bad.pdf"
        corrupt.write_bytes(b"not a pdf")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        with pytest.raises(ExtractionError, match="Failed to open PDF"):
            extractor.extract(corrupt, output_dir)

    def test_extract_single_page_empty_text(self, tmp_path):
        """PDF with an empty page returns page with empty text."""
        import fitz

        pdf_path = tmp_path / "blank.pdf"
        doc = fitz.open()
        doc.new_page(width=595, height=842)  # blank page, no text
        doc.save(str(pdf_path))
        doc.close()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extractor = PdfExtractor()
        result = extractor.extract(pdf_path, output_dir)

        assert result.page_count == 1
        assert result.pages[0].text.strip() == ""
