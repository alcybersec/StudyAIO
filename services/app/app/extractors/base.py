"""Base extractor interface and common data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImageInfo:
    """Metadata for an extracted image."""

    filename: str
    caption: str = ""
    position: str = ""


@dataclass
class PageContent:
    """Extracted content from a single page or slide."""

    page_number: int
    text: str
    images: list[ImageInfo] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Complete extraction result from a file."""

    pages: list[PageContent]
    metadata: dict[str, str]
    image_count: int = 0
    page_count: int = 0

    def to_manifest(self) -> dict:
        """Convert to the manifest JSON structure defined in the PRD."""
        return {
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                    "images": [
                        {
                            "filename": img.filename,
                            "caption": img.caption,
                            "position": img.position,
                        }
                        for img in page.images
                    ],
                }
                for page in self.pages
            ],
            "metadata": self.metadata,
        }


class BaseExtractor(ABC):
    """Abstract base class for file content extractors."""

    @abstractmethod
    def extract(self, file_path: Path, output_dir: Path) -> ExtractionResult:
        """Extract text and images from a file.

        Args:
            file_path: Path to the source file.
            output_dir: Directory to save extracted images.

        Returns:
            ExtractionResult with per-page text and image references.
        """
        ...
