"""Tests for the OOXML decompression bound (#59).

Every archive here is built inside `tmp_path` at test time and is a few
kilobytes on disk — nothing resembling a zip bomb is committed to the repo. The
expansions are deliberately small (8-16 MB) and the limit is patched down to
match, so an assertion that fails still cannot cost the test run any real memory.
"""

import struct
import tracemalloc
import zipfile
import zlib
from pathlib import Path

import pytest

from app.core.exceptions import ExtractionError
from app.extractors.archive import check_archive_bounds
from app.extractors.docx import DocxExtractor
from app.extractors.pptx import PptxExtractor

MIB = 1024 * 1024


def _zeros_archive(path: Path, *, member: str, mib: int) -> bytes:
    """Write a deflate archive holding `mib` MB of zeros. Returns the payload."""
    payload = b"\0" * (mib * MIB)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, payload)
    return payload


def _understate_size(path: Path, *, payload: bytes, declared: int) -> None:
    """Rewrite the archive's declared size and CRC to describe only a prefix.

    This is the lie a real attacker tells: the local header and the central
    directory both claim a harmless `file_size`, with a CRC over just that many
    bytes so the claim is self-consistent and survives zipfile's own checking.
    The fields are patched at their fixed offsets — APPNOTE 4.3.7 and 4.3.12,
    single-member archive — rather than by searching for the old values, which
    are only four bytes and do occur elsewhere in the file.
    """
    raw = bytearray(path.read_bytes())
    lie_crc = zlib.crc32(payload[:declared]) & 0xFFFFFFFF
    assert raw[:4] == b"PK\x03\x04", "expected the member's local header first"
    struct.pack_into("<I", raw, 14, lie_crc)  # local header: crc-32
    struct.pack_into("<I", raw, 22, declared)  # local header: uncompressed size
    central = raw.rindex(b"PK\x01\x02")
    struct.pack_into("<I", raw, central + 16, lie_crc)  # directory: crc-32
    struct.pack_into("<I", raw, central + 24, declared)  # directory: uncompressed size
    path.write_bytes(bytes(raw))

    with zipfile.ZipFile(path) as archive:
        (entry,) = archive.infolist()
        assert (entry.file_size, entry.CRC) == (declared, lie_crc), "the lie did not take"


class TestDecompressedSizeBound:
    """The bound on what an archive is allowed to expand to."""

    def test_honest_declaration_over_the_limit_is_rejected(self, tmp_path, monkeypatch):
        """An archive whose own central directory declares more than the limit is
        refused without decompressing anything."""
        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 1)
        bomb = tmp_path / "bomb.pptx"
        _zeros_archive(bomb, member="ppt/slides/slide1.xml", mib=8)
        assert bomb.stat().st_size < 64 * 1024  # a few KB on disk

        with pytest.raises(ExtractionError) as excinfo:
            check_archive_bounds(bomb, kind="PPTX")

        message = str(excinfo.value)
        assert "declares 8 MB decompressed" in message
        assert "limit of 1 MB" in message
        assert "MAX_ARCHIVE_DECOMPRESSED_MB" in message

    def test_understated_declaration_is_rejected_on_the_bytes_read(self, tmp_path, monkeypatch):
        """A declared size can lie, so the bound also counts real output.

        `ZipFile.read()` — the call both python-docx and python-pptx make —
        inflates the whole member regardless of the declared size, so trusting
        that field alone would let this archive through.
        """
        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 1)
        bomb = tmp_path / "liar.pptx"
        payload = _zeros_archive(bomb, member="ppt/slides/slide1.xml", mib=8)
        _understate_size(bomb, payload=payload, declared=100)

        # The cheap pre-check is satisfied: the archive claims 100 bytes.
        with zipfile.ZipFile(bomb) as archive:
            assert sum(e.file_size for e in archive.infolist()) == 100

        with pytest.raises(ExtractionError) as excinfo:
            check_archive_bounds(bomb, kind="PPTX")

        message = str(excinfo.value)
        assert "expands to 1 MB decompressed" in message
        assert "MAX_ARCHIVE_DECOMPRESSED_MB" in message

    def test_rejecting_a_liar_does_not_allocate_what_it_asked_for(self, tmp_path, monkeypatch):
        """Catching the lie must not cost the memory the lie was requesting.

        The measuring pass reads in fixed chunks precisely so that finding the
        bound exceeded stays cheap; a naive `read()` here would allocate all
        16 MB before returning the 100 bytes it was told to expect.
        """
        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 1)
        bomb = tmp_path / "liar.docx"
        payload = _zeros_archive(bomb, member="word/document.xml", mib=16)
        _understate_size(bomb, payload=payload, declared=100)
        del payload

        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            with pytest.raises(ExtractionError):
                check_archive_bounds(bomb, kind="DOCX")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            if not was_tracing:
                tracemalloc.stop()

        # 16 MB of expansion, refused inside 4 MB of allocation.
        assert peak < 4 * MIB, f"measuring pass peaked at {peak} bytes"

    def test_archive_under_the_limit_passes(self, tmp_path, monkeypatch):
        """The bound is a ceiling, not a tax: an archive below it is accepted."""
        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 8)
        ok = tmp_path / "fine.docx"
        _zeros_archive(ok, member="word/document.xml", mib=1)

        check_archive_bounds(ok, kind="DOCX")  # no raise


