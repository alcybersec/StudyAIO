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

    parser.print_usage(sys.stderr)
    print("error: a command is required (ensure-admin)", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
