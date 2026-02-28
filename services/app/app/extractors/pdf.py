"""PDF extractor using PyMuPDF (fitz)."""

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


class PdfExtractor(BaseExtractor):
    """Extracts text and images from PDF files using PyMuPDF."""

    def extract(self, file_path: Path, output_dir: Path) -> ExtractionResult:
        """Extract text and images from a PDF file.

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
                        filename = f"page{page_number}_img{img_idx + 1}.{image_ext}"
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
        )

        return ExtractionResult(
            pages=pages,
            metadata={"extractor_version": "1.0", "source_type": "pdf"},
            image_count=total_images,
            page_count=len(pages),
        )
