"""Security utilities: TOTP, QR codes, backup codes."""

import base64
import hashlib
import hmac
import io
import re
import secrets
from collections.abc import Iterable

import pyotp
import qrcode

#: Crockford base32: the digits and letters that survive being written on paper
#: and typed back. I, L and O are absent because handwriting does not reliably
#: distinguish them from 1, 1 and 0; U is dropped by the same convention, so
#: that a random code cannot spell anything unfortunate. Exactly 32 symbols, so
#: each character carries 5 bits.
BACKUP_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: Characters per code, before display grouping. 16 symbols from a 32-symbol
#: alphabet is 80 bits of entropy -- see `hash_backup_code` for why the length
#: and the choice of hash are one decision, not two.
BACKUP_CODE_LENGTH = 16

#: Characters per dash-separated group when a code is shown to a user.
BACKUP_CODE_GROUP_SIZE = 4

#: Folded onto their canonical symbol when a code is read back in, so a user
#: who writes O for 0 or l for 1 is not locked out by their own handwriting.
_BACKUP_CODE_CONFUSABLES = str.maketrans({"O": "0", "I": "1", "L": "1"})


def setup_totp(user_email: str, issuer: str = "StudyAIO") -> tuple[str, str]:
    """Generate a new TOTP secret and provisioning URI.

    Args:
        user_email: The user's email for the TOTP label.
        issuer: The application name shown in authenticator apps.

    Returns:
        Tuple of (secret, provisioning_uri).
    """
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email,
        issuer_name=issuer,
    )
    return secret, uri


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret.

    Args:
        secret: The base32-encoded TOTP secret.
        code: The 6-digit TOTP code from the user.

    Returns:
        True if the code is valid (within 1 time-step window).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate one-time MFA backup codes in display form.

    Each code is `BACKUP_CODE_LENGTH` symbols of Crockford base32, shown in
    dash-separated groups. Only their hashes are ever stored, so this is the
    one and only moment the raw codes exist.

    Args:
        count: Number of backup codes to generate.

    Returns:
        List of formatted codes, e.g. ``["23AB-45CD-67EF-89GH", ...]``.
    """
    return [
        format_backup_code(
            "".join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(BACKUP_CODE_LENGTH))
        )
        for _ in range(count)
    ]


def format_backup_code(code: str) -> str:
    """Group a canonical code into dashed blocks for display.

    Args:
        code: A normalized code.

    Returns:
        The code in `BACKUP_CODE_GROUP_SIZE`-character groups joined by dashes.
    """
    size = BACKUP_CODE_GROUP_SIZE
    return "-".join(code[i : i + size] for i in range(0, len(code), size))


def normalize_backup_code(code: str) -> str:
    """Canonical form of a backup code as a human actually typed it.

    Dashes, spaces and case are presentation, so they are stripped before the
    code is hashed; the characters excluded from the alphabet are folded onto
    the ones they are confused with. This has to happen on both the storing and
    the checking side, or the two hashes never meet.

    Args:
        code: The code as submitted.

    Returns:
        Uppercase, separator-free, de-confused code. May be empty.
    """
    return re.sub(r"[^0-9A-Z]", "", code.upper()).translate(_BACKUP_CODE_CONFUSABLES)


def hash_backup_code(code: str) -> str:
    """Hash a backup code for storage and comparison.

    SHA-256 rather than the Argon2id password hasher, for the same reason
    `hash_magic_link_token` gives: the value being hashed is one *we* generated
    at full entropy, not one a human chose, so there is no dictionary to run
    and nothing for a slow KDF to slow down. `BACKUP_CODE_LENGTH` exists to
    make that true -- 16 Crockford symbols is 80 bits, which no offline attacker
    reaches at any hash rate. Hashing exists so that reading the database
    (backup, replica, dump, SQL injection) does not yield a usable credential.

    The old 8-character `[A-Z0-9]` format was ~41 bits, which a fast hash would
    *not* have protected; that is why the format widened in the same change
    that started hashing.

    Argon2id was rejected on a second ground as well: a login knows only that
    *some* code was submitted, so it must compare against every stored hash.
    Ten Argon2id verifications per attempt, at 64 MiB each, turns the login
    path into a memory-amplification lever. SHA-256 makes it one hash and a
    set membership test.

    Args:
        code: The raw code, in any form a user might type it.

    Returns:
        Lowercase hex SHA-256 digest (64 chars) of the normalized code.
    """
    return hashlib.sha256(normalize_backup_code(code).encode()).hexdigest()


def hash_backup_codes(codes: Iterable[str]) -> list[str]:
    """Hash a batch of freshly generated codes for storage.

    Args:
        codes: The raw codes.

    Returns:
        Their digests, in the same order.
    """
    return [hash_backup_code(code) for code in codes]


def find_backup_code_hash(code: str, stored_hashes: Iterable[str]) -> str | None:
    """Find which stored digest a submitted code matches.

    Returns the digest rather than a bool so the caller can remove exactly that
    entry -- a backup code is single-use, and "which one" is what consuming it
    needs to know.

    The loop does not break on a match: comparing every candidate keeps the
    work independent of *where* in the list the code sat. `compare_digest` is
    used for the same reason. Neither matters much when both sides are digests
    of an 80-bit secret, but a wrong code and a right one should not differ in
    anything observable.

    Args:
        code: The code as submitted by the user.
        stored_hashes: The digests currently on the account.

    Returns:
        The matching stored digest, or None if the code matches nothing.
    """
    if not normalize_backup_code(code):
        # An empty submission must not match, whatever is stored.
        return None

    candidate = hash_backup_code(code)
    matched: str | None = None
    for stored in stored_hashes:
        if not isinstance(stored, str) or not stored.isascii():
            # `compare_digest` raises TypeError on a non-ASCII str, which on the
            # login path would be a 500. A value of that shape was not written
            # by us and could never match a digest anyway, so skip it. Same
            # fail-closed posture as the column checks in `consume_backup_code`.
            continue
        if hmac.compare_digest(candidate, stored):
            matched = stored
    return matched


def generate_qr_code_base64(provisioning_uri: str) -> str:
    """Generate a QR code image as a base64-encoded PNG string.

    Args:
        provisioning_uri: The TOTP provisioning URI.

    Returns:
        Base64-encoded PNG string (without data URI prefix).
    """
    img = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")
