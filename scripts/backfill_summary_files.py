#!/usr/bin/env python3
"""Move summary markdown files onto the per-course storage key (issue #92).

Summary keys used to be `summaries/<CODE>/<CODE>_Week<N>.md`. Course codes are
unique only per user, so two users who both take `CSIT302` shared one key and
one file: the second pipeline run overwrote the first user's summary, and both
`summaries` rows pointed at the survivor. The keys are now
`summaries/<course_id>/Week<N>.md`.

Alembic revision `d0e1f2g3h4i5` rewrites the `file_path` column. This script
does the storage half, which a migration cannot: it runs where the blobs are.

What it does, per `summaries` row:

    1. writes `summaries/<course_id>/Week<N>.md` **from `content_md`**, not by
       moving the old file. Where two users collided, the old file holds one
       user's text under both rows' path, so moving it would hand somebody
       else's summary to one of them. The column is per-user and correct.
    2. points `file_path` at the new key.
    3. deletes the old-shape file, once every row has been written.

It only ever writes keys it derives from a row, and only ever deletes
old-shape keys some row actually pointed at. Nothing else under the data
directory is read or touched. It is idempotent -- a second run rewrites the
same bytes and finds nothing left to delete -- and can be run before or after
the migration, since both derive the same key from the same column.

Run it with the application's own environment (same `DATABASE_URL`, same
`DATA_DIR` / S3 settings), e.g. inside the app container:

    python scripts/backfill_summary_files.py --dry-run   # report only
    python scripts/backfill_summary_files.py

Options:
    --dry-run       Report the counts and change nothing.
    --keep-legacy   Leave the old-shape files on disk. They are unreachable
                    either way: `/api/files/summaries/<CODE>/...` no longer
                    resolves to a course, so it 404s.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add services/app to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import summary_service  # noqa: E402


async def backfill(*, dry_run: bool, delete_legacy: bool) -> dict[str, int]:
    """Run the backfill against the configured database and storage."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            counts = await summary_service.backfill_summary_storage_keys(
                session,
                delete_legacy=delete_legacy,
                dry_run=dry_run,
            )
            if dry_run:
                await session.rollback()
            else:
                await session.commit()
    finally:
        await engine.dispose()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing, updating or deleting anything.",
    )
    parser.add_argument(
        "--keep-legacy",
        action="store_true",
        help="Do not delete the old-shape summary files.",
    )
    args = parser.parse_args()

    counts = asyncio.run(backfill(dry_run=args.dry_run, delete_legacy=not args.keep_legacy))

    prefix = "would write" if args.dry_run else "wrote"
    print(
        f"{counts['rows']} summaries: {prefix} {counts['files_written']} files, "
        f"{counts['paths_updated']} file_path values re-keyed, "
        f"{counts['legacy_deleted']} legacy files "
        f"{'would be deleted' if args.dry_run else 'deleted'}."
    )
    if args.dry_run:
        print("Dry run: nothing was written, updated or deleted.")


if __name__ == "__main__":
    main()
