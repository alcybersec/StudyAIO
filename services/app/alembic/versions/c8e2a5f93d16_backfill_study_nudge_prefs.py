"""Backfill the missing study_nudge preference rows (GL#15)

Revision ID: c8e2a5f93d16
Revises: b7d1f4a82c35
Create Date: 2026-10-10

b7d1f4a82c35 seeded users with no preference rows and switched on defaults for
untouched users, but ``study_nudge`` is a new event type: a user who already had
rows never got a ``study_nudge`` row, so the nudge could not reach them and the
settings page showed it inconsistently.

For every active user (except the placeholder system user) who has preference
rows, insert each missing ``(channel, study_nudge)`` row:

* enabled for ``email`` only when the user never changed a preference, i.e. no
  existing row has ``updated_at - created_at >= 1 second`` (same rule as
  b7d1f4a82c35; a real toggle moves ``updated_at`` through ``onupdate``);
  enabled-ness is deliberately not tested, because b7d1f4a82c35's raw UPDATE
  switched default rows on without touching ``updated_at``;
* disabled for every other channel, and for all channels when the user changed
  anything (user ruling, decisions.md 2026-10-10: opt-out defaults for the
  untouched, changers left alone).

Users with no rows at all are out of scope (b7d1f4a82c35 seeded them, and a
brand-new user is seeded by the service). Only missing rows are inserted, so
existing rows are never modified and a re-run is a no-op; the unique constraint
on (user_id, channel, event_type) is respected via ON CONFLICT DO NOTHING.
Nothing is deleted.

Constants are inlined by value; the source of truth is
``app.services.notification_service`` (CHANNELS, DEFAULT_ENABLED).

Downgrade is a no-op: the inserted rows cannot be told apart from rows a user
created or toggled afterwards, and deleting them could erase a real choice.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e2a5f93d16"
down_revision = "b7d1f4a82c35"
branch_labels = None
depends_on = None

# Mirrors notification_service.CHANNELS / DEFAULT_ENABLED.
CHANNELS = ("email", "telegram", "push")
EVENT_TYPE = "study_nudge"
DEFAULT_ENABLED_CHANNEL = "email"
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Insert missing study_nudge rows for users who already have preference rows."""
    bind = op.get_bind()
    for channel in CHANNELS:
        bind.execute(
            sa.text(
                "INSERT INTO notification_preferences "
                "(id, user_id, channel, event_type, enabled, created_at, updated_at) "
                "SELECT gen_random_uuid()::text, u.id, CAST(:channel AS varchar), CAST(:event AS varchar), "
                "(CAST(:default_on AS boolean) AND NOT EXISTS ("
                "SELECT 1 FROM notification_preferences t "
                "WHERE t.user_id = u.id AND t.updated_at - t.created_at >= interval '1 second')), "
                "now(), now() FROM users u "
                "WHERE u.is_active AND u.id <> :system_user "
                "AND EXISTS (SELECT 1 FROM notification_preferences p WHERE p.user_id = u.id) "
                "AND NOT EXISTS (SELECT 1 FROM notification_preferences m "
                "WHERE m.user_id = u.id AND m.channel = CAST(:channel AS varchar) "
                "AND m.event_type = CAST(:event AS varchar)) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "channel": channel,
                "event": EVENT_TYPE,
                "default_on": channel == DEFAULT_ENABLED_CHANNEL,
                "system_user": SYSTEM_USER_ID,
            },
        )


def downgrade() -> None:
    """No-op: inserted rows are indistinguishable from later user choices."""
