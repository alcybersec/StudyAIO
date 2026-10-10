"""Tests for the plain-text extractor (quick capture, R-016)."""

import pytest

from app.core.exceptions import ExtractionError
from app.extractors import get_extractor
from app.extractors.txt import TxtExtractor


class TestTxtExtractor:
    def test_registered_for_txt(self):
        assert isinstance(get_extractor("txt"), TxtExtractor)

    def test_extracts_single_page_manifest(self, tmp_path):
        src = tmp_path / "note.txt"
        src.write_text("Packets are routed hop by hop.\nSecond line.", encoding="utf-8")
        result = TxtExtractor().extract(src, tmp_path / "out")
        assert result.page_count == 1
        assert result.image_count == 0
        assert result.pages[0].page_number == 1
        assert "hop by hop" in result.pages[0].text
        manifest = result.to_manifest()
        assert manifest["pages"][0]["images"] == []

    def test_undecodable_bytes_do_not_fail(self, tmp_path):
        src = tmp_path / "bad.txt"
        src.write_bytes(b"ok \xff\xfe text")
        result = TxtExtractor().extract(src, tmp_path / "out")
        assert "ok" in result.pages[0].text

    def test_empty_file_raises_extraction_error(self, tmp_path):
        src = tmp_path / "empty.txt"
        src.write_text("   \n")
        with pytest.raises(ExtractionError):
            TxtExtractor().extract(src, tmp_path / "out")

    def test_missing_file_raises_extraction_error(self, tmp_path):
        with pytest.raises(ExtractionError):
            TxtExtractor().extract(tmp_path / "nope.txt", tmp_path / "out")
