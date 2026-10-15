"""Keep database connections out of provider calls (GL#50, audit TECH-07)."""

from sqlalchemy.ext.asyncio import AsyncSession


async def release_connection(session: AsyncSession, *, read_only: bool = False) -> None:
    """End the session's open transaction so its pooled connection is returned.

    Call this after the last read/flush of a stage's input phase and before any
    provider call (`get_agent(...).generate_*`, `embed_texts`): the call takes
    seconds to minutes and a transaction left open across it holds a Postgres
    connection idle-in-transaction the whole time. The session stays usable;
    SQLAlchemy checks a connection out again on the next statement, which is the
    "fresh transaction to persist" half of the pattern. Pending work (a
    `PipelineRun` flushed as ``running``, the ``summarizing`` status) is
    committed, which is also what lets the UI see it while the call runs.

    Committing, not rolling back: nothing pending here is speculative, and the
    session factory sets ``expire_on_commit=False`` so loaded rows stay readable.

    Args:
        session: The stage's session.
        read_only: The session only read since its last commit and nothing pending
            should be written (the re-embed path, which promises not to commit
            before its replacement rows exist): roll back instead of committing.
    """
    if read_only:
        await session.rollback()
    else:
        await session.commit()
