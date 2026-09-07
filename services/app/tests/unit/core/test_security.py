"""Tests for core security module (TOTP, QR, backup codes)."""

import base64

import pyotp

from app.core.security import (
    BACKUP_CODE_ALPHABET,
    BACKUP_CODE_GROUP_SIZE,
    BACKUP_CODE_LENGTH,
    find_backup_code_hash,
    format_backup_code,
    generate_backup_codes,
    generate_qr_code_base64,
    hash_backup_code,
    hash_backup_codes,
    normalize_backup_code,
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

    def test_codes_carry_the_full_entropy_budget(self):
        """The length is a security parameter, not cosmetics.

        A fast hash is only defensible because the code is wide. If this
        shrinks back towards the old 8 characters, `hash_backup_code`'s choice
        of SHA-256 stops being justifiable and nothing else would notice.
        """
        for code in generate_backup_codes():
            assert len(normalize_backup_code(code)) == BACKUP_CODE_LENGTH

    def test_codes_use_only_the_unambiguous_alphabet(self):
        for code in generate_backup_codes():
            assert set(normalize_backup_code(code)) <= set(BACKUP_CODE_ALPHABET)

    def test_the_confusable_letters_are_never_generated(self):
        """I, L, O and U are absent, so folding them on input is unambiguous."""
        joined = "".join(generate_backup_codes(count=200))
        assert not (set(joined) & set("ILOU"))

    def test_codes_are_shown_in_readable_groups(self):
        for code in generate_backup_codes():
            assert code.count("-") == BACKUP_CODE_LENGTH // BACKUP_CODE_GROUP_SIZE - 1

    def test_codes_are_unique(self):
        codes = generate_backup_codes(count=100)
        assert len(set(codes)) == 100


class TestBackupCodeNormalization:
    """A code as typed by a human must reach the same digest as when issued."""

    def test_display_form_matches_the_canonical_form(self):
        assert normalize_backup_code("23AB-45CD-67EF-89GH") == "23AB45CD67EF89GH"

    def test_lowercase_and_spaces_are_forgiven(self):
        assert normalize_backup_code(" 23ab 45cd ") == "23AB45CD"

    def test_confusable_letters_fold_onto_digits(self):
        assert normalize_backup_code("OIL") == "011"

    def test_an_issued_code_hashes_the_same_however_it_is_typed(self):
        code = generate_backup_codes(count=1)[0]
        assert hash_backup_code(code) == hash_backup_code(code.replace("-", "").lower())

    def test_format_is_the_inverse_of_normalize(self):
        code = generate_backup_codes(count=1)[0]
        assert format_backup_code(normalize_backup_code(code)) == code


class TestBackupCodeHashing:
    """The stored value must not be a usable credential."""

    def test_hash_is_a_sha256_hex_digest(self):
        digest = hash_backup_code("23AB-45CD-67EF-89GH")
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_the_raw_code_does_not_survive_hashing(self):
        code = generate_backup_codes(count=1)[0]
        digest = hash_backup_code(code)
        assert normalize_backup_code(code) not in digest
        assert code not in digest

    def test_hash_batch_preserves_order(self):
        codes = generate_backup_codes(count=3)
        assert hash_backup_codes(codes) == [hash_backup_code(c) for c in codes]

    def test_distinct_codes_hash_distinctly(self):
        codes = generate_backup_codes(count=50)
        assert len(set(hash_backup_codes(codes))) == 50


class TestFindBackupCodeHash:
    """Matching a submitted code against the digests on an account."""

    def test_a_matching_code_returns_its_stored_digest(self):
        codes = generate_backup_codes(count=3)
        hashes = hash_backup_codes(codes)
        assert find_backup_code_hash(codes[1], hashes) == hashes[1]

    def test_a_code_from_another_account_matches_nothing(self):
        mine = hash_backup_codes(generate_backup_codes(count=3))
        theirs = generate_backup_codes(count=1)[0]
        assert find_backup_code_hash(theirs, mine) is None

    def test_a_removed_code_no_longer_matches(self):
        codes = generate_backup_codes(count=3)
        hashes = hash_backup_codes(codes)
        remaining = [h for h in hashes if h != hashes[0]]
        assert find_backup_code_hash(codes[0], remaining) is None

    def test_an_empty_submission_matches_nothing(self):
        hashes = hash_backup_codes(generate_backup_codes(count=3))
        assert find_backup_code_hash("", hashes) is None
        assert find_backup_code_hash("----", hashes) is None

    def test_an_empty_account_matches_nothing(self):
        code = generate_backup_codes(count=1)[0]
        assert find_backup_code_hash(code, []) is None


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
