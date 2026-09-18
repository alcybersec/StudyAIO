"""Bounding what an OOXML archive is allowed to expand to (#59).

`.docx` and `.pptx` are ZIP archives. `MAX_UPLOAD_SIZE_MB` caps the *compressed*
bytes a user may upload, and #48's magic-byte check makes sure the bytes really
are a ZIP — but neither says anything about what that ZIP expands to. Deflate
tops out around 1032:1, so a 50 MB upload that passes both checks can still ask
the worker for tens of gigabytes of memory.

**Why the bound sits before the parser rather than inside it.** Neither library
lets us hand it a `ZipFile` to inspect, and both read the whole archive eagerly
before returning anything:

- `python-pptx` (`pptx/opc/serialized.py::_ZipPkgReader._blobs`) builds
  `{name: z.read(name) for name in z.namelist()}` — every member, decompressed,
  in one dict.
- `python-docx` (`docx/opc/pkgreader.py::_load_serialized_parts`) walks the
  relationship graph and calls `ZipFile.read()` on each part it reaches.

Both take a path or a stream and construct the `ZipFile` themselves, so there is
no hook between "open" and "all of it is in memory". The only place a bound can
sit is *before* `Document()` / `Presentation()` is called.

**Why the declared size is not sufficient on its own.** `ZipInfo.file_size` is a
free pre-check, and it rejects any bomb whose central directory is honest. But
an attacker writes that field, so it can understate reality, and it is tempting
to assume CPython then clips the read. It clips the bytes *returned* and trips
its CRC check, which looks like safety; it is not. `ZipFile.read(name)` calls
`ZipExtFile.read(-1)`, which hands the decompressor `MAX_N` (2 GB) as
`max_length`, so zlib inflates the whole member before anything is truncated.
Measured on CPython 3.12 against a 200 MB-of-zeros member whose declared size
*and* CRC were rewritten to describe only its first 100 bytes:

    declared file_size: 100  compress_size: 203842
    read() returned: 100 bytes; tracemalloc peak during read: 458834317 bytes

100 bytes out, 458 MB allocated — and that is precisely the call python-docx and
python-pptx make. So the second pass below counts the bytes that actually come
out. Two details make it measure reality rather than the claim:

1. It reads in fixed chunks, so each `decompress()` call gets a small
   `max_length` — the bound `read(-1)` throws away.
2. It reads through a copy of the `ZipInfo` whose `file_size` is raised one read
   past the remaining allowance, because `ZipExtFile` initialises `self._left`
   from that field and would otherwise stop at the understated value and report
   the lie straight back to us. A member still producing bytes once the
   allowance is gone is rejected on the running total; should it stop there
   instead, with contents its declared CRC does not match, `BadZipFile` is
   raised, which is also a rejection. Honest archives are unaffected by the
   raised value: their stream ends where the decompressor says it does, and
   their CRC still matches.

The cost is one extra decompression pass per archive, bounded by the limit, on
top of the parser's own. For a real lecture deck that is a few milliseconds
against an AI pipeline measured in seconds.

The entry-count bound covers the other shape of the same attack: tens of
thousands of members, none individually large, where the cost is per-member
overhead in the readers above.
"""

import copy
import zipfile
from pathlib import Path

import structlog

from app.config import settings
from app.core.exceptions import ExtractionError

logger = structlog.get_logger()

# Read granularity for the measuring pass. Small enough that one
# `decompress(data, max_length)` call cannot materialise a bomb, large enough
# that walking a legitimate 100 MB document is not syscall-bound.
_CHUNK_BYTES = 256 * 1024


def check_archive_bounds(file_path: Path, *, kind: str) -> None:
    """Refuse an OOXML archive that expands past the configured bounds.

    Args:
        file_path: Path to the `.docx`/`.pptx` file, unopened.
        kind: Label used in error messages, e.g. ``"DOCX"``.

    Raises:
        ExtractionError: If the archive cannot be read, holds more than
            ``MAX_ARCHIVE_ENTRIES`` members, or expands — by its own declaration
            or in fact — past ``MAX_ARCHIVE_DECOMPRESSED_MB``.
    """
    max_entries = settings.max_archive_entries
    max_bytes = settings.max_archive_decompressed_mb * 1024 * 1024

    try:
        with zipfile.ZipFile(file_path) as archive:
            entries = archive.infolist()

            if len(entries) > max_entries:
                raise ExtractionError(
                    f"{kind} {file_path.name} contains {len(entries)} archive entries, "
                    f"over the limit of {max_entries} (MAX_ARCHIVE_ENTRIES). "
                    f"Refusing to extract it."
                )

            declared = sum(entry.file_size for entry in entries)
            if declared > max_bytes:
                raise _too_large(kind, file_path, declared, max_bytes, "declares")

            measured = _measure_decompressed(archive, entries, max_bytes)
            if measured > max_bytes:
                raise _too_large(kind, file_path, measured, max_bytes, "expands to")

    except (zipfile.BadZipFile, NotImplementedError, OSError) as e:
        # The upload-time magic-byte check only looks at the first four bytes, so
        # a truncated, corrupt or exotically compressed archive still reaches
        # here — as does a member whose contents disagree with its declared CRC,
        # which is how an understated `file_size` surfaces once the measuring
        # pass reads past it. All of them are extraction failures, and the
        # message is the same one the parsers themselves used to produce.
        raise ExtractionError(f"Failed to open {kind} {file_path.name}: {e}") from e

    logger.debug(
        "archive_bounds_ok",
        file=file_path.name,
        entries=len(entries),
        decompressed_bytes=measured,
    )


def _measure_decompressed(
    archive: zipfile.ZipFile, entries: list[zipfile.ZipInfo], max_bytes: int
) -> int:
    """Total the bytes the archive really produces, stopping once over `max_bytes`.

    Returns the running total: the true expansion when it came in under the
    limit, and the first over-limit reading otherwise — the caller only needs to
    know which side of the line it fell on.
    """
    total = 0
    for entry in entries:
        if entry.is_dir():
            continue
        # See the module docstring: `file_size` is what bounds `ZipExtFile`, so a
        # copy of it is raised one read past the remaining allowance. The reader
        # therefore stops either where the member genuinely ends or a chunk after
        # the allowance ran out — never where the central directory claims, and
        # the loop below crosses `max_bytes` and returns before that ceiling.
        probe = copy.copy(entry)
        probe.file_size = (max_bytes - total) + _CHUNK_BYTES + 1
        with archive.open(probe) as member:
            while True:
                chunk = member.read(_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    return total
    return total


def _too_large(kind: str, file_path: Path, size: int, max_bytes: int, verb: str) -> ExtractionError:
    return ExtractionError(
        f"{kind} {file_path.name} {verb} {size // (1024 * 1024)} MB decompressed, "
        f"over the limit of {max_bytes // (1024 * 1024)} MB "
        f"(MAX_ARCHIVE_DECOMPRESSED_MB). Refusing to extract it."
    )
