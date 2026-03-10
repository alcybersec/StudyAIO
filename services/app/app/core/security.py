"""Security utilities: TOTP, QR codes, backup codes."""

import base64
import io
import secrets
import string

import pyotp
import qrcode


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
    """Generate a list of one-time backup codes.

    Args:
        count: Number of backup codes to generate.

    Returns:
        List of 8-character alphanumeric backup codes.
    """
    alphabet = string.ascii_uppercase + string.digits
    return ["".join(secrets.choice(alphabet) for _ in range(8)) for _ in range(count)]


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
