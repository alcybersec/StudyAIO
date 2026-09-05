"""Operator commands for StudyAIO.

Run inside the API container:

    docker compose exec api python -m app.cli ensure-admin --email you@example.com

`ensure-admin` is the only supported way to obtain a first admin credential.
The set-password link it prints is a bearer credential for the account, so it
goes to stdout and is never written to the structured log — the same rule
`user_service` applies to reset links in SaaS mode.
"""

import argparse
import asyncio
import sys
from urllib.parse import quote_plus

from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import settings
from app.core.database import async_session_factory, engine
from app.core.exceptions import StudyAIOError
from app.core.logging import configure_logging
from app.services import admin_service
from app.services.user_service import ACCOUNT_SETUP_TOKEN_HOURS


async def _ensure_admin(email: str, username: str | None) -> int:
    """Bootstrap an admin account and print its set-password link."""
    try:
        async with async_session_factory() as session:
            try:
                user, token = await admin_service.ensure_admin(session, email, username)
            except (StudyAIOError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            await session.commit()
    finally:
        await engine.dispose()

    base = settings.app_base_url.rstrip("/")
    print(f"admin:  {user.email}  (id {user.id}, role {user.role})")
    print(f"open:   {base}/reset-password?token={quote_plus(token)}")
    print(
        f"base:   {base} (from APP_BASE_URL) — the token is not origin-bound; "
        "if that host is unreachable from your browser, keep the ?token= and "
        "substitute the origin you use."
    )
    if base.split("://")[-1].split(":")[0].split("/")[0] in ("localhost", "127.0.0.1", "0.0.0.0"):
        print(f"warning: {base} is a local address — it will not load from another machine.")
    print()
    print(
        f"The link is single-use and expires in {ACCOUNT_SETUP_TOKEN_HOURS} hours. "
        "It is a credential — do not paste it into a shared channel or an issue tracker."
    )
    print(
        "Any link printed by an earlier run of this command is now void — use only the newest one."
    )
    return 0


async def _backfill_concept_embeddings(batch_size: int) -> int:
    """Embed concepts that have none.

    Concept embeddings were never generated before the #33 fix, so every
    concept created up to that point has a NULL embedding and is invisible to
    `GET /api/concepts/{id}/similar`. New concepts are embedded on extraction;
    this is for the ones already in the table.

    Idempotent — it only touches rows where `embedding IS NULL`, so it can be
    re-run, and a run interrupted halfway keeps the work it committed.

    Args:
        batch_size: Concepts per provider call and per commit.

    Returns:
        A process exit code.
    """
    from sqlalchemy import func, select

    from app.models.concept import Concept
    from app.services.concept_service import _embed_concepts

    async with async_session_factory() as session:
        total = await session.scalar(
            select(func.count()).select_from(Concept).where(Concept.embedding.is_(None))
        )
        if not total:
            print("No concepts are missing an embedding — nothing to do.")
            return 0

        print(f"{total} concept(s) missing an embedding. Embedding in batches of {batch_size}.")

        done = 0
        while True:
            result = await session.execute(
                select(Concept).where(Concept.embedding.is_(None)).limit(batch_size)
            )
            batch = list(result.scalars().all())
            if not batch:
                break

            _embed_concepts(batch)

            # A provider that returns nothing would loop forever on the same
            # rows, so stop rather than spin.
            if any(c.embedding is None for c in batch):
                await session.rollback()
                print(
                    "error: the embedding provider returned nothing for a batch; "
                    "stopping. Check EMBEDDING_BACKEND and EMBEDDING_DIMENSIONS.",
                    file=sys.stderr,
                )
                return 1

            await session.commit()
            done += len(batch)
            print(f"  {done}/{total}")

    print(f"Done. {done} concept(s) embedded.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    configure_logging("WARNING")

    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command")

    ensure = sub.add_parser(
        "ensure-admin",
        help="Guarantee a reachable admin account and print its set-password link",
    )
    ensure.add_argument("--email", required=True, help="Address the admin logs in with")
    ensure.add_argument(
        "--username",
        default=None,
        help="Display name, used only when no admin account exists yet",
    )

    backfill = sub.add_parser(
        "backfill-concept-embeddings",
        help="Embed concepts created before embeddings worked (issue #33)",
    )
    backfill.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Concepts per provider call and per commit (default: 128)",
    )

    args = parser.parse_args(argv)

    if args.command == "ensure-admin":
        try:
            return asyncio.run(_ensure_admin(args.email, args.username))
        except (OSError, OperationalError, InterfaceError) as exc:
            print(
                f"error: cannot reach the database ({type(exc).__name__}: {exc}) — "
                "is the db service up, and are you running this inside the api "
                "container?",
                file=sys.stderr,
            )
            return 1

    if args.command == "backfill-concept-embeddings":
        try:
            return asyncio.run(_backfill_concept_embeddings(args.batch_size))
        except (OSError, OperationalError, InterfaceError) as exc:
            print(
                f"error: cannot reach the database ({type(exc).__name__}: {exc}) — "
                "is the db service up, and are you running this inside the api "
                "container?",
                file=sys.stderr,
            )
            return 1

    parser.print_usage(sys.stderr)
    print(
        "error: a command is required (ensure-admin, backfill-concept-embeddings)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
