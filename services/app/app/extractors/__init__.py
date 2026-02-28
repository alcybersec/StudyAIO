"""File content extractors."""

from app.extractors.base import BaseExtractor, ExtractionResult, ImageInfo, PageContent
from app.extractors.docx import DocxExtractor
from app.extractors.pdf import PdfExtractor
from app.extractors.pptx import PptxExtractor

_EXTRACTORS: dict[str, type[BaseExtractor]] = {
    "pdf": PdfExtractor,
    "docx": DocxExtractor,
    "pptx": PptxExtractor,
}


def get_extractor(file_type: str) -> BaseExtractor:
    """Get the appropriate extractor for a file type.

    Args:
        file_type: One of "pdf", "docx", "pptx".

    Returns:
        An instantiated extractor.

    Raises:
        ValueError: If file_type is not supported.
    """
    extractor_cls = _EXTRACTORS.get(file_type.lower())
    if extractor_cls is None:
        raise ValueError(f"Unsupported file type: {file_type}. Supported: {list(_EXTRACTORS.keys())}")
    return extractor_cls()


__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "ImageInfo",
    "PageContent",
    "get_extractor",
]
