"""Default existing users to the "StudyAIO provided" backend.

Before this, `user_settings.settings_json.agent_backend` selected a provider
while the credentials came from the instance configuration — so a selection a
user never backed with a key of their own still spent the operator's key, and
`GET /api/settings` handed that key back (issue #30).

The new model splits the two: `studyaio` means "the instance's provider and
credentials", and every other value means "my own provider, my own
credential". Rows are rewritten to preserve today's *behaviour* under the new
meaning:

* a backend selected with no personal credential for it becomes `studyaio` —
  those users were on the instance's key all along, and the agent factory now
  refuses a credential-less selection rather than falling back;
* a backend backed by the user's own credential is left exactly as it is;
* an unrecognised backend becomes `studyaio`.

Stale credential material is dropped while the rows are open, because it is
now dead weight that can only ever leak: empty credential strings, expired
Claude CLI OAuth blobs (a refresh token nobody has used since it expired), and
unparseable ones. Downgrade cannot restore them and does not try.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-09-05 00:00:00.000000

"""

import json
import time
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "z6a7b8c9d0e1"
down_revision: str | None = "y5z6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


STUDYAIO_BACKEND = "studyaio"

#: Mirrors settings_service.SECRET_KEYS at the time of this revision. Migrations
#: are pinned history, so this is copied rather than imported.
SECRET_KEYS = (
    "anthropic_api_key",
    "openai_api_key",
    "zai_api_key",
    "claude_cli_credentials",
)

#: Mirrors settings_service.BACKEND_REQUIRED_KEY at the time of this revision.
BACKEND_REQUIRED_KEY = {
    "claude_code": "claude_cli_credentials",
    "anthropic_api": "anthropic_api_key",
    "openai": "openai_api_key",
    "zai": "zai_api_key",
    "ollama": "ollama_base_url",
}


def _cli_credentials_are_dead(raw: Any) -> bool:
    """Whether a stored Claude CLI credential blob is unusable.

    Args:
        raw: The stored `claude_cli_credentials` string.

    Returns:
        True if it cannot be parsed, carries no tokens, or has expired.
    """
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return True
    if not isinstance(parsed, dict):
        return True

    oauth = parsed.get("claudeAiOauth") or {}
    if not oauth.get("accessToken") or not oauth.get("refreshToken"):
        return True

    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, int | float) and expires_at > 0:
        # Claude CLI stores expiry as epoch milliseconds.
        return expires_at / 1000 < time.time()
    return False


def rewrite_settings(data: dict[str, Any]) -> dict[str, Any] | None:
    """Rewrite one user's `settings_json` for the new provider model.

    Args:
        data: The stored settings dict.

    Returns:
        The rewritten dict, or None when nothing needs to change.
    """
    updated = dict(data)
    changed = False

    for key in SECRET_KEYS:
        if key in updated and not str(updated[key] or "").strip():
            del updated[key]
            changed = True

    if "claude_cli_credentials" in updated and _cli_credentials_are_dead(
        updated["claude_cli_credentials"]
    ):
        del updated["claude_cli_credentials"]
        changed = True

    backend = updated.get("agent_backend")
    if backend and backend != STUDYAIO_BACKEND:
        required = BACKEND_REQUIRED_KEY.get(backend)
        if required is None or not str(updated.get(required) or "").strip():
            updated["agent_backend"] = STUDYAIO_BACKEND
            changed = True

    return updated if changed else None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, settings_json FROM user_settings")).fetchall()

    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw or "{}")
        rewritten = rewrite_settings(data)
        if rewritten is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE user_settings SET settings_json = CAST(:payload AS jsonb) WHERE id = :id"
            ),
            {"payload": json.dumps(rewritten), "id": row_id},
        )


def downgrade() -> None:
    # Nothing to restore. `studyaio` was the effective behaviour of every row
    # this touched, and the credentials it dropped were empty or expired —
    # they cannot be reconstructed and were unusable anyway. The pre-migration
    # code reads an unknown `agent_backend` as its default, so rows left
    # saying `studyaio` behave there exactly as they did before.
    pass
