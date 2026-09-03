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

from app.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import StudyAIOError
from app.services import admin_service


async def _ensure_admin(email: str, username: str | None) -> int:
    """Bootstrap an admin account and print its set-password link."""
    async with async_session_factory() as session:
        try:
            user, token = await admin_service.ensure_admin(session, email, username)
        except (StudyAIOError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        await session.commit()

    base = settings.app_base_url.rstrip("/")
    print(f"admin:  {user.email}  (id {user.id}, role {user.role})")
    print(f"open:   {base}/reset-password?token={quote_plus(token)}")
    print("")
    print("The link is single-use and expires in 24 hours. It is a credential —")
    print("do not paste it into a shared channel or an issue tracker.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
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
        return asyncio.run(_ensure_admin(args.email, args.username))

    parser.print_usage(sys.stderr)
    print("error: a command is required (ensure-admin)", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
