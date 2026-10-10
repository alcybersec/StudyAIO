"""Backfill opt-out notification defaults for untouched users (GL#15)

Revision ID: b7d1f4a82c35
Revises: a5c9e3d71b04
Create Date: 2026-10-10

User ruling (decisions.md 2026-10-10): existing users who never changed their
notification preferences get the new opt-out defaults; anyone who changed a
preference is left as is.

For every active user:

* no preference rows -> insert the full seed (3 channels x 6 events), with the
  DEFAULT_ENABLED email rows on and the rest off;
* rows exist, all disabled, and none ever updated -> switch the DEFAULT_ENABLED
  email rows on;
* anything else -> untouched.

"Untouched" means ``updated_at - created_at < 1 second``: the model fills the
two columns from separate ``datetime.now`` defaults (a few microseconds apart
on seed) and ``onupdate`` moves ``updated_at`` on any real toggle.

The constants are inlined by value; the source of truth is
``app.services.notification_service`` (CHANNELS, EVENT_TYPES, DEFAULT_ENABLED).
Migrations must not import app code that can change later.

Idempotent: a second run finds every such user already having an enabled row
(or touched rows) and changes nothing. Nothing is deleted.

Downgrade is a no-op: the prior state of a backfilled user cannot be told apart
from a user who later opted in, and disabling would destroy a real choice.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7d1f4a82c35"
down_revision = "a5c9e3d71b04"
branch_labels = None
depends_on = None

# Mirrors notification_service.CHANNELS / EVENT_TYPES / DEFAULT_ENABLED.
CHANNELS = ("email", "telegram", "push")
EVENT_TYPES = (
    "pipeline_complete",
    "review_created",
    "cards_due",
    "exam_reminder",
    "weekly_digest",
    "study_nudge",
)
DEFAULT_ENABLED_EVENTS = ("cards_due", "exam_reminder", "weekly_digest", "study_nudge")
DEFAULT_ENABLED_CHANNEL = "email"


def upgrade() -> None:
    """Seed users without rows; enable defaults for users who never changed any."""
    bind = op.get_bind()

    # 1. Active users with no rows at all: insert the full seed. The NOT EXISTS
    # check would see rows inserted by earlier loop iterations, so snapshot the
    # row-less users first.
    bind.execute(
        sa.text(
            "CREATE TEMP TABLE _pref_backfill_users ON COMMIT DROP AS "
            "SELECT u.id FROM users u WHERE u.is_active AND NOT EXISTS ("
            "SELECT 1 FROM notification_preferences p WHERE p.user_id = u.id)"
        )
    )
    for channel in CHANNELS:
        for event in EVENT_TYPES:
            enabled = channel == DEFAULT_ENABLED_CHANNEL and event in DEFAULT_ENABLED_EVENTS
            bind.execute(
                sa.text(
                    "INSERT INTO notification_preferences "
                    "(id, user_id, channel, event_type, enabled, created_at, updated_at) "
                    "SELECT gen_random_uuid()::text, id, :channel, :event, :enabled, "
                    "now(), now() FROM _pref_backfill_users"
                ),
                {"channel": channel, "event": event, "enabled": enabled},
            )

    # 2. Active users whose rows are all disabled and never updated. Users just
    # seeded above already have the defaults on, so they fail the "all disabled"
    # test and are skipped.
    bind.execute(
        sa.text(
            "UPDATE notification_preferences SET enabled = true "
            "WHERE channel = :channel AND event_type = ANY(:events) AND user_id IN ("
            "SELECT u.id FROM users u WHERE u.is_active "
            "AND EXISTS (SELECT 1 FROM notification_preferences p WHERE p.user_id = u.id) "
            "AND NOT EXISTS (SELECT 1 FROM notification_preferences p WHERE p.user_id = u.id "
            "AND (p.enabled OR p.updated_at - p.created_at >= interval '1 second')))"
        ),
        {"channel": DEFAULT_ENABLED_CHANNEL, "events": list(DEFAULT_ENABLED_EVENTS)},
    )


def downgrade() -> None:
    """No-op: prior state is unknowable and reverting could erase a real opt-in."""
