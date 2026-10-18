"""GET/PATCH /api/onboarding on a real Postgres, on the real auth path (`api.onboarding v1`).

Every step is derived from the caller's own rows and the one stored preference
is the caller's own column. Two tenants with very different progress make both
directions observable: another user's data must not move the caller's steps,
and a PATCH must touch exactly one row.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.utils import generate_id
from app.models.flashcard_review import FlashcardReview
from app.models.user import User

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _checklist(db_session, user_id: str) -> str:
    db_session.expire_all()
    return await db_session.scalar(select(User.onboarding_checklist).where(User.id == user_id))


async def test_get_ignores_another_users_progress(make_user, client_factory, db_session):
    alice, bob = await make_user(), await make_user()
    a = await seed_course(db_session, alice.id, code="NET101", week=3)
    b = await seed_course(db_session, bob.id, code="OS201", week=7, flashcards=1)
    db_session.add(
        FlashcardReview(
            id=generate_id(),
            user_id=bob.id,
            flashcard_id=b.flashcards[0].id,
            next_review_at=datetime.now(UTC),
            last_reviewed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    bob_body = (await client_factory(bob).get("/api/onboarding")).json()
    alice_body = (await client_factory(alice).get("/api/onboarding")).json()

    assert bob_body["phase"] == "done"  # his review is real...
    assert alice_body["phase"] == "has_summary"  # ...and none of it is hers
    assert alice_body["steps"]["check_in"] == "active"
    assert alice_body["summary_target"] == {
        "course_id": a.course.id,
        "course_code": "NET101",
        "week": 3,
    }


async def test_get_for_a_user_with_nothing_is_new_despite_populated_tenants(
    make_user, client_factory, db_session
):
    await seed_course(db_session, (await make_user()).id)
    empty = await make_user()

    body = (await client_factory(empty).get("/api/onboarding")).json()

    assert body["phase"] == "new"
    assert body["summary_target"] is None
    assert body["steps"] == {"upload": "active", "summary": "locked", "check_in": "locked"}


async def test_patch_changes_only_the_callers_row(make_user, client_factory, db_session):
    alice, bob = await make_user(), await make_user()
    alice_id, bob_id = alice.id, bob.id  # expire_all() in _checklist unloads attributes
    await seed_course(db_session, alice_id, code="NET101")
    await seed_course(db_session, bob_id, code="OS201")
    bob_client = client_factory(bob)
    before_bob = (await bob_client.get("/api/onboarding")).json()

    response = await client_factory(alice).patch("/api/onboarding", json={"checklist": "dismissed"})

    assert response.status_code == 200
    assert response.json()["checklist"] == "dismissed"
    assert response.json()["visible"] is False
    assert await _checklist(db_session, alice_id) == "dismissed"
    assert await _checklist(db_session, bob_id) == "auto"
    assert (await bob_client.get("/api/onboarding")).json() == before_bob


async def test_patch_rejects_an_unknown_state_and_stores_nothing(
    make_user, client_factory, db_session
):
    alice = await make_user()

    response = await client_factory(alice).patch("/api/onboarding", json={"checklist": "hidden"})

    assert response.status_code == 422
    assert await _checklist(db_session, alice.id) == "auto"


async def test_onboarding_requires_a_caller(client_factory):
    anonymous = client_factory()

    assert (await anonymous.get("/api/onboarding")).status_code == 401
    response = await anonymous.patch("/api/onboarding", json={"checklist": "pinned"})
    assert response.status_code == 401