class TestEntryCountBound:
    """The other shape of the same attack: many members, none of them large."""

    def test_too_many_entries_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.max_archive_entries", 50)
        many = tmp_path / "many.pptx"
        with zipfile.ZipFile(many, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(51):
                zf.writestr(f"ppt/slides/slide{i}.xml", b"<p/>")

        with pytest.raises(ExtractionError) as excinfo:
            check_archive_bounds(many, kind="PPTX")

        message = str(excinfo.value)
        assert "51 archive entries" in message
        assert "limit of 50" in message
        assert "MAX_ARCHIVE_ENTRIES" in message

    def test_entry_count_at_the_limit_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.max_archive_entries", 50)
        many = tmp_path / "many.pptx"
        with zipfile.ZipFile(many, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(50):
                zf.writestr(f"ppt/slides/slide{i}.xml", b"<p/>")

        check_archive_bounds(many, kind="PPTX")  # no raise


class TestUnreadableArchive:
    """A ZIP that is not a ZIP past its first four bytes."""

    def test_truncated_archive_fails_as_an_extraction_error(self, tmp_path):
        """The upload-time magic-byte check passes on these four bytes alone, so
        the guard is the first code to actually parse the archive."""
        bad = tmp_path / "bad.pptx"
        bad.write_bytes(b"PK\x03\x04truncated here")

        with pytest.raises(ExtractionError, match="Failed to open PPTX"):
            check_archive_bounds(bad, kind="PPTX")


class TestEveryPathThatOpensTheArchive:
    """Both stages that open a DOCX/PPTX have to be behind the bound.

    `classify` runs before `extract` in the chain the orchestrator builds, and it
    opens the archive itself for a text preview. A bound only in the extractors
    would therefore never be reached: the bomb would go off one stage earlier.
    """

    def test_extractors_refuse_the_bomb(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 1)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        pptx_bomb = tmp_path / "bomb.pptx"
        _zeros_archive(pptx_bomb, member="ppt/slides/slide1.xml", mib=8)
        with pytest.raises(ExtractionError, match="MAX_ARCHIVE_DECOMPRESSED_MB"):
            PptxExtractor().extract(pptx_bomb, output_dir)

        docx_bomb = tmp_path / "bomb.docx"
        _zeros_archive(docx_bomb, member="word/document.xml", mib=8)
        with pytest.raises(ExtractionError, match="MAX_ARCHIVE_DECOMPRESSED_MB"):
            DocxExtractor().extract(docx_bomb, output_dir)

    def test_classify_preview_does_not_inflate_a_pptx(self, tmp_path, monkeypatch):
        """The preview stops at the bound instead of expanding the archive.

        `_extract_text_preview` swallows its own failures by design — a preview is
        best-effort and classification carries on from the filename — so an empty
        return proves nothing on its own. What is asserted is the memory: with the
        guard removed, `Presentation()` reads every member of this archive into a
        dict and peaks past its full 16 MB, declared size or no declared size.
        """
        from app.core.storage import LocalStorageBackend
        from app.pipeline.classify import _extract_text_preview

        monkeypatch.setattr("app.config.settings.max_archive_decompressed_mb", 1)
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        bomb = uploads / "bomb.pptx"
        payload = _zeros_archive(bomb, member="ppt/slides/slide1.xml", mib=16)
        _understate_size(bomb, payload=payload, declared=100)
        del payload
        monkeypatch.setattr(
            "app.pipeline.classify.get_storage",
            lambda: LocalStorageBackend(base_dir=str(tmp_path)),
        )

        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            preview = _extract_text_preview("uploads/bomb.pptx", "pptx")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            if not was_tracing:
                tracemalloc.stop()

        assert preview == ""
        assert peak < 4 * MIB, f"classify preview peaked at {peak} bytes"

    def test_classify_preview_checks_the_docx_bound(self, tmp_path, monkeypatch):
        """The DOCX branch is guarded too.

        python-docx reads the parts its relationship graph reaches rather than
        every member, so a bare one-member archive would fail it early for
        unrelated reasons and prove nothing about memory. The assertion is
        therefore that the branch consults the bound at all, before it opens
        anything — the guard itself is covered behaviourally above.
        """
        from app.core.storage import LocalStorageBackend
        from app.pipeline.classify import _extract_text_preview

        seen: list[tuple[Path, str]] = []

        def _spy(file_path, *, kind):
            seen.append((file_path, kind))
            raise ExtractionError("bound exceeded")

        monkeypatch.setattr("app.pipeline.classify.check_archive_bounds", _spy)
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        _zeros_archive(uploads / "lecture.docx", member="word/document.xml", mib=1)
        monkeypatch.setattr(
            "app.pipeline.classify.get_storage",
            lambda: LocalStorageBackend(base_dir=str(tmp_path)),
        )

        assert _extract_text_preview("uploads/lecture.docx", "docx") == ""
        assert seen == [(uploads / "lecture.docx", "DOCX")]


class TestRealDocumentsStillExtract:
    """The bound must be invisible to real lecture material."""

    def test_pptx_extracts_under_the_default_bounds(self, simple_pptx, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = PptxExtractor().extract(simple_pptx, output_dir)

        assert result.page_count == 3
        assert "CSIT302" in result.pages[0].text

    def test_docx_extracts_under_the_default_bounds(self, simple_docx, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = DocxExtractor().extract(simple_docx, output_dir)

        all_text = " ".join(p.text for p in result.pages)
        assert "CSIT302" in all_text

    @pytest.mark.parametrize("fixture", ["simple_pptx", "simple_docx"])
    def test_real_documents_sit_far_below_the_defaults(self, fixture, request):
        """Headroom check, so a future tightening of the defaults has to notice.

        A python-pptx/python-docx document is the small end of real material, but
        it is the only real sample in the unit suite; the assertion is only that
        the defaults are orders of magnitude away, not that they are calibrated.
        """
        from app.config import settings

        path = request.getfixturevalue(fixture)
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()

        assert len(entries) * 100 < settings.max_archive_entries
        assert sum(e.file_size for e in entries) * 100 < (
            settings.max_archive_decompressed_mb * MIB
        )
