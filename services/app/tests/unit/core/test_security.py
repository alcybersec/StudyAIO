"""Tests for core security module (TOTP, QR, backup codes)."""

import base64

import pyotp

from app.core.security import (
    generate_backup_codes,
    generate_qr_code_base64,
    setup_totp,
    verify_totp,
)


class TestTOTP:
    """TOTP setup and verification."""

    def test_setup_totp_returns_secret_and_uri(self):
        secret, uri = setup_totp("user@example.com")
        assert isinstance(secret, str)
        assert len(secret) == 32  # pyotp default base32 length
        assert "otpauth://totp/" in uri
        assert "user%40example.com" in uri or "user@example.com" in uri
        assert "StudyAIO" in uri

    def test_setup_totp_custom_issuer(self):
        _, uri = setup_totp("user@example.com", issuer="MyApp")
        assert "MyApp" in uri

    def test_verify_totp_valid_code(self):
        secret, _ = setup_totp("user@example.com")
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid_code(self):
        secret, _ = setup_totp("user@example.com")
        assert verify_totp(secret, "000000") is False

    def test_verify_totp_wrong_secret(self):
        secret1, _ = setup_totp("user1@example.com")
        secret2, _ = setup_totp("user2@example.com")
        totp = pyotp.TOTP(secret1)
        code = totp.now()
        # Code from secret1 should not verify with secret2
        assert verify_totp(secret2, code) is False


class TestBackupCodes:
    """Backup code generation."""

    def test_generate_default_count(self):
        codes = generate_backup_codes()
        assert len(codes) == 10

    def test_generate_custom_count(self):
        codes = generate_backup_codes(count=5)
        assert len(codes) == 5

    def test_codes_are_8_chars(self):
        codes = generate_backup_codes()
        for code in codes:
            assert len(code) == 8

    def test_codes_alphanumeric_uppercase(self):
        codes = generate_backup_codes()
        for code in codes:
            assert code.isalnum()
            assert code == code.upper()

    def test_codes_are_unique(self):
        codes = generate_backup_codes(count=100)
        assert len(set(codes)) == 100


class TestQRCode:
    """QR code generation."""

    def test_generate_qr_code_returns_base64(self):
        _, uri = setup_totp("user@example.com")
        b64 = generate_qr_code_base64(uri)
        assert isinstance(b64, str)
        # Should be valid base64
        decoded = base64.b64decode(b64)
        # PNG magic bytes
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_qr_code_nonempty(self):
        _, uri = setup_totp("user@example.com")
        b64 = generate_qr_code_base64(uri)
        assert len(b64) > 100  # A QR code PNG should be substantial
