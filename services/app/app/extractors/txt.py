"""Plain-text extractor — quick-capture notes and pasted text (R-016)."""

from pathlib import Path

from app.core.exceptions import ExtractionError
from app.extractors.base import BaseExtractor, ExtractionResult, PageContent


class TxtExtractor(BaseExtractor):
    """Reads a UTF-8 text file as a single page with no images."""

    def extract(self, file_path: Path, output_dir: Path) -> ExtractionResult:
        """Extract the text of a plain-text file.

        Args:
            file_path: Path to the text file (never modified).
            output_dir: Created for consistency; text has no images.

        Returns:
            ExtractionResult with one page.

        Raises:
            ExtractionError: If the file cannot be read or holds no text.
        """
        try:
            raw = file_path.read_bytes()
        except OSError as e:
            raise ExtractionError(f"Failed to open text file {file_path.name}: {e}") from e

        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            raise ExtractionError(f"Text file {file_path.name} is empty")

        output_dir.mkdir(parents=True, exist_ok=True)
        return ExtractionResult(
            pages=[PageContent(page_number=1, text=text)],
            metadata={"source": "text"},
            image_count=0,
            page_count=1,
        )
