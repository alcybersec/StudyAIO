"""PDF extractor using PyMuPDF (fitz)."""

import hashlib
from pathlib import Path

import fitz
import structlog

from app.core.exceptions import ExtractionError
from app.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    ImageInfo,
    PageContent,
)

logger = structlog.get_logger()

# Images smaller than this (bytes) AND both dimensions below _MIN_DIM
# are likely icons/logos — skip them.
_MIN_SIZE_BYTES = 5_000
_MIN_DIM = 200


class PdfExtractor(BaseExtractor):
    """Extracts text and images from PDF files using PyMuPDF."""

    def extract(self, file_path: Path, output_dir: Path) -> ExtractionResult:
        """Extract text and images from a PDF file.

        Deduplicates images by content hash and filters out small
        icons/logos that appear on many pages (e.g. university watermarks).

        Args:
            file_path: Path to the PDF file.
            output_dir: Directory to save extracted images.

        Returns:
            ExtractionResult with per-page content.

        Raises:
            ExtractionError: If the PDF cannot be opened or parsed.
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF {file_path.name}: {e}") from e

        pages: list[PageContent] = []
        total_images = 0
        seen_hashes: dict[str, str] = {}  # hash -> filename (first occurrence)
        skipped_dupes = 0
        skipped_small = 0

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_number = page_idx + 1
                text = page.get_text("text")
                page_images: list[ImageInfo] = []

                for img_idx, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)

                        # Skip tiny images (icons, bullets, logos)
                        if (
                            len(image_bytes) < _MIN_SIZE_BYTES
                            and width < _MIN_DIM
                            and height < _MIN_DIM
                        ):
                            skipped_small += 1
                            continue

                        # Deduplicate by content hash
                        img_hash = hashlib.md5(image_bytes).hexdigest()
                        if img_hash in seen_hashes:
                            skipped_dupes += 1
                            continue

                        filename = f"page{page_number}_img{img_idx + 1}.{image_ext}"
                        seen_hashes[img_hash] = filename
                        image_path = images_dir / filename
                        image_path.write_bytes(image_bytes)

                        page_images.append(
                            ImageInfo(filename=filename, position=f"page_{page_number}")
                        )
                        total_images += 1
                    except Exception:
                        logger.warning(
                            "pdf_image_extraction_failed",
                            page=page_number,
                            img_idx=img_idx,
                            xref=xref,
                        )

                pages.append(
                    PageContent(
                        page_number=page_number,
                        text=text,
                        images=page_images,
                    )
                )
        finally:
            doc.close()

        logger.info(
            "pdf_extraction_complete",
            file=file_path.name,
            pages=len(pages),
            images=total_images,
            skipped_dupes=skipped_dupes,
            skipped_small=skipped_small,
        )

        return ExtractionResult(
            pages=pages,
            metadata={"extractor_version": "1.1", "source_type": "pdf"},
            image_count=total_images,
            page_count=len(pages),
        )
