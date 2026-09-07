"""Tests for the backup-code hashing migration (issue #71).

The migration is loaded by path -- Alembic version modules are not importable
as a package -- and its row decision is exercised directly, which is the whole
of its behaviour. Following `test_provider_backfill_migration.py`.

The decision is deliberately asymmetric: anything that cannot be positively
identified as already-hashed is cleared. A false "clear" costs a user one
re-enrollment; a false "keep" leaves a plaintext MFA credential in the column,
which is the entire reason the migration exists.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b8c9d0e1f2g3_hash_mfa_backup_codes.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("backup_code_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load()


def _digests(*values: str) -> str:
    """A column value in the post-migration format."""
    return json.dumps([hashlib.sha256(v.encode()).hexdigest() for v in values])


class TestPlaintextIsCleared:
    """The pre-migration format is discarded rather than hashed forward."""

    def test_old_format_codes_are_cleared(self, migration):
        """Eight characters of [A-Z0-9] -- about 41 bits, and never verifiable.

        Hashing these forward would make a weak secret live for the first time.
        """
        assert migration.needs_clearing(json.dumps(["ABCD1234", "EFGH5678"])) is True

    def test_a_single_plaintext_code_is_cleared(self, migration):
        assert migration.needs_clearing(json.dumps(["ABCD1234"])) is True

    def test_new_format_plaintext_is_also_cleared(self, migration):
        """Belt and braces: the shape check is "is it a digest", not "is it 8 chars"."""
        assert migration.needs_clearing(json.dumps(["23AB-45CD-67EF-89GH"])) is True

    def test_a_partially_hashed_array_is_cleared(self, migration):
        """One plaintext survivor is one MFA bypass; the array goes as a unit."""
        mixed = json.loads(_digests("one", "two"))
        mixed.append("ABCD1234")
        assert migration.needs_clearing(json.dumps(mixed)) is True

    def test_an_uppercase_digest_is_not_trusted(self, migration):
        """`hexdigest()` is lowercase. Anything else was not written by us."""
        upper = [h.upper() for h in json.loads(_digests("one"))]
        assert migration.needs_clearing(json.dumps(upper)) is True

    def test_a_truncated_digest_is_cleared(self, migration):
        short = [json.loads(_digests("one"))[0][:32]]
        assert migration.needs_clearing(json.dumps(short)) is True

    def test_non_string_members_are_cleared(self, migration):
        assert migration.needs_clearing(json.dumps([1, 2, 3])) is True


class TestMalformedIsCleared:
    """A value we cannot authenticate against is a value we do not keep."""

    def test_unparseable_json_is_cleared(self, migration):
        assert migration.needs_clearing("not json {{{") is True

    def test_a_bare_string_is_cleared(self, migration):
        assert migration.needs_clearing(json.dumps("ABCD1234")) is True

    def test_an_object_is_cleared(self, migration):
        assert migration.needs_clearing(json.dumps({"codes": ["ABCD1234"]})) is True


class TestAlreadyHashedIsLeftAlone:
    """Idempotent: safe to run twice, and safe if the new app wrote first."""

    def test_a_full_array_of_digests_survives(self, migration):
        assert migration.needs_clearing(_digests("one", "two", "three")) is False

    def test_ten_digests_survive(self, migration):
        assert migration.needs_clearing(_digests(*[str(i) for i in range(10)])) is False

    def test_an_exhausted_account_is_left_alone(self, migration):
        """`[]` is what the app writes once the last code has been spent."""
        assert migration.needs_clearing("[]") is False


class TestNothingStored:
    """No churn on rows with nothing to clear."""

    def test_null_is_left_alone(self, migration):
        assert migration.needs_clearing(None) is False

    def test_an_empty_string_is_left_alone(self, migration):
        assert migration.needs_clearing("") is False
        assert migration.needs_clearing("   ") is False


class TestRoundTripAgainstTheRealHasher:
    """The migration's notion of "already hashed" must match the app's output."""

    def test_the_application_format_is_recognised(self, migration):
        from app.core.security import generate_backup_codes, hash_backup_codes

        stored = json.dumps(hash_backup_codes(generate_backup_codes()))
        assert migration.needs_clearing(stored) is False

    def test_the_raw_application_codes_are_not(self, migration):
        from app.core.security import generate_backup_codes

        assert migration.needs_clearing(json.dumps(generate_backup_codes())) is True
