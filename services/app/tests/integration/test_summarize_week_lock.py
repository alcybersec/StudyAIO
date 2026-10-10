"""TECH-05 (GL#23): summarize is serialised per (user, course, week) by a real
Postgres advisory lock (floor 4: no summary version is lost or duplicated).

Two artifacts of one week are summarized concurrently on two independent
sessions/connections. The agent call sits inside the locked region, so if the
lock works the two agent calls never overlap, the loser reads the winner's
committed summary (and gets it as `existing_summary`), and the versions come out
as exactly 1 then 2. Without the lock both read "no summary", both write
version 1 and one fails on the unique constraint.
"""

import asyncio
import hashlib
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.agents.base import SummaryResult
from app.core.database import async_session_factory, engine
from app.core.utils import generate_id
from app.models.course import Course
from app.models.summary import Summary
from app.models.user import User
from app.pipeline import summarize as summarize_stage
from app.pipeline.classify import _classify
from app.pipeline.extract import _extract
from app.pipeline.resilience import StageBusyError
from app.pipeline.summarize import _summarize, _week_lock
from app.services import account_service, artifact_service

from ._support import FakeAgent, make_pdf

pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass
class _GatedAgent(FakeAgent):
    """Records how many summary calls are in flight at once."""

    active: int = 0
    max_active: int = 0
    seen_existing: list[str | None] = field(default_factory=list)

    async def generate_summary(self, extraction, existing_summary):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.seen_existing.append(existing_summary)
        try:
            await asyncio.sleep(0.4)  # long enough for the other run to hit the lock
            kind = "update" if existing_summary else "new"
            return SummaryResult(content_md=f"# NET101 - Week 3\n\n## Overview\n\nA {kind}.\n")
        finally:
            self.active -= 1


@pytest_asyncio.fixture(loop_scope="session")
async def owner():
    uid = generate_id()
    async with async_session_factory() as session:
        session.add(
            User(
                id=uid,
                email=f"lock-{uid[-10:]}@example.com",
                username=f"lock_{uid[-10:]}",
                role="user",
                tier="pro",
                is_active=True,
                email_verified=True,
                mfa_enabled=False,
            )
        )
        await session.commit()
    yield uid
    async with async_session_factory() as session:
        await account_service.delete_user_account(session, uid)
        await session.commit()


@pytest.fixture
def gated(monkeypatch):
    agent = _GatedAgent()
    for target in ("app.pipeline.classify.get_agent", "app.pipeline.summarize.get_agent"):
        monkeypatch.setattr(target, lambda *a, **k: agent)
    monkeypatch.setattr(summarize_stage, "LOCK_POLL_SECONDS", 0.05)
    return agent


async def _prepared(owner: str, name: str, lines: list[str]) -> str:
    content = make_pdf(lines)
    async with async_session_factory() as session:
        artifact = await artifact_service.create_upload_artifact(
            session,
            content=content,
            original_filename=name,
            sha256=hashlib.sha256(content).hexdigest(),
            user_id=owner,
        )
        artifact_id = artifact.id
    await _classify(artifact_id, user_id=owner)
    await _extract(artifact_id, user_id=owner)
    return artifact_id


async def test_concurrent_summarize_same_week_serialises_and_keeps_every_version(owner, gated):
    first = await _prepared(owner, "net-w3-a.pdf", ["Lecture A"])
    second = await _prepared(owner, "net-w3-b.pdf", ["Lecture B"])

    results = await asyncio.gather(
        _summarize(first, user_id=owner), _summarize(second, user_id=owner)
    )

    # The agent calls never overlapped: the second waited for the first.
    assert gated.max_active == 1
    # Both succeeded with distinct, contiguous versions (none lost or duplicated).
    assert sorted(r["version"] for r in results) == [1, 2]
    # The run that waited saw the winner's committed summary.
    assert sum(1 for s in gated.seen_existing if s is None) == 1
    assert sum(1 for s in gated.seen_existing if s is not None) == 1

    async with async_session_factory() as session:
        rows = (
            (await session.execute(select(Summary).join(Course).where(Course.user_id == owner)))
            .scalars()
            .all()
        )
    assert len(rows) == 1 and rows[0].version == 2
    assert set(rows[0].source_artifacts) == {first, second}
    # Each version wrote its own blob; the prior one was not overwritten.
    assert len({r["file_path"] for r in results}) == 2


async def test_week_lock_is_exclusive_per_key_and_released_on_exit(monkeypatch):
    monkeypatch.setattr(summarize_stage, "LOCK_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(summarize_stage, "LOCK_POLL_SECONDS", 0.05)
    uid, cid = generate_id(), generate_id()

    async with _week_lock(uid, cid, 3):
        # The same key on another connection cannot get in ...
        with pytest.raises(StageBusyError):
            async with _week_lock(uid, cid, 3):
                pytest.fail("lock was not exclusive")
        # ... a different week is independent.
        async with _week_lock(uid, cid, 4):
            pass

    # Released on exit: immediately re-acquirable.
    async with _week_lock(uid, cid, 3):
        pass

    # And nothing is left held by this app's pool.
    async with engine.connect() as conn:
        held = (
            await conn.execute(
                text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted")
            )
        ).scalar_one()
    assert held == 0
