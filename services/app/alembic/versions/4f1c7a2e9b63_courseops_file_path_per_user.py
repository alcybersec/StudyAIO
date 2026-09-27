"""Re-key course_documents.file_path on the owning user.

`app/api/courseops.py` used to build `courseops/<sha256[:16]>_<name>`:
content-addressed, with no owner in the key. Two users who upload the same
course handbook -- realistic, since a handbook goes to a whole cohort -- wrote
to one blob.

Unlike #92, nothing was corrupted and nothing leaked. The key is derived from
the content hash, so the same key holds the same bytes. The defect is
*lifecycle*: `account_service.purge_user_storage` deliberately skipped
`courseops/` entirely, because deleting one user's copy would pull the file out
from under another user's still-live `CourseDocument` row. So closing an account
left its course documents on disk indefinitely -- the same class #97 fixed for
summaries, but one where the naive fix was worse than the gap (issue #107).

This revision rewrites `file_path` to `courseops/<user_id>/<sha256[:16]>_<name>`,
which the purge sweeps as one prefix per user like every other namespace.

Reference counting was considered and rejected: the deduplication it preserves
is worth very little here -- a handful of shared handbooks -- against a deletion
path that needs the count taken inside the deleting transaction, or two
concurrent account closures each see the other's reference and neither deletes.

**The new key is derived from the old one, not recomputed.** The basename
already contains `<sha256[:16]>_<sanitize_filename(name)>`, so prepending the
user id is exact; recomputing it here would mean reproducing
`core.utils.sanitize_filename` in a migration and keeping the two in step
forever. Rows are only rewritten when `file_path` has the legacy two-segment
shape, so re-running cannot double-nest. `sanitize_filename` strips everything
but alphanumerics and " ._-()", so a name can never contain a slash and the
segment count is an exact discriminator.

What this revision does **not** do is touch storage. A migration runs wherever
alembic runs, which is not necessarily where the blobs are (S3, a volume mounted
only into the app container). `scripts/backfill_courseops_files.py` does the
file half, and it **copies** rather than moves: a legacy blob may be referenced
by several users, and each needs its own copy under its own prefix. Copying is
safe here for exactly the reason the bug was benign -- content addressing means
every referrer wants those identical bytes. This is the inverse of #92, where
copying the colliding file to both new keys would have *been* the disclosure.

Between this revision and that script, `file_path` names a file that is not
there yet. The only reader is `GET /api/files/courseops/documents/{id}`, which
404s on a missing blob; the raw-path route refuses the `courseops` prefix
outright (#66), and `pipeline/courseops_task` reads the blob only during the
extraction that follows an upload, which writes the new shape directly.

The revision id is random rather than the next letter pair in the older
sequence: two branches once picked the same "obvious" next value, and duplicate
identifiers are not two heads -- Alembic refuses to load the directory at all.

Revision ID: 4f1c7a2e9b63
Revises: 6b2e9a4c71df
Create Date: 2026-09-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f1c7a2e9b63"
down_revision: str | None = "6b2e9a4c71df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Spelled out here rather than imported from `courseops_service`: a migration
#: is pinned history and must keep meaning what it meant on the day it ran,
#: even after the builder changes again.
PREFIX = "courseops"


def new_file_path(user_id: str, file_path: str) -> str:
    """Prepend the owner to a legacy two-segment courseops key.

    Anything else -- already migrated, or not a courseops key at all -- is
    returned unchanged, which is what makes this idempotent.
    """
    parts = file_path.split("/")
    if len(parts) == 2 and parts[0] == PREFIX:
        return f"{PREFIX}/{user_id}/{parts[1]}"
    return file_path


def legacy_file_path(user_id: str, file_path: str) -> str:
    """Strip the owner back out, restoring the shared shape."""
    parts = file_path.split("/")
    if len(parts) == 3 and parts[0] == PREFIX and parts[1] == user_id:
        return f"{PREFIX}/{parts[2]}"
    return file_path


def _rewrite(transform) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, user_id, file_path FROM course_documents")).fetchall()
    for doc_id, user_id, file_path in rows:
        if not file_path:
            continue
        updated = transform(user_id, file_path)
        if updated == file_path:
            continue
        bind.execute(
            sa.text("UPDATE course_documents SET file_path = :path WHERE id = :id"),
            {"path": updated, "id": doc_id},
        )


def upgrade() -> None:
    _rewrite(new_file_path)


def downgrade() -> None:
    """Restore the shared shape.

    Two users who uploaded the same file get the same `file_path` back, because
    that is what the old shape means. The per-user copies the backfill wrote are
    left on disk: deleting them on the way down would destroy the only copies
    that exist if the legacy blob has already been cleaned up.
    """
    _rewrite(legacy_file_path)
