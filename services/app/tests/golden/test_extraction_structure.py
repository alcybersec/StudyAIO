"""Golden tests for extraction manifest structure.

Validates that extractors produce manifests with the correct schema:
- manifest has `pages` (list) and `metadata` (dict)
- each page has `page_number` (int), `text` (str), `images` (list)
- each image has `filename` (str), `caption` (str), `position` (str)
- page numbers are sequential starting from 1
"""

from pathlib import Path

import pytest

from app.extractors.base import ExtractionResult, ImageInfo, PageContent


# ── Schema validation helpers ────────────────────────────────────────


def validate_manifest(manifest: dict) -> None:
    """Assert that a manifest dict conforms to the expected schema."""
    assert isinstance(manifest, dict), "Manifest must be a dict"
    assert "pages" in manifest, "Manifest must have 'pages' key"
    assert "metadata" in manifest, "Manifest must have 'metadata' key"

    assert isinstance(manifest["pages"], list), "'pages' must be a list"
    assert isinstance(manifest["metadata"], dict), "'metadata' must be a dict"

    for i, page in enumerate(manifest["pages"]):
        assert isinstance(page, dict), f"Page {i} must be a dict"
        assert "page_number" in page, f"Page {i} missing 'page_number'"
        assert "text" in page, f"Page {i} missing 'text'"
        assert "images" in page, f"Page {i} missing 'images'"

        assert isinstance(page["page_number"], int), f"Page {i} 'page_number' must be int"
        assert isinstance(page["text"], str), f"Page {i} 'text' must be str"
        assert isinstance(page["images"], list), f"Page {i} 'images' must be list"

        for j, img in enumerate(page["images"]):
            assert isinstance(img, dict), f"Page {i}, image {j} must be a dict"
            assert "filename" in img, f"Page {i}, image {j} missing 'filename'"
            assert "caption" in img, f"Page {i}, image {j} missing 'caption'"
            assert "position" in img, f"Page {i}, image {j} missing 'position'"
            assert isinstance(img["filename"], str)
            assert isinstance(img["caption"], str)
            assert isinstance(img["position"], str)


def validate_page_numbers_sequential(manifest: dict) -> None:
    """Assert page numbers are sequential starting from 1."""
    page_numbers = [p["page_number"] for p in manifest["pages"]]
    assert page_numbers == list(range(1, len(page_numbers) + 1)), (
        f"Page numbers must be sequential from 1, got {page_numbers}"
    )


# ── ExtractionResult.to_manifest() tests ────────────────────────────


class TestExtractionResultManifest:
    """Tests for ExtractionResult.to_manifest() structure."""

    def test_empty_extraction_produces_valid_manifest(self):
        result = ExtractionResult(pages=[], metadata={"source_type": "pdf"})
        manifest = result.to_manifest()
        validate_manifest(manifest)
        assert manifest["pages"] == []

    def test_single_page_manifest(self):
        result = ExtractionResult(
            pages=[PageContent(page_number=1, text="Hello world", images=[])],
            metadata={"source_type": "pdf", "extractor_version": "1.0"},
        )
        manifest = result.to_manifest()
        validate_manifest(manifest)
        assert len(manifest["pages"]) == 1
        assert manifest["pages"][0]["text"] == "Hello world"

    def test_multi_page_manifest_sequential(self):
        pages = [
            PageContent(page_number=i, text=f"Page {i} content", images=[])
            for i in range(1, 6)
        ]
        result = ExtractionResult(pages=pages, metadata={"source_type": "pdf"})
        manifest = result.to_manifest()
        validate_manifest(manifest)
        validate_page_numbers_sequential(manifest)
        assert len(manifest["pages"]) == 5

    def test_manifest_with_images(self):
        result = ExtractionResult(
            pages=[
                PageContent(
                    page_number=1,
                    text="Page with images",
                    images=[
                        ImageInfo(filename="page1_img1.png", caption="Diagram", position="page_1"),
                        ImageInfo(filename="page1_img2.png", caption="", position="page_1"),
                    ],
                ),
            ],
            metadata={"source_type": "pdf"},
        )
        manifest = result.to_manifest()
        validate_manifest(manifest)
        assert len(manifest["pages"][0]["images"]) == 2
        assert manifest["pages"][0]["images"][0]["filename"] == "page1_img1.png"
        assert manifest["pages"][0]["images"][0]["caption"] == "Diagram"

    def test_metadata_preserved(self):
        result = ExtractionResult(
            pages=[PageContent(page_number=1, text="Test", images=[])],
            metadata={
                "source_type": "docx",
                "extractor_version": "1.0",
                "author": "Test Author",
            },
        )
        manifest = result.to_manifest()
        assert manifest["metadata"]["source_type"] == "docx"
        assert manifest["metadata"]["extractor_version"] == "1.0"
        assert manifest["metadata"]["author"] == "Test Author"


