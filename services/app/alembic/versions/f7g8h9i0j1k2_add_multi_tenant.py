"""Add multi-tenant user_id FKs and user_settings table.

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-03-04 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "f7g8h9i0j1k2"
down_revision: str | None = "e6f7g8h9i0j1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default admin user for backfilling existing data
DEFAULT_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ADMIN_EMAIL = "admin@studyaio.local"
DEFAULT_ADMIN_USERNAME = "admin"


def upgrade() -> None:
    # ── 1. Create user_settings table ─────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("settings_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("dashboard_layout", JSONB, nullable=True),
        sa.Column("theme", sa.String(20), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 2. Add user_id columns as NULLABLE (safe for existing data) ───
    tables = [
        "courses",
        "lecture_artifacts",
        "exams",
        "study_sessions",
        "flashcard_reviews",
        "course_documents",
    ]
    for table in tables:
        op.add_column(table, sa.Column("user_id", sa.String(36), nullable=True))

    # ── 3. Create default admin user if none exists ───────────────────
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT id FROM users LIMIT 1")).fetchone()

    if existing:
        admin_id = existing[0]
    else:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, username, role, tier, is_active, "
                "email_verified, mfa_enabled, created_at, updated_at) "
                "VALUES (:id, :email, :username, 'admin', 'pro', true, "
                "true, false, now(), now())"
            ),
            {
                "id": DEFAULT_ADMIN_ID,
                "email": DEFAULT_ADMIN_EMAIL,
                "username": DEFAULT_ADMIN_USERNAME,
            },
        )
        admin_id = DEFAULT_ADMIN_ID

    # ── 4. Backfill: set all NULL user_id rows to admin ───────────────
    for table in tables:
        conn.execute(
            sa.text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": admin_id},
        )

    # ── 5. ALTER to NOT NULL + add FK constraints ─────────────────────
    for table in tables:
        op.alter_column(table, "user_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "users",
            ["user_id"],
            ["id"],
        )

    # ── 6. Replace unique constraints ─────────────────────────────────
    # courses: drop unique(code), add unique(code, user_id)
    op.drop_constraint("courses_code_key", "courses", type_="unique")
    op.create_unique_constraint("uq_courses_code_user", "courses", ["code", "user_id"])

    # lecture_artifacts: drop unique(sha256), add unique(sha256, user_id)
    op.drop_index("ix_lecture_artifacts_sha256", "lecture_artifacts")
    op.create_unique_constraint(
        "uq_artifacts_sha256_user", "lecture_artifacts", ["sha256", "user_id"]
    )
    op.create_index("ix_lecture_artifacts_sha256", "lecture_artifacts", ["sha256"])

    # ── 7. Add user_id indexes ────────────────────────────────────────
    for table in tables:
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    tables = [
        "courses",
        "lecture_artifacts",
        "exams",
        "study_sessions",
        "flashcard_reviews",
        "course_documents",
    ]

    # Drop user_id indexes
    for table in tables:
        op.drop_index(f"ix_{table}_user_id", table)

    # Restore original unique constraints
    op.drop_index("ix_lecture_artifacts_sha256", "lecture_artifacts")
    op.drop_constraint("uq_artifacts_sha256_user", "lecture_artifacts", type_="unique")
    op.create_index("ix_lecture_artifacts_sha256", "lecture_artifacts", ["sha256"], unique=True)

    op.drop_constraint("uq_courses_code_user", "courses", type_="unique")
    op.create_unique_constraint("courses_code_key", "courses", ["code"])

    # Drop FK constraints and columns
    for table in tables:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    # Drop user_settings table
    op.drop_table("user_settings")
