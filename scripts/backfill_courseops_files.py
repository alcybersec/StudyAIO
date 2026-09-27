#!/usr/bin/env python3
"""Give every course document its own per-user blob (issue #107).

Course document keys used to be `courseops/<sha256[:16]>_<name>` —
content-addressed with no owner — so two users who uploaded the same handbook
shared one blob. Nothing was corrupted (the same key means the same bytes), but
`account_service.purge_user_storage` could not delete it: removing one user's
copy would pull the file out from under another user's live `CourseDocument`
row. Closing an account therefore left its course documents on disk forever.
The keys are now `courseops/<user_id>/<sha256[:16]>_<name>`.

Alembic revision `4f1c7a2e9b63` rewrites the `file_path` column. This script
does the storage half, which a migration cannot: it runs where the blobs are.

What it does, per legacy `course_documents` row:

    1. **copies** the blob to `courseops/<user_id>/<same basename>`. Copy, not
       move: several users may reference one legacy blob and each needs their
       own. Safe for the same reason the bug was benign — the key is
       content-addressed, so every referrer wants those identical bytes. (The
       #92 backfill had to do the opposite: there one file held a single user's
       content under two rows' key, so copying would have been the disclosure.)
    2. points `file_path` at the new key.
    3. deletes the legacy blob, once no row references it any more.

A legacy blob that is already gone is not an error — the row is re-keyed
regardless, so it agrees with the migration either way — but it is counted
separately so a surprising number is visible rather than silent.

It only ever reads and writes keys it derives from a row, and only ever deletes
legacy-shape keys some row actually pointed at. Nothing else under the data
directory is touched. It is idempotent — a second run finds every row already
per-user and nothing left to delete — and can be run before or after the
migration, since both derive the same key from the same columns.

Run it with the application's own environment (same `DATABASE_URL`, same
`DATA_DIR` / S3 settings), e.g. inside the app container:

    python scripts/backfill_courseops_files.py --dry-run   # report only
    python scripts/backfill_courseops_files.py

Options:
    --dry-run       Report the counts and change nothing.
    --keep-legacy   Leave the old-shape blobs on disk. They are unreachable
                    either way once every row is re-keyed: the only reader
                    resolves a document id and reads `file_path` off the row,
                    and `/api/files/courseops/<raw path>` is refused (#66).
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add services/app to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "app"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import courseops_service  # noqa: E402


async def backfill(*, dry_run: bool, delete_legacy: bool) -> dict[str, int]:
    """Run the backfill against the configured database and storage."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            counts = await courseops_service.backfill_courseops_storage_keys(
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
        help="Report what would change without copying, updating or deleting anything.",
    )
    parser.add_argument(
        "--keep-legacy",
        action="store_true",
        help="Do not delete the old-shape blobs.",
    )
    args = parser.parse_args()

    counts = asyncio.run(backfill(dry_run=args.dry_run, delete_legacy=not args.keep_legacy))

    prefix = "would copy" if args.dry_run else "copied"
    print(
        f"{counts['rows']} course documents: {prefix} {counts['blobs_copied']} blobs, "
        f"{counts['paths_updated']} file_path values re-keyed, "
        f"{counts['legacy_deleted']} legacy blobs "
        f"{'would be deleted' if args.dry_run else 'deleted'}."
    )
    if counts["legacy_missing"]:
        print(
            f"{counts['legacy_missing']} rows pointed at a legacy blob that was already "
            "missing; they were re-keyed anyway."
        )
    if args.dry_run:
        print("Dry run: nothing was copied, updated or deleted.")


if __name__ == "__main__":
    main()