# ── Sample manifest fixture validation ───────────────────────────────


class TestSampleManifestStructure:
    """Validate the sample_manifest fixture itself."""

    def test_sample_manifest_valid(self, sample_manifest):
        validate_manifest(sample_manifest)

    def test_sample_manifest_sequential_pages(self, sample_manifest):
        validate_page_numbers_sequential(sample_manifest)

    def test_sample_manifest_has_images(self, sample_manifest):
        total_images = sum(len(p["images"]) for p in sample_manifest["pages"])
        assert total_images > 0, "Sample manifest should contain images"


# ── Real extractor output tests ──────────────────────────────────────


class TestPdfExtractorManifest:
    """Validate manifest structure from the PDF extractor."""

    def test_pdf_extraction_manifest(self, simple_pdf):
        from app.extractors.pdf import PdfExtractor

        output_dir = simple_pdf.parent / "output"
        output_dir.mkdir()
        result = PdfExtractor().extract(simple_pdf, output_dir)
        manifest = result.to_manifest()
        validate_manifest(manifest)
        validate_page_numbers_sequential(manifest)
        assert len(manifest["pages"]) == 2

    def test_pdf_manifest_has_text(self, simple_pdf):
        from app.extractors.pdf import PdfExtractor

        output_dir = simple_pdf.parent / "output"
        output_dir.mkdir()
        result = PdfExtractor().extract(simple_pdf, output_dir)
        manifest = result.to_manifest()
        assert any(p["text"].strip() for p in manifest["pages"]), "PDF pages should have text"

    def test_pdf_metadata_source_type(self, simple_pdf):
        from app.extractors.pdf import PdfExtractor

        output_dir = simple_pdf.parent / "output"
        output_dir.mkdir()
        result = PdfExtractor().extract(simple_pdf, output_dir)
        manifest = result.to_manifest()
        assert manifest["metadata"].get("source_type") == "pdf"


class TestDocxExtractorManifest:
    """Validate manifest structure from the DOCX extractor."""

    def test_docx_extraction_manifest(self, simple_docx):
        from app.extractors.docx import DocxExtractor

        output_dir = simple_docx.parent / "output"
        output_dir.mkdir()
        result = DocxExtractor().extract(simple_docx, output_dir)
        manifest = result.to_manifest()
        validate_manifest(manifest)
        assert len(manifest["pages"]) >= 1

    def test_docx_manifest_has_text(self, simple_docx):
        from app.extractors.docx import DocxExtractor

        output_dir = simple_docx.parent / "output"
        output_dir.mkdir()
        result = DocxExtractor().extract(simple_docx, output_dir)
        manifest = result.to_manifest()
        full_text = " ".join(p["text"] for p in manifest["pages"])
        assert "Network Security" in full_text or "CSIT302" in full_text

    def test_docx_metadata_source_type(self, simple_docx):
        from app.extractors.docx import DocxExtractor

        output_dir = simple_docx.parent / "output"
        output_dir.mkdir()
        result = DocxExtractor().extract(simple_docx, output_dir)
        manifest = result.to_manifest()
        assert manifest["metadata"].get("source_type") == "docx"


class TestPptxExtractorManifest:
    """Validate manifest structure from the PPTX extractor."""

    def test_pptx_extraction_manifest(self, simple_pptx):
        from app.extractors.pptx import PptxExtractor

        output_dir = simple_pptx.parent / "output"
        output_dir.mkdir()
        result = PptxExtractor().extract(simple_pptx, output_dir)
        manifest = result.to_manifest()
        validate_manifest(manifest)
        validate_page_numbers_sequential(manifest)
        assert len(manifest["pages"]) == 3  # 3 slides

    def test_pptx_manifest_has_text(self, simple_pptx):
        from app.extractors.pptx import PptxExtractor

        output_dir = simple_pptx.parent / "output"
        output_dir.mkdir()
        result = PptxExtractor().extract(simple_pptx, output_dir)
        manifest = result.to_manifest()
        full_text = " ".join(p["text"] for p in manifest["pages"])
        assert "Firewalls" in full_text

    def test_pptx_metadata_source_type(self, simple_pptx):
        from app.extractors.pptx import PptxExtractor

        output_dir = simple_pptx.parent / "output"
        output_dir.mkdir()
        result = PptxExtractor().extract(simple_pptx, output_dir)
        manifest = result.to_manifest()
        assert manifest["metadata"].get("source_type") == "pptx"

    def test_pptx_speaker_notes_in_text(self, simple_pptx):
        from app.extractors.pptx import PptxExtractor

        output_dir = simple_pptx.parent / "output"
        output_dir.mkdir()
        result = PptxExtractor().extract(simple_pptx, output_dir)
        manifest = result.to_manifest()
        # Slide 3 has speaker notes about IDS vs IPS
        full_text = " ".join(p["text"] for p in manifest["pages"])
        assert "IDS" in full_text
