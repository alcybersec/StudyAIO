"""DOCX extractor using python-docx."""

from pathlib import Path

import docx
import structlog

from app.core.exceptions import ExtractionError
from app.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    ImageInfo,
    PageContent,
)

logger = structlog.get_logger()

# DOCX doesn't have native page breaks that are easy to detect.
# We treat the whole document as page 1 unless we find page-break markers,
# or we chunk by headings.
_HEADING_STYLES = {"Heading 1", "Heading 2", "Heading1", "Heading2"}


class DocxExtractor(BaseExtractor):
    """Extracts text and images from DOCX files using python-docx."""

    def extract(self, file_path: Path, output_dir: Path) -> ExtractionResult:
        """Extract text and images from a DOCX file.

        Sections are split by headings (Heading 1/2). Each section maps to
        a logical "page" in the extraction result.

        Args:
            file_path: Path to the DOCX file.
            output_dir: Directory to save extracted images.

        Returns:
            ExtractionResult with per-section content.

        Raises:
            ExtractionError: If the DOCX cannot be opened or parsed.
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        try:
            document = docx.Document(str(file_path))
        except Exception as e:
            raise ExtractionError(f"Failed to open DOCX {file_path.name}: {e}") from e

        # Extract images from the document's relationships
        total_images = 0
        image_filenames: list[str] = []
        for rel in document.part.rels.values():
            if "image" in rel.reltype:
                try:
                    image_data = rel.target_part.blob
                    content_type = rel.target_part.content_type
                    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
                    total_images += 1
                    filename = f"img{total_images}.{ext}"
                    image_path = images_dir / filename
                    image_path.write_bytes(image_data)
                    image_filenames.append(filename)
                except Exception:
                    logger.warning("docx_image_extraction_failed", rel_type=rel.reltype)

        # Split document into sections by headings
        sections: list[tuple[str, list[str]]] = []
        current_texts: list[str] = []

        for para in document.paragraphs:
            if para.style and para.style.name in _HEADING_STYLES and current_texts:
                sections.append(("", current_texts))
                current_texts = []
            current_texts.append(para.text)

        if current_texts:
            sections.append(("", current_texts))

        # If no sections were created, put everything on page 1
        if not sections:
            sections = [("", [""])]

        pages: list[PageContent] = []
        for idx, (_, texts) in enumerate(sections):
            page_number = idx + 1
            # Attach images to the first page
            page_images = []
            if page_number == 1:
                page_images = [
                    ImageInfo(filename=fn, position="embedded") for fn in image_filenames
                ]

            pages.append(
                PageContent(
                    page_number=page_number,
                    text="\n".join(texts),
                    images=page_images,
                )
            )

        logger.info(
            "docx_extraction_complete",
            file=file_path.name,
            sections=len(pages),
            images=total_images,
        )

        return ExtractionResult(
            pages=pages,
            metadata={"extractor_version": "1.0", "source_type": "docx"},
            image_count=total_images,
            page_count=len(pages),
        )
