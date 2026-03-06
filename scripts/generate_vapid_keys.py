#!/usr/bin/env python3
"""Generate VAPID key pair for Web Push notifications.

Run once, then add the output to your .env file.

Usage:
    python scripts/generate_vapid_keys.py
"""

from py_vapid import Vapid


def main() -> None:
    """Generate and print VAPID key pair."""
    vapid = Vapid()
    vapid.generate_keys()

    private_key = vapid.private_pem().decode("utf-8").strip()
    public_key = vapid.public_key_urlsafe_base64()

    print("Add these to your .env file:\n")
    print(f'VAPID_PUBLIC_KEY="{public_key}"')
    print(f'VAPID_PRIVATE_KEY="{private_key}"')
    print(f'VAPID_ADMIN_EMAIL="admin@yourdomain.com"')
    print()
    print(f"Public key (for frontend):\n{public_key}")


if __name__ == "__main__":
    main()
