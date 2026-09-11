"""`chunks.stable_id` must be scoped to the artifact, not to the file's hash (#85).

`chunks.stable_id` carries a global UNIQUE, and the id used to be
`f"{sha256[:8]}_p{page}_c{idx}"` -- derived only from file content. Two users
who upload the same lecture deck therefore produced byte-identical stable ids,
and the second one's `index` stage died on `chunks_stable_id_key`. #80 is what
made that reachable: before it, the second upload was rejected at ingest and
the pipeline never ran.

Why this suite and not `tests/unit`
-----------------------------------
The collision is a database constraint firing. `tests/unit` has no database --
it tests `_build_stable_id` in isolation, and before this fix it asserted the
*broken* shape was correct, which is exactly what the issue predicted would
happen. Those format assertions are still the right thing to keep (they live
in `tests/unit/services/test_index_service.py`, now pointed at the artifact-
scoped shape); what only a real Postgres can answer is whether two users'
chunks can coexist in one `chunks` table.

The shape follows `test_idor_row_level.py:TestArtifactDigestUniquenessIsPerUser`
-- behaviour plus a schema assertion, so the green cannot be an accident -- with
one deliberate difference. #80 was fixed by *dropping* a constraint, so its
schema assertion says `lecture_artifacts_sha256_key` is gone. #85 is fixed in
code only: `chunks_stable_id_key` is still there and must stay there, because
an artifact id is a UUID and the new shape satisfies the global rule on its own.
So the schema assertion here says the constraint is still **present**, and the
behavioural one says the two users' ids are **disjoint**.

No migration, deliberately
--------------------------
`stable_id` is write-only across the tree: it is written by
`index_artifact_chunks` and read by nothing -- search selects
`id/text/page_ref/slide_title/artifact_id` and the embedding distance, deletes
are artifact-scoped, and there is no conflict target anywhere. Old hash-shaped
rows and new artifact-shaped rows can sit in the same table forever, so the fix
ships without rewriting any data. `test_an_old_shaped_row_reindexes_cleanly`
is what holds that claim to account.

What these tests deliberately do not cover
------------------------------------------
They call `index_service.index_artifact_chunks` directly, so the failure they
see pre-fix is a raw `IntegrityError`. Driven through `app/pipeline/index.py`
the same collision surfaces differently, and worse: its `except` handler calls
`session.commit()` on a session the failed flush has already marked for
rollback, so `PendingRollbackError` replaces the `IndexingError` -- the
artifact is left stuck at `"indexing"` rather than `"failed"`, the
`pipeline_runs` failure row is rolled back, and the task retries despite the
explicit intent not to. Confirmed against a real session while fixing #85;
that handler is a separate bug, tracked separately, and survives this fix.
"""

import hashlib

import pytest
import sqlalchemy

from app.agents.embeddings import EmbeddingProvider
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.user import User
from app.services import index_service

SECOND_USER_ID = "00000000-0000-0000-0000-0000000000c5"

# The same file, uploaded by both users. #80 made this legal at ingest.
SHARED_BYTES = b"the week 1 lecture deck the whole cohort downloaded"
SHARED_SHA256 = hashlib.sha256(SHARED_BYTES).hexdigest()

PAGES = [
    {"page_number": 1, "text": "Transport layer basics and flow control.", "slide_title": "L1"},
    {"page_number": 2, "text": "Congestion control and retransmission.", "slide_title": "L2"},
]


class _FixedEmbeddings(EmbeddingProvider):
    """A provider with no model behind it -- this suite is about ids, not vectors."""

    @property
    def dimensions(self) -> int:
        return 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]

    def preload(self) -> None:
        return None


async def _second_user(db_session) -> str:
    """A second real user, rolled back with the test's SAVEPOINT."""
    db_session.add(
        User(
            id=SECOND_USER_ID,
            email="second-uploader@test.local",
            username="second_uploader",
            role="user",
            tier="free",
            is_active=True,
            email_verified=False,
            mfa_enabled=False,
        )
    )
    await db_session.flush()
    return SECOND_USER_ID


async def _artifact(db_session, user_id: str) -> LectureArtifact:
    """One user's copy of the shared file. Same digest for both owners."""
    artifact = LectureArtifact(
        id=generate_id(),
        user_id=user_id,
        original_filename="week1.pdf",
        file_path=f"/data/uploads/{user_id}/week1.pdf",
        file_type="pdf",
        sha256=SHARED_SHA256,
        file_size_bytes=len(SHARED_BYTES),
        status="ingested",
    )
    db_session.add(artifact)
    await db_session.flush()
    return artifact


async def _index(db_session, artifact: LectureArtifact) -> list[Chunk]:
    """Run the index stage's real service against the real database."""
    return await index_service.index_artifact_chunks(
        session=db_session,
        artifact_id=artifact.id,
        pages=PAGES,
        embedding_provider=_FixedEmbeddings(),
    )


async def _stable_ids(db_session, artifact_id: str) -> set[str]:
    rows = await db_session.execute(
        sqlalchemy.select(Chunk.stable_id).where(Chunk.artifact_id == artifact_id)
    )
    return set(rows.scalars())


async def _row_ids(db_session, artifact_id: str) -> set[str]:
    rows = await db_session.execute(
        sqlalchemy.select(Chunk.id).where(Chunk.artifact_id == artifact_id)
    )
    return set(rows.scalars())


