"""Unit tests for invite code issuing and redemption."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.auth import generate_magic_link_token, hash_magic_link_token
from app.core.exceptions import InviteError
from app.models.invite_code import InviteCode
from app.services import invite_service


def make_invite(**overrides) -> InviteCode:
    """Build an InviteCode without touching the database."""
    defaults = {
        "id": "inv-1",
        "code": "BETA-ABCD2345",
        "max_uses": 1,
        "used_count": 0,
        "expires_at": datetime.now(UTC) + timedelta(days=30),
        "revoked_at": None,
        "email": None,
        "token_hash": None,
        "sent_at": None,
        "accepted_at": None,
    }
    defaults.update(overrides)
    return InviteCode(**defaults)


class TestGenerateCode:
    def test_has_the_beta_prefix(self):
        assert invite_service.generate_code().startswith("BETA-")

    def test_has_the_expected_length(self):
        code = invite_service.generate_code()
        assert len(code) == len("BETA-") + invite_service.CODE_LENGTH

    def test_avoids_visually_ambiguous_characters(self):
        """0/O and 1/I/L get misread when a tester types a code by hand."""
        for _ in range(50):
            body = invite_service.generate_code().removeprefix("BETA-")
            assert not set(body) & set("01OIL")

    def test_codes_are_not_repeated(self):
        codes = {invite_service.generate_code() for _ in range(200)}
        assert len(codes) == 200


class TestNormalizeCode:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("beta-abcd2345", "BETA-ABCD2345"),
            ("  BETA-ABCD2345  ", "BETA-ABCD2345"),
            ("Beta-Abcd2345", "BETA-ABCD2345"),
        ],
    )
    def test_normalizes_case_and_whitespace(self, raw, expected):
        assert invite_service.normalize_code(raw) == expected


class TestIsRedeemable:
    def test_fresh_code_is_redeemable(self):
        assert make_invite().is_redeemable() is True

    def test_revoked_code_is_not(self):
        assert make_invite(revoked_at=datetime.now(UTC)).is_redeemable() is False

    def test_expired_code_is_not(self):
        expired = make_invite(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        assert expired.is_redeemable() is False

    def test_used_up_code_is_not(self):
        assert make_invite(max_uses=2, used_count=2).is_redeemable() is False

    def test_partially_used_multi_use_code_is(self):
        assert make_invite(max_uses=5, used_count=2).is_redeemable() is True

    def test_code_without_expiry_never_expires(self):
        assert make_invite(expires_at=None).is_redeemable() is True

    def test_uses_remaining_never_goes_negative(self):
        assert make_invite(max_uses=1, used_count=3).uses_remaining == 0


class TestCreateInvite:
    @pytest.mark.asyncio
    async def test_persists_a_code(self, mock_session):
        invite = await invite_service.create_invite(mock_session, created_by="admin-1")
        assert invite.code.startswith("BETA-")
        assert invite.created_by == "admin-1"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_sets_expiry_from_days(self, mock_session):
        invite = await invite_service.create_invite(mock_session, expires_in_days=7)
        assert invite.expires_at is not None
        delta = invite.expires_at - datetime.now(UTC)
        assert timedelta(days=6) < delta <= timedelta(days=7)

    @pytest.mark.asyncio
    async def test_none_expiry_means_no_expiry(self, mock_session):
        invite = await invite_service.create_invite(mock_session, expires_in_days=None)
        assert invite.expires_at is None

    @pytest.mark.asyncio
    async def test_rejects_zero_max_uses(self, mock_session):
        with pytest.raises(InviteError):
            await invite_service.create_invite(mock_session, max_uses=0)

    @pytest.mark.asyncio
    async def test_rejects_negative_expiry(self, mock_session):
        with pytest.raises(InviteError):
            await invite_service.create_invite(mock_session, expires_in_days=0)

    @pytest.mark.asyncio
    async def test_carries_the_note(self, mock_session):
        invite = await invite_service.create_invite(mock_session, note="tester A")
        assert invite.note == "tester A"


class TestRedeemInvite:
    def _with_invite(self, mock_session, invite):
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

    @pytest.mark.asyncio
    async def test_consumes_one_use(self, mock_session):
        invite = make_invite(max_uses=3, used_count=1)
        self._with_invite(mock_session, invite)

        redeemed = await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

        assert redeemed.used_count == 2
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_accepts_a_lowercase_code(self, mock_session):
        self._with_invite(mock_session, make_invite())
        redeemed = await invite_service.redeem_invite(mock_session, "  beta-abcd2345 ")
        assert redeemed.used_count == 1

    @pytest.mark.asyncio
    async def test_rejects_an_empty_code(self, mock_session):
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "")

    @pytest.mark.asyncio
    async def test_rejects_a_whitespace_code(self, mock_session):
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "   ")

    @pytest.mark.asyncio
    async def test_rejects_an_unknown_code(self, mock_session):
        self._with_invite(mock_session, None)
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "BETA-NOPENOPE")

    @pytest.mark.asyncio
    async def test_rejects_a_revoked_code(self, mock_session):
        self._with_invite(mock_session, make_invite(revoked_at=datetime.now(UTC)))
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

    @pytest.mark.asyncio
    async def test_rejects_an_expired_code(self, mock_session):
        self._with_invite(
            mock_session, make_invite(expires_at=datetime.now(UTC) - timedelta(days=1))
        )
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

    @pytest.mark.asyncio
    async def test_rejects_a_used_up_code(self, mock_session):
        self._with_invite(mock_session, make_invite(max_uses=1, used_count=1))
        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

    @pytest.mark.asyncio
    async def test_does_not_reveal_that_a_code_exists(self, mock_session):
        """Unknown and spent codes must be indistinguishable to a guesser."""
        self._with_invite(mock_session, None)
        with pytest.raises(InviteError) as unknown:
            await invite_service.redeem_invite(mock_session, "BETA-UNKNOWN1")

        self._with_invite(mock_session, make_invite(max_uses=1, used_count=1))
        with pytest.raises(InviteError) as spent:
            await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

        assert str(unknown.value) == str(spent.value)

    @pytest.mark.asyncio
    async def test_locks_the_row(self, mock_session):
        """Two simultaneous registrations must not both spend the last use."""
        self._with_invite(mock_session, make_invite())
        await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")
        statement = str(mock_session.execute.call_args[0][0])
        assert "FOR UPDATE" in statement.upper()


class TestRevokeInvite:
    @pytest.mark.asyncio
    async def test_sets_revoked_at(self, mock_session):
        invite = make_invite()
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

        revoked = await invite_service.revoke_invite(mock_session, "inv-1")

        assert revoked.revoked_at is not None
        assert revoked.is_redeemable() is False

    @pytest.mark.asyncio
    async def test_is_idempotent(self, mock_session):
        first = datetime.now(UTC) - timedelta(days=1)
        invite = make_invite(revoked_at=first)
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

        revoked = await invite_service.revoke_invite(mock_session, "inv-1")

        assert revoked.revoked_at == first

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_invite(self, mock_session):
        assert await invite_service.revoke_invite(mock_session, "nope") is None


class TestCreateEmailInvite:
    """Email invites: addressed to one person, redeemed with a token."""

    @pytest.mark.asyncio
    async def test_returns_the_raw_token_only_here(self, mock_session):
        """The token is never recoverable afterwards — only its hash is stored."""
        minted = await invite_service.create_email_invite(mock_session, email="tester@example.com")

        assert minted.raw_token
        assert minted.invite.token_hash == hash_magic_link_token(minted.raw_token)
        # The load-bearing assertion: the raw value is NOT on the row.
        assert minted.raw_token not in (minted.invite.token_hash or "")

    @pytest.mark.asyncio
    async def test_is_single_use(self, mock_session):
        """Multi-use would let a forwarded invite be redeemed by someone else,
        and accepted_at would still credit the addressee."""
        minted = await invite_service.create_email_invite(mock_session, email="tester@example.com")
        assert minted.invite.max_uses == 1

    @pytest.mark.asyncio
    async def test_normalizes_the_address(self, mock_session):
        minted = await invite_service.create_email_invite(
            mock_session, email="  Tester@Example.COM  "
        )
        assert minted.invite.email == "tester@example.com"

    @pytest.mark.asyncio
    async def test_is_not_marked_sent_on_creation(self, mock_session):
        """Created and delivered are different facts. With SMTP down the invite
        exists and its link works, but nobody was told."""
        minted = await invite_service.create_email_invite(mock_session, email="tester@example.com")
        assert minted.invite.sent_at is None

    @pytest.mark.asyncio
    async def test_rejects_a_blank_address(self, mock_session):
        with pytest.raises(InviteError):
            await invite_service.create_email_invite(mock_session, email="   ")


class TestRedeemToken:
    """Redemption accepts a token through the same field as a code."""

    def _with_invite(self, mock_session, invite):
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

    @pytest.mark.asyncio
    async def test_redeems_an_email_invite_by_token(self, mock_session):
        token = generate_magic_link_token()
        invite = make_invite(email="tester@example.com", token_hash=hash_magic_link_token(token))
        self._with_invite(mock_session, invite)

        # The address is required now: an email invite is redeemable only by the
        # person it was sent to. See TestEmailInviteBinding.
        redeemed = await invite_service.redeem_invite(
            mock_session, token, email="tester@example.com"
        )

        assert redeemed.used_count == 1
        assert redeemed.accepted_at is not None

    @pytest.mark.asyncio
    async def test_looks_the_token_up_by_hash_not_by_value(self, mock_session):
        """The wiring assertion. A token compared against `code` would 'work'
        for an unknown token (both miss) while storing a raw credential."""
        token = generate_magic_link_token()
        invite = make_invite(token_hash=hash_magic_link_token(token))
        self._with_invite(mock_session, invite)

        await invite_service.redeem_invite(mock_session, token)

        # The WHERE clause, not the whole statement: every column appears in
        # the SELECT list, so matching on the full text passes either way.
        where = str(mock_session.execute.await_args.args[0]).split("WHERE", 1)[1]
        assert "token_hash" in where
        assert "invite_codes.code" not in where

    @pytest.mark.asyncio
    async def test_does_not_uppercase_a_token(self, mock_session):
        """normalize_code() uppercases, which is right for a transcribed code
        and destroys a base64url token. Branch order is what protects this."""
        token = "aB-cD_eF" * 5  # mixed case, url-safe alphabet
        invite = make_invite(token_hash=hash_magic_link_token(token))
        self._with_invite(mock_session, invite)

        await invite_service.redeem_invite(mock_session, token)

        # The hash of the UPPERCASED token would not match the stored one.
        assert hash_magic_link_token(token) != hash_magic_link_token(token.upper())

    @pytest.mark.asyncio
    async def test_an_unknown_token_is_rejected_identically_to_an_unknown_code(self, mock_session):
        """Distinct wording would tell a stranger which guesses landed."""
        self._with_invite(mock_session, None)
        with pytest.raises(InviteError) as token_err:
            await invite_service.redeem_invite(mock_session, generate_magic_link_token())

        self._with_invite(mock_session, None)
        with pytest.raises(InviteError) as code_err:
            await invite_service.redeem_invite(mock_session, "BETA-ZZZZ9999")

        assert str(token_err.value) == str(code_err.value)

    @pytest.mark.asyncio
    async def test_a_spent_invite_is_rejected_identically_to_an_unknown_one(self, mock_session):
        token = generate_magic_link_token()
        self._with_invite(
            mock_session,
            make_invite(token_hash=hash_magic_link_token(token), used_count=1, max_uses=1),
        )
        with pytest.raises(InviteError) as spent:
            await invite_service.redeem_invite(mock_session, token)

        self._with_invite(mock_session, None)
        with pytest.raises(InviteError) as unknown:
            await invite_service.redeem_invite(mock_session, generate_magic_link_token())

        assert str(spent.value) == str(unknown.value)

    @pytest.mark.asyncio
    async def test_accepted_at_is_set_once_not_on_every_redemption(self, mock_session):
        """A shared code records when it was FIRST accepted. Overwriting would
        retarget the funnel's conversion at the most recent registrant."""
        first = datetime(2026, 1, 1, tzinfo=UTC)
        invite = make_invite(max_uses=5, used_count=1, accepted_at=first)
        self._with_invite(mock_session, invite)

        await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

        assert invite.accepted_at == first

    @pytest.mark.asyncio
    async def test_a_code_still_redeems_by_code(self, mock_session):
        """The token branch must not have broken the original path."""
        invite = make_invite()
        self._with_invite(mock_session, invite)

        await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")

        where = str(mock_session.execute.await_args.args[0]).split("WHERE", 1)[1]
        assert "invite_codes.code" in where
        assert "token_hash" not in where


