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
import pathlib
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


async def _backfill_courseops_keys(dry_run: bool, keep_legacy: bool) -> int:
    """Give existing course document blobs a per-user key.

    `courseops/<sha256[:16]>_<name>` was content-addressed with no owner, so two
    users who uploaded the same handbook shared one blob and the account-deletion
    purge could not touch it (#107). Keys are
    `courseops/<user_id>/<sha256[:16]>_<name>` now, and revision `4f1c7a2e9b63`
    re-keys the column — this moves the files, which a migration cannot, because
    it runs wherever alembic runs and not necessarily where the blobs are.

    Lives here rather than only in `scripts/backfill_courseops_files.py` because
    the repo-root `scripts/` directory is in neither the image (the build context
    is `services/app`) nor any compose mount, so the script is unreachable from
    a deployed container. This entrypoint ships in the image.

    Idempotent. Copies rather than moves, since several accounts may reference
    one legacy blob and each needs their own.

    Args:
        dry_run: Report what would change and write nothing.
        keep_legacy: Leave the old-shape blobs on disk.

    Returns:
        A process exit code.
    """
    from app.services import courseops_service

    async with async_session_factory() as session:
        counts = await courseops_service.backfill_courseops_storage_keys(
            session,
            delete_legacy=not keep_legacy,
            dry_run=dry_run,
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    verb = "would copy" if dry_run else "copied"
    print(
        f"{counts['rows']} course document(s): {verb} {counts['blobs_copied']} blob(s), "
        f"{counts['paths_updated']} file_path value(s) re-keyed, "
        f"{counts['legacy_deleted']} legacy blob(s) "
        f"{'would be deleted' if dry_run else 'deleted'}."
    )
    if counts["legacy_missing"]:
        print(
            f"{counts['legacy_missing']} row(s) pointed at a legacy blob that was already "
            "missing; they were re-keyed anyway."
        )
    if dry_run:
        print("Dry run: nothing was copied, updated or deleted.")
    return 0


async def _run_evals(only: str | None, no_judge: bool, out: str | None, n: int) -> int:
    """Score generated summaries against the eval cases.

    `tests/golden/` checks that a summary has the right shape; nothing measured
    whether it is any good, so a prompt change could be an improvement or a
    regression and the suite said the same either way.

    Deliberately not part of CI: it costs money and is not deterministic, and a
    non-deterministic gate is worse than no gate. Run it when a prompt changes
    and read it against the previous run.

    Args:
        only: Run a single case id.
        no_judge: Skip the model-graded faithfulness check, leaving only the
            deterministic scores — which need no credentials and cost nothing.
        out: Write the full report as JSON here, for diffing against last time.
        n: Repetitions per case. Generation is non-deterministic, so a single
            run is a sample: the first live run of this harness found four
            fabrications on one case where a later run found one. Repeating
            separates a fabrication that happens every time — a property of the
            prompt — from one that happened once.

    Returns:
        A process exit code: non-zero if any case failed, so it is usable in a
        script even though it is not wired into CI.
    """
    from evals.runner import format_report, run

    report = await run(only=only, judge=not no_judge, n=n)
    print(format_report(report))

    if out:
        import json as _json

        pathlib.Path(out).write_text(_json.dumps(report.to_dict(), indent=2) + "\n")
        print(f"\nJSON written to {out}")

    # report.cases, not report.scores: the aggregate rename that came with the
    # -n flag missed this line, and because it runs AFTER the report prints, the
    # output looked completely healthy above an AttributeError traceback.
    return 0 if report.passed == len(report.cases) else 1


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

    courseops = sub.add_parser(
        "backfill-courseops-keys",
        help="Give existing course document blobs a per-user storage key (issue #107)",
    )
    courseops.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without copying, updating or deleting anything",
    )
    courseops.add_argument(
        "--keep-legacy",
        action="store_true",
        help="Leave the old-shape blobs on disk",
    )

    evals = sub.add_parser(
        "evals",
        help="Score generated summaries against the eval cases (costs AI calls)",
    )
    evals.add_argument("--case", default=None, help="Run a single case by id")
    evals.add_argument(
        "--no-judge",
        action="store_true",
        help="Deterministic scores only — no model needed, no cost",
    )
    evals.add_argument("--out", default=None, help="Write the full report as JSON here")
    evals.add_argument(
        "-n",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run each case N times. Generation is non-deterministic, so one run "
            "is a sample — this separates persistent findings from occasional "
            "ones. Multiplies the cost by N."
        ),
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

    if args.command == "backfill-courseops-keys":
        try:
            return asyncio.run(_backfill_courseops_keys(args.dry_run, args.keep_legacy))
        except (OSError, OperationalError, InterfaceError) as exc:
            print(
                f"error: cannot reach the database ({type(exc).__name__}: {exc}) — "
                "is the db service up, and are you running this inside the api "
                "container?",
                file=sys.stderr,
            )
            return 1

    if args.command == "evals":
        try:
            return asyncio.run(_run_evals(args.case, args.no_judge, args.out, args.n))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    parser.print_usage(sys.stderr)
    print(
        "error: a command is required (ensure-admin, backfill-concept-embeddings, "
        "backfill-courseops-keys, evals)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
