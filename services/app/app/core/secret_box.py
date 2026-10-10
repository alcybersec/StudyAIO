"""Authenticated at-rest encryption for per-user credentials (SEC-06, GL#20, R-033).

Values in ``user_settings.settings_json`` named by ``settings_service.SECRET_KEYS``
are stored as ``enc:v1:<fernet token>``. Fernet is AES-128-CBC with an
HMAC-SHA256 tag, so a modified token fails to decrypt instead of yielding
garbage.

The key comes from ``SETTINGS_ENCRYPTION_KEY``: one url-safe base64 Fernet key,
or a comma-separated list. The FIRST key encrypts; every key decrypts, which is
how a key is rotated (prepend the new one, run ``python -m app.cli
encrypt-user-secrets --apply``, then drop the old one).

Without a key: a single-user-mode instance keeps storing plaintext (and logs a
warning at startup); a multi-user one refuses to start.

Nothing here logs or returns a plaintext value.
"""

import sys

import structlog
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings

logger = structlog.get_logger()

#: Marks a stored value as ciphertext. Anything without it is legacy plaintext.
PREFIX = "enc:v1:"

ENV_VAR = "SETTINGS_ENCRYPTION_KEY"

#: The all-zero Fernet key the root conftest installs so the suite can start the
#: lifespan in multi-user mode. It is public, so it protects nothing.
WELL_KNOWN_TEST_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def _running_under_pytest() -> bool:
    """Test-mode signal that no environment variable can fake in production."""
    return "pytest" in sys.modules


class SecretBoxError(Exception):
    """The secret store is misconfigured (e.g. no key where one is required)."""


class SecretDecryptError(SecretBoxError):
    """A stored value could not be decrypted (tampered, wrong key, or no key)."""


def _keys() -> list[Fernet]:
    raw = settings.settings_encryption_key.get_secret_value()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return [Fernet(p.encode()) for p in parts]
    except (ValueError, TypeError) as exc:
        raise SecretBoxError(f"{ENV_VAR} contains a key that is not a valid Fernet key") from exc


def is_configured() -> bool:
    """Whether an encryption key is set."""
    return bool(settings.settings_encryption_key.get_secret_value().strip())


def is_encrypted(value: object) -> bool:
    """Whether a stored value is ciphertext produced by this module."""
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(plaintext: str) -> str:
    """Encrypt a credential for storage.

    Args:
        plaintext: The credential value.

    Returns:
        ``enc:v1:<token>``; the value unchanged when no key is set on a
        single-user instance.

    Raises:
        SecretBoxError: No key is set and the instance is not in single-user mode, or
            no key is set and the value looks like ciphertext (it would be
            misread on the way back).
    """
    # No pass-through for values that merely look like ciphertext: a user can
    # submit "enc:v1:..." as their API key, and storing it verbatim would make it
    # unreadable (or, worse, trusted as already-protected). Always encrypt.
    if not is_configured():
        if settings.single_user_mode:
            if is_encrypted(plaintext):
                raise SecretBoxError(
                    "a credential may not start with the reserved prefix 'enc:v1:'"
                )
            return plaintext
        raise SecretBoxError(f"{ENV_VAR} is not set; refusing to store a credential in plaintext")
    token = MultiFernet(_keys()).encrypt(plaintext.encode()).decode()
    return f"{PREFIX}{token}"


def decrypt(stored: str) -> str:
    """Return the plaintext of a stored credential.

    Legacy plaintext (no prefix) is returned as is.

    Args:
        stored: A value read from ``settings_json``.

    Returns:
        The plaintext credential.

    Raises:
        SecretDecryptError: Ciphertext that is tampered with, written under a
            key no longer configured, or read with no key at all.
    """
    if not is_encrypted(stored):
        return stored
    if not is_configured():
        raise SecretDecryptError(f"stored credential is encrypted but {ENV_VAR} is not set")
    try:
        return MultiFernet(_keys()).decrypt(stored[len(PREFIX) :].encode()).decode()
    except (InvalidToken, SecretBoxError) as exc:
        raise SecretDecryptError("stored credential failed authentication") from exc


def needs_rotation(stored: str) -> bool:
    """Whether ciphertext was written under a key other than the current first one."""
    if not is_encrypted(stored) or not is_configured():
        return False
    try:
        keys = _keys()
        keys[0].decrypt(stored[len(PREFIX) :].encode())
    except (InvalidToken, SecretBoxError):
        return True
    return False


def check_startup() -> None:
    """Fail fast on a missing or malformed key.

    Raises:
        RuntimeError: Key malformed, or missing on a multi-user instance.
    """
    if not is_configured():
        if not settings.single_user_mode:
            raise RuntimeError(
                f"FATAL: {ENV_VAR} is not set. User AI credentials must be encrypted at "
                'rest in SaaS mode. Generate one with: python -c "from '
                'cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        logger.warning(
            "settings_encryption_key_unset",
            detail=f"{ENV_VAR} is unset: per-user AI credentials are stored in plaintext",
        )
        return
    try:
        _keys()
    except SecretBoxError as exc:
        raise RuntimeError(f"FATAL: {ENV_VAR} is malformed: {exc}") from exc
    raw = settings.settings_encryption_key.get_secret_value()
    if (
        not settings.single_user_mode
        and not _running_under_pytest()
        and WELL_KNOWN_TEST_KEY in (p.strip() for p in raw.split(","))
    ):
        raise RuntimeError(
            f"FATAL: {ENV_VAR} is the well-known all-zero test key. Generate a real one "
            'with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
