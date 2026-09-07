"""Drop the stale global UNIQUE(sha256) on lecture_artifacts.

`c73364432b98` created `lecture_artifacts` with a bare
`sa.UniqueConstraint("sha256")` -- Postgres named it
`lecture_artifacts_sha256_key` -- plus a unique index
`ix_lecture_artifacts_sha256`. That was correct for a single-tenant app.

`f7g8h9i0j1k2` made the app multi-tenant. For `courses` it did the swap
properly: `drop_constraint("courses_code_key")` then
`create_unique_constraint("uq_courses_code_user")`. For `lecture_artifacts`,
two lines further down, it dropped the *index* and added
`uq_artifacts_sha256_user` -- but never dropped the table-level constraint.
Both have been live at head ever since, and only the index half of the
single-tenant rule was ever removed (issue #80).

The effect is that the second user to upload a given file collides on
`lecture_artifacts_sha256_key`. For a study tool this is the normal case, not
an edge case: one lecturer's slide deck goes to a whole cohort, and everybody
after the first uploader is refused. The refusal is also a disclosure -- the
constraint fires precisely because *somebody else* already holds those exact
bytes.

`LectureArtifact.__table_args__` has only ever declared
`UniqueConstraint("sha256", "user_id")`, and `artifact_service.check_duplicate`
has only ever filtered on `(sha256, user_id)`. So the model and the application
already agree that the digest is unique per user; this revision is the schema
catching up to them, not a change of intent.

The non-unique `ix_lecture_artifacts_sha256` that `f7g8h9i0j1k2` left behind is
untouched, so digest lookups keep their index after the constraint's implicit
one goes away.

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-09-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2g3h4"
down_revision: str | None = "b8c9d0e1f2g3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Postgres' generated name for the `UniqueConstraint("sha256")` in
#: `c73364432b98`. Spelled out rather than derived: migrations are pinned
#: history, and this name is what is actually in the deployed database.
STALE_CONSTRAINT = "lecture_artifacts_sha256_key"


def upgrade() -> None:
    # IF EXISTS rather than a bare DROP CONSTRAINT: a database that was
    # repaired by hand before this revision landed is in exactly the state
    # this revision wants, and should not be turned into a failed upgrade.
    op.execute(
        sa.text(f"ALTER TABLE lecture_artifacts DROP CONSTRAINT IF EXISTS {STALE_CONSTRAINT}")
    )


def downgrade() -> None:
    # Deliberately a no-op, and not a reversible one.
    #
    # Once this revision has been live, `lecture_artifacts` may legitimately
    # hold the same sha256 under two different users -- that is the entire
    # point of it. Recreating a global UNIQUE over that data cannot succeed:
    # Postgres would fail building the implicit index, so a downgrade that
    # tried would abort partway rather than return the schema to its old
    # shape. Failing is the honest outcome only if the old shape were
    # recoverable, and it is not; the rows exist.
    #
    # Nothing is lost by leaving the looser constraint in place. The invariant
    # the application actually relies on is `uq_artifacts_sha256_user`, which
    # `f7g8h9i0j1k2` owns and this revision does not touch, so it survives a
    # downgrade intact and per-user dedup keeps working either way.
    #
    # Note that `f7g8h9i0j1k2.downgrade()` already has this same problem: it
    # recreates `ix_lecture_artifacts_sha256` as a unique index and would fail
    # on cross-user duplicates. Downgrading past that revision on a database
    # with real multi-tenant data is not a supported operation regardless of
    # this one.
    pass