@pytest.mark.asyncio(loop_scope="session")
class TestChunkStableIdIsArtifactScoped:
    """Two users, one file, and the index stage has to survive it."""

    async def test_two_users_can_index_the_same_file(self, db_session, test_user_id):
        """Both artifacts index, and neither user's stable ids touch the other's.

        Verified by reverting `index_service`: pre-fix this raises
        `IntegrityError: duplicate key value violates unique constraint
        "chunks_stable_id_key"` on the second `_index`, because the two
        artifacts are the same file and so shared a sha256 prefix, producing
        `<prefix>_p1_c0` twice.
        """
        second_user_id = await _second_user(db_session)

        first = await _artifact(db_session, test_user_id)
        second = await _artifact(db_session, second_user_id)
        assert first.sha256 == second.sha256, "the premise: it is the same file"

        first_chunks = await _index(db_session, first)
        second_chunks = await _index(db_session, second)
        assert first_chunks and second_chunks

        first_ids = await _stable_ids(db_session, first.id)
        second_ids = await _stable_ids(db_session, second.id)

        assert first_ids and second_ids
        assert first_ids.isdisjoint(second_ids), (
            "the two users' chunks share a stable_id, so the id is still derived "
            f"from something they have in common: {sorted(first_ids & second_ids)}"
        )
        assert all(sid.startswith(f"{first.id}_") for sid in first_ids)
        assert all(sid.startswith(f"{second.id}_") for sid in second_ids)

    async def test_the_global_constraint_is_still_there(self, db_session):
        """Name the constraint, so the test above cannot pass for the wrong reason.

        #85 is fixed in code, not by relaxing the schema -- the opposite of
        #80. If someone later drops `chunks_stable_id_key` as well, the
        behavioural test above keeps passing while the invariant quietly stops
        being enforced, so assert on `pg_constraint` directly.

        Note the model declares the rule twice: `unique=True` on the column
        (`chunk.py:22`) *and* `Index("ix_chunks_stable_id", unique=True)`
        (`chunk.py:35`). That double declaration is how `lecture_artifacts`
        drifted in #80; if `chunks` is ever relaxed, both have to go together.
        """
        rows = await db_session.execute(
            sqlalchemy.text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'chunks'::regclass AND contype = 'u'"
            )
        )
        names = {r[0] for r in rows}
        assert "chunks_stable_id_key" in names, (
            "the global UNIQUE(stable_id) is gone from the migrated schema. #85 "
            "was fixed by scoping the id to the artifact, not by dropping this "
            f"constraint -- the new id shape is meant to satisfy it. Found: {sorted(names)}"
        )

    async def test_reindexing_one_artifact_leaves_the_others_chunks_alone(
        self, db_session, test_user_id
    ):
        """Idempotency is `delete(Chunk).where(artifact_id == ...)`, and must stay scoped.

        The upsert never used `stable_id` as a conflict target, so the global
        uniqueness bought nothing in exchange for breaking the second uploader.
        This pins the mechanism that *does* do the work: re-running the stage
        replaces one artifact's rows and no others.
        """
        second_user_id = await _second_user(db_session)
        first = await _artifact(db_session, test_user_id)
        second = await _artifact(db_session, second_user_id)

        await _index(db_session, first)
        await _index(db_session, second)
        second_rows_before = await _row_ids(db_session, second.id)
        second_ids_before = await _stable_ids(db_session, second.id)
        assert second_rows_before

        await _index(db_session, first)

        assert await _stable_ids(db_session, second.id) == second_ids_before
        assert await _row_ids(db_session, second.id) == second_rows_before, (
            "re-indexing one artifact replaced another artifact's chunk rows, so "
            "the delete is no longer artifact-scoped"
        )

    async def test_an_old_shaped_row_reindexes_cleanly(self, db_session, test_user_id):
        """No data migration: a pre-fix row coexists, then is replaced in place.

        The claim being pinned is that old `<sha256[:8]>_p<page>_c<idx>` rows
        need no rewriting. An 8-hex prefix cannot collide with a 36-char UUID,
        so a legacy row does not block a new artifact from indexing; and when
        its own artifact is re-indexed, the artifact-scoped delete clears it
        without anyone having touched the database by hand.
        """
        second_user_id = await _second_user(db_session)
        legacy = await _artifact(db_session, test_user_id)
        fresh = await _artifact(db_session, second_user_id)

        # Exactly what the pre-fix code would have written for this file.
        old_shape = f"{SHARED_SHA256[:8]}_p1_c0"
        db_session.add(
            Chunk(
                id=generate_id(),
                artifact_id=legacy.id,
                stable_id=old_shape,
                text="written before #85 was fixed",
                page_ref=1,
            )
        )
        await db_session.flush()

        # A new artifact indexes while the legacy row is still sitting there.
        await _index(db_session, fresh)
        assert old_shape in await _stable_ids(db_session, legacy.id)

        # And re-indexing the legacy artifact replaces it, no migration needed.
        await _index(db_session, legacy)
        legacy_ids = await _stable_ids(db_session, legacy.id)
        assert old_shape not in legacy_ids
        assert legacy_ids and all(sid.startswith(f"{legacy.id}_") for sid in legacy_ids)
        assert legacy_ids.isdisjoint(await _stable_ids(db_session, fresh.id))
