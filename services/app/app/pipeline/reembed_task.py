"""Re-chunk and re-embed existing artifacts whose chunks outgrow the embedder (GL#17).

Before GL#17 chunks were sized at ~500 estimated tokens, but all-MiniLM-L6-v2 embeds
only 256 word pieces, so the back half of every chunk was never in its vector. New
uploads are now chunked to fit; this task repairs the rows written before.

The rewrite itself is `app.pipeline.index._index(..., refresh=...)`, so the embedding
gateway call sites stay exactly the ones ADR 0005 lists. Properties of the task:

- **Per user.** Artifacts are enumerated with a `LectureArtifact.user_id == user_id`
  filter (floor 1); chunks and extractions are only reached through those ids.
- **Never leaves an artifact unsearchable (floor 4).** `_index` embeds the new chunks
  *before* deleting the old ones, and the delete + insert are one transaction committed
  per artifact. A failure rolls back to the old, still-searchable chunks.
- **Idempotent and resumable without a marker column.** An artifact is stale only if a
  stored chunk exceeds the embedder window. After the rewrite none does, so a re-run
  (or a run resumed after a crash) skips it. Chunk ids are the stable
  `<artifact>_p<page>_c<idx>` ones.
- **Batched.** Artifacts are walked in id order, `batch_size` per page, with a progress
  log line (counters) per page.

Run it with `python -m app.pipeline.reembed_task` (see `main`).
"""

import argparse
import sys
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, run_async
from app.core.exceptions import IndexingError
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.user import User
from app.pipeline.index import _index
from app.pipeline.metrics import REEMBED_ARTIFACTS
from app.worker import celery_app

logger = structlog.get_logger()

DEFAULT_BATCH_SIZE = 25

#: `_index(refresh=...)` statuses -> counter names.
_OUTCOMES = {
    "reembedded": "reembedded",
    "stale": "reembedded",  # dry run: would be re-embedded
    "skipped_fit": "skipped_fit",
    "skipped_no_text": "skipped_no_extraction",
}


async def _artifact_page(
    session: AsyncSession, user_id: str, after_id: str | None, limit: int
) -> list[str]:
    """Next page of this user's artifact ids that have chunks, in id order."""
    stmt = (
        select(LectureArtifact.id)
        .where(
            LectureArtifact.user_id == user_id,
            select(Chunk.id).where(Chunk.artifact_id == LectureArtifact.id).exists(),
        )
        .order_by(LectureArtifact.id)
        .limit(limit)
    )
    if after_id is not None:
        stmt = stmt.where(LectureArtifact.id > after_id)
    return list((await session.execute(stmt)).scalars().all())


async def _reembed_artifact(artifact_id: str, user_id: str, dry_run: bool) -> str:
    """Rewrite one artifact's chunks if stale. Returns the counter name."""
    try:
        result = await _index(artifact_id, user_id, refresh="dry_run" if dry_run else "apply")
    except IndexingError as exc:
        # No extraction to re-chunk from: the old chunks stay, which beats none.
        logger.warning(
            "reembed_artifact_skipped", user_id=user_id, artifact_id=artifact_id, reason=str(exc)
        )
        return "skipped_no_extraction"
    return _OUTCOMES[result["status"]]


async def reembed_user_chunks_async(
    user_id: str, batch_size: int = DEFAULT_BATCH_SIZE, dry_run: bool = False
) -> dict[str, Any]:
    """Re-embed one user's stale artifacts.

    Args:
        user_id: Owner whose artifacts are processed; nothing else is touched.
        batch_size: Artifacts per page and per progress log line.
        dry_run: Count stale artifacts without writing anything.

    Returns:
        Counters: scanned, reembedded, skipped_fit, skipped_no_extraction, failed.
    """
    counters: dict[str, Any] = {
        "user_id": user_id,
        "scanned": 0,
        "reembedded": 0,
        "skipped_fit": 0,
        "skipped_no_extraction": 0,
        "failed": 0,
    }
    after_id: str | None = None
    while True:
        async with async_session_factory() as session:
            ids = await _artifact_page(session, user_id, after_id, batch_size)
        if not ids:
            break
        for artifact_id in ids:
            counters["scanned"] += 1
            try:
                outcome = await _reembed_artifact(artifact_id, user_id, dry_run)
            except Exception as exc:
                outcome = "failed"
                logger.error(
                    "reembed_artifact_failed",
                    user_id=user_id,
                    artifact_id=artifact_id,
                    error=str(exc),
                )
            counters[outcome] += 1
            if not dry_run:
                REEMBED_ARTIFACTS.labels(outcome=outcome).inc()
        after_id = ids[-1]
        logger.info("reembed_progress", dry_run=dry_run, **counters)
    logger.info("reembed_user_done", dry_run=dry_run, **counters)
    return counters


async def _all_user_ids() -> list[str]:
    async with async_session_factory() as session:
        return list((await session.execute(select(User.id).order_by(User.id))).scalars().all())


@celery_app.task(name="app.pipeline.reembed_task.reembed_user_chunks")
def reembed_user_chunks(user_id: str, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    """Celery task: re-embed one user's stale chunks (idempotent, safe to re-run)."""
    return run_async(reembed_user_chunks_async(user_id, batch_size=batch_size))


@celery_app.task(name="app.pipeline.reembed_task.reembed_all_chunks")
def reembed_all_chunks(batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:
    """Celery task: enqueue one `reembed_user_chunks` per user."""
    user_ids = run_async(_all_user_ids())
    for uid in user_ids:
        reembed_user_chunks.delay(uid, batch_size)
    logger.info("reembed_enqueued", users=len(user_ids), batch_size=batch_size)
    return {"users_enqueued": len(user_ids)}


def main(argv: list[str] | None = None) -> int:
    """Operator entry point: `python -m app.pipeline.reembed_task`.

    By default enqueues the Celery work (the worker runs it). `--inline` runs in
    this process; `--dry-run` (implies inline) only reports what is stale.
    """
    parser = argparse.ArgumentParser(prog="python -m app.pipeline.reembed_task")
    parser.add_argument("--user-id", default=None, help="Only this user (default: every user)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--inline", action="store_true", help="Run here, not via the worker")
    parser.add_argument("--dry-run", action="store_true", help="Report stale artifacts only")
    args = parser.parse_args(argv)

    if args.dry_run or args.inline:

        async def _go() -> list[dict[str, Any]]:
            users = [args.user_id] if args.user_id else await _all_user_ids()
            return [
                await reembed_user_chunks_async(u, args.batch_size, dry_run=args.dry_run)
                for u in users
            ]

        for result in run_async(_go()):
            print(result)
        return 0

    if args.user_id:
        reembed_user_chunks.delay(args.user_id, args.batch_size)
        print(f"enqueued re-embed for user {args.user_id}")
    else:
        reembed_all_chunks.delay(args.batch_size)
        print("enqueued re-embed for all users")
    return 0


if __name__ == "__main__":
    sys.exit(main())
