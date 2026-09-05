"""Drop the dead `embedding_backend` key from user settings.

`embedding_backend` was offered as a per-user setting: accepted by
`PUT /api/settings`, validated, stored in `user_settings.settings_json`, echoed
back by `GET /api/settings`, and rendered as a dropdown. Nothing per-user ever
read it. `get_embedding_provider()` is a process-wide singleton that resolves
the backend from `EMBEDDING_BACKEND` alone, so a stored override changed
nothing for anybody (issue #32).

**This migration therefore changes no behaviour.** It removes a key that did
nothing, from users who were already getting the instance's backend whatever
they had picked. It is hygiene: with the key gone from `ALLOWED_KEYS`, a stale
value left in `settings_json` is inert but would silently reactivate if the key
were ever re-added, and it would reactivate as a *stored user preference* that
predates the reason it was removed.

The setting itself is not going away — it stays instance-wide, set by the
operator through `EMBEDDING_BACKEND`. Only the per-user copy of it goes.

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-09-05 00:00:00.000000

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "z6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The key this revision removes. Migrations are pinned history, so the name is
#: spelled out here rather than imported from a module that no longer has it.
DEAD_KEY = "embedding_backend"


def strip_embedding_backend(data: dict[str, Any]) -> dict[str, Any] | None:
    """Remove the dead `embedding_backend` key from one user's settings.

    Args:
        data: The stored settings dict.

    Returns:
        The rewritten dict, or None when the key was not present and there is
        nothing to write.
    """
    if DEAD_KEY not in data:
        return None

    updated = dict(data)
    del updated[DEAD_KEY]
    return updated


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, settings_json FROM user_settings")).fetchall()

    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw or "{}")
        rewritten = strip_embedding_backend(data)
        if rewritten is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE user_settings SET settings_json = CAST(:payload AS jsonb) WHERE id = :id"
            ),
            {"payload": json.dumps(rewritten), "id": row_id},
        )


def downgrade() -> None:
    # Nothing to restore, and nothing that would want restoring. The key was
    # write-only in effect: no code path outside the settings API ever read a
    # user's copy of it, so every row behaved as if it held the instance's
    # `EMBEDDING_BACKEND` both before and after this revision. Re-inserting the
    # values would put back a preference that was never honoured.
    pass