class TestResendEmailInvite:
    """Resending rotates the token: the original is unrecoverable by design."""

    @pytest.mark.asyncio
    async def test_issues_a_different_token(self, mock_session, monkeypatch):
        original = make_invite(
            email="tester@example.com", token_hash=hash_magic_link_token("old-token")
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = original
        mock_session.execute.return_value = result

        minted = await invite_service.resend_email_invite(mock_session, "inv-1")

        assert minted is not None
        assert minted.raw_token != "old-token"
        assert minted.invite.token_hash == hash_magic_link_token(minted.raw_token)

    @pytest.mark.asyncio
    async def test_the_previous_link_stops_working(self, mock_session):
        """The load-bearing one. A resend that left the old token live would mean
        the first email stays a working credential wherever it now sits."""
        old_token = generate_magic_link_token()
        invite = make_invite(
            email="tester@example.com", token_hash=hash_magic_link_token(old_token)
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

        await invite_service.resend_email_invite(mock_session, "inv-1")

        assert invite.token_hash != hash_magic_link_token(old_token)

    @pytest.mark.asyncio
    async def test_clears_sent_at(self, mock_session):
        """Until the new email goes out, the row must not claim a delivery."""
        invite = make_invite(
            email="t@x.com",
            token_hash=hash_magic_link_token("t"),
            sent_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

        await invite_service.resend_email_invite(mock_session, "inv-1")

        assert invite.sent_at is None

    @pytest.mark.asyncio
    async def test_renews_an_expired_invite(self, mock_session):
        """An expired link is the usual reason to resend, so a fresh token with
        the old dead expiry would be useless."""
        invite = make_invite(
            email="t@x.com",
            token_hash=hash_magic_link_token("t"),
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

        await invite_service.resend_email_invite(mock_session, "inv-1", expires_in_days=14)

        assert invite.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_refuses_a_shared_code(self, mock_session):
        """A shared code has no address to send to."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = make_invite()
        mock_session.execute.return_value = result

        with pytest.raises(InviteError):
            await invite_service.resend_email_invite(mock_session, "inv-1")

    @pytest.mark.asyncio
    async def test_refuses_a_revoked_invite(self, mock_session):
        """Revoking was a decision; re-inviting past it should be explicit."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = make_invite(
            email="t@x.com",
            token_hash=hash_magic_link_token("t"),
            revoked_at=datetime.now(UTC),
        )
        mock_session.execute.return_value = result

        with pytest.raises(InviteError):
            await invite_service.resend_email_invite(mock_session, "inv-1")

    @pytest.mark.asyncio
    async def test_refuses_one_already_accepted(self, mock_session):
        """The account exists — that person needs a password reset, not an
        invitation."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = make_invite(
            email="t@x.com", token_hash=hash_magic_link_token("t"), used_count=1, max_uses=1
        )
        mock_session.execute.return_value = result

        with pytest.raises(InviteError):
            await invite_service.resend_email_invite(mock_session, "inv-1")

    @pytest.mark.asyncio
    async def test_returns_none_for_an_unknown_invite(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        assert await invite_service.resend_email_invite(mock_session, "nope") is None


class TestEmailInviteBinding:
    """An email invite is redeemable only by the address it was sent to."""

    def _with_invite(self, mock_session, invite):
        result = MagicMock()
        result.scalar_one_or_none.return_value = invite
        mock_session.execute.return_value = result

    def _email_invite(self, token, **overrides):
        return make_invite(
            email="sam@example.com", token_hash=hash_magic_link_token(token), **overrides
        )

    @pytest.mark.asyncio
    async def test_the_addressee_can_redeem(self, mock_session):
        token = generate_magic_link_token()
        self._with_invite(mock_session, self._email_invite(token))

        redeemed = await invite_service.redeem_invite(mock_session, token, email="sam@example.com")

        assert redeemed.used_count == 1

    @pytest.mark.asyncio
    async def test_a_forwarded_link_is_refused(self, mock_session):
        """Being sent the link is not the same as being entitled to it."""
        token = generate_magic_link_token()
        self._with_invite(mock_session, self._email_invite(token))

        with pytest.raises(InviteError):
            await invite_service.redeem_invite(
                mock_session, token, email="someone-else@example.com"
            )

    @pytest.mark.asyncio
    async def test_a_refused_forward_does_not_consume_the_use(self, mock_session):
        """The load-bearing one. Burning the use would let a stranger destroy an
        invitation the real invitee is still waiting to accept."""
        token = generate_magic_link_token()
        invite = self._email_invite(token)
        self._with_invite(mock_session, invite)

        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, token, email="nope@example.com")

        assert invite.used_count == 0
        assert invite.accepted_at is None

    @pytest.mark.asyncio
    async def test_the_match_ignores_case_and_whitespace(self, mock_session):
        """Sign-up forms hand back what people type."""
        token = generate_magic_link_token()
        self._with_invite(mock_session, self._email_invite(token))

        redeemed = await invite_service.redeem_invite(
            mock_session, token, email="  SAM@Example.COM  "
        )

        assert redeemed.used_count == 1

    @pytest.mark.asyncio
    async def test_a_missing_email_is_refused(self, mock_session):
        """No address supplied cannot silently pass the check."""
        token = generate_magic_link_token()
        self._with_invite(mock_session, self._email_invite(token))

        with pytest.raises(InviteError):
            await invite_service.redeem_invite(mock_session, token, email=None)

    @pytest.mark.asyncio
    async def test_a_shared_code_is_unaffected(self, mock_session):
        """Shared codes name no recipient, so any address may redeem one."""
        self._with_invite(mock_session, make_invite())

        redeemed = await invite_service.redeem_invite(
            mock_session, "BETA-ABCD2345", email="anyone@example.com"
        )

        assert redeemed.used_count == 1

    @pytest.mark.asyncio
    async def test_a_shared_code_redeems_with_no_email_at_all(self, mock_session):
        """Back-compat: callers that never pass an address still work."""
        self._with_invite(mock_session, make_invite())
        assert (await invite_service.redeem_invite(mock_session, "BETA-ABCD2345")).used_count == 1

    @pytest.mark.asyncio
    async def test_an_expired_invite_reports_the_generic_error_not_the_mismatch(self, mock_session):
        """Ordering matters: the enumeration-safe rejection must win, so an
        attacker cannot use the mismatch message to confirm a token exists."""
        token = generate_magic_link_token()
        self._with_invite(
            mock_session,
            self._email_invite(token, expires_at=datetime(2020, 1, 1, tzinfo=UTC)),
        )

        with pytest.raises(InviteError) as expired:
            await invite_service.redeem_invite(mock_session, token, email="wrong@example.com")

        self._with_invite(mock_session, None)
        with pytest.raises(InviteError) as unknown:
            await invite_service.redeem_invite(mock_session, generate_magic_link_token())

        assert str(expired.value) == str(unknown.value)
