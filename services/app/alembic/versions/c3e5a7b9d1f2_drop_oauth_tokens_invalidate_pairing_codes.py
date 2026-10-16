"""Stop storing OAuth sign-in tokens; invalidate Telegram pairing codes.

M34-S2-SEC-013 (``models.secrets-at-rest v2``): sign-in never uses the provider
tokens, so ``oauth_accounts.access_token`` and ``refresh_token`` are set to NULL on
every row. No row is deleted and no other column changes; the columns stay (always
NULL) for one release.

M34-S2-SEC-014 (``models.telegram-pairing-code v1``): ``telegram_links.link_token``
now holds a SHA-256 digest of the pairing code. Existing codes are plaintext and never
expire, so every one is set to NULL (an unused code stops working; a used one is
already NULL). The downgrade does the same, because the old code compares plaintext
and a stored digest must not survive it.

Data only: Core ``UPDATE`` over ``sa.table``, no schema change. Prints counts only.

Downgrade: the nulled OAuth tokens cannot be restored; it changes nothing for them.

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e5a7b9d1f2"
down_revision: str | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OAUTH = sa.table(
    "oauth_accounts",
    sa.column("access_token", sa.Text),
    sa.column("refresh_token", sa.Text),
)
_TELEGRAM = sa.table("telegram_links", sa.column("link_token", sa.String))


def _null_pairing_codes(bind: sa.Connection) -> int:
    result = bind.execute(
        sa.update(_TELEGRAM).where(_TELEGRAM.c.link_token.is_not(None)).values(link_token=None)
    )
    return result.rowcount


def upgrade() -> None:
    bind = op.get_bind()
    oauth = bind.execute(
        sa.update(_OAUTH)
        .where(sa.or_(_OAUTH.c.access_token.is_not(None), _OAUTH.c.refresh_token.is_not(None)))
        .values(access_token=None, refresh_token=None)
    ).rowcount
    codes = _null_pairing_codes(bind)
    print(
        f"oauth_accounts: tokens nulled on {oauth} rows; telegram_links: {codes} codes invalidated"
    )


def downgrade() -> None:
    codes = _null_pairing_codes(op.get_bind())
    print(
        "oauth_accounts: nothing restored (the tokens cannot be restored); "
        f"telegram_links: {codes} codes invalidated"
    )
