"""Re-key summaries.file_path on the course id instead of the course code.

`summary_service.build_summary_storage_key` used to build
`summaries/<CODE>/<CODE>_Week<N>.md`, and `pipeline/summarize.py` stored that
string on the row. Course codes are unique only per user
(`uq_courses_code_user`), so two users who both take `CSIT302` produced the
*same* key: the second pipeline run overwrote the first user's file, and both
`summaries` rows then pointed at the survivor. Nothing raised; the rows were
individually correct and `content_md` was right on both (issue #92).

This revision rewrites `file_path` to the new shape,
`summaries/<course_id>/Week<N>.md`. `courses.id` is a per-user primary key, so
the collision cannot recur, and it survives a rename, which a code-shaped key
does not.

What this revision does **not** do is touch storage. A migration runs wherever
alembic runs, which is not necessarily where the blobs are (S3, a volume
mounted only into the app container), and the old file cannot simply be moved
anyway: where two users collided it holds one of them's content, so copying it
to both new keys would be the disclosure this issue is about.
`scripts/backfill_summary_files.py` does the file half, writing each new file
from `summaries.content_md` -- the per-user, trustworthy copy -- and deleting
the old-shape files afterwards. It is idempotent and order-independent with
respect to this revision: both derive the same key from the same column.

Between this revision and that script, `file_path` names a file that is not
there yet. Nothing reads it: the UI renders `content_md` (`SummaryTab.tsx`,
`export_service`, `pipeline/assets.py`), and the only reader of the file is
`GET /api/files/summaries/...`, which nothing links to.

The revision id is random rather than the next letter pair in the older
sequence: two branches picked `d0e1f2g3h4i5` off `c9d0e1f2g3h4` independently
because the sequence made the next value obvious, and duplicate identifiers
are not two heads -- Alembic refuses to load the directory at all. This one
chains onto `d0e1f2g3h4i5` (the email normalisation from #91), which reached
`main` first.

The key shape is spelled out here rather than imported from
`summary_service`: a migration is pinned history and must keep meaning what it
meant on the day it ran, even after the builder changes again.

Revision ID: 6b2e9a4c71df
Revises: d0e1f2g3h4i5
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b2e9a4c71df"
down_revision: str | None = "d0e1f2g3h4i5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def new_file_path(course_id: str, week: int) -> str:
    """The post-#92 key: per-user by construction, rename-proof."""
    return f"summaries/{course_id}/Week{week}.md"


def legacy_file_path(course_code: str, week: int) -> str:
    """The pre-#92 key. Two users sharing a code share this string."""
    return f"summaries/{course_code}/{course_code}_Week{week}.md"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, course_id, week FROM summaries")).fetchall()
    for summary_id, course_id, week in rows:
        bind.execute(
            sa.text("UPDATE summaries SET file_path = :path WHERE id = :id"),
            {"path": new_file_path(course_id, week), "id": summary_id},
        )


def downgrade() -> None:
    """Restore the colliding shape.

    Two users who share a course code get the same `file_path` back, because
    that is what the old shape means. The files the backfill wrote are left
    where they are: `content_md` is unaffected either way, and deleting them
    on the way down would lose the only per-user copies on disk.

    The join is spelled out in one SELECT and the writes are per row, so the
    statements stay portable rather than Postgres-only.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT s.id, c.code, s.week FROM summaries s JOIN courses c ON c.id = s.course_id")
    ).fetchall()
    for summary_id, course_code, week in rows:
        bind.execute(
            sa.text("UPDATE summaries SET file_path = :path WHERE id = :id"),
            {"path": legacy_file_path(course_code, week), "id": summary_id},
        )
