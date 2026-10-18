"""Onboarding service: derivation edges and the unknown-state guard."""

from unittest.mock import AsyncMock

import pytest

from app.services import onboarding_service


def test_check_in_without_a_summary_target_still_finishes() -> None:
    status = onboarding_service.derive_status(
        uploaded=False,
        summary_target=None,
        summary_read=False,
        check_in_done=True,
        checklist="auto",
    )
    assert status.phase == "done" and status.visible is False


@pytest.mark.asyncio
async def test_set_checklist_rejects_an_unknown_state_before_writing() -> None:
    session = AsyncMock()
    with pytest.raises(ValueError):
        await onboarding_service.set_checklist(session, user_id="u", checklist="nope")
    session.execute.assert_not_awaited()
