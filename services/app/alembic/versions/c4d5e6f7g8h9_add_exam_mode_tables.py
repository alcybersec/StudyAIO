"""Add exam mode tables (exams, quiz_attempts, study_sessions).

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-03-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7g8h9"
down_revision: str | None = "b3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Exams table
    op.create_table(
        "exams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("exam_date", sa.DateTime(), nullable=False),
        sa.Column("weeks_scope", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("target_mastery_pct", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_exams_course_status", "exams", ["course_id", "status"])
    op.create_index("ix_exams_exam_date", "exams", ["exam_date"])

    # Quiz attempts table
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "quiz_question_id",
            sa.String(36),
            sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exam_id",
            sa.String(36),
            sa.ForeignKey("exams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selected_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("time_spent_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_quiz_attempts_question", "quiz_attempts", ["quiz_question_id"])
    op.create_index("ix_quiz_attempts_exam", "quiz_attempts", ["exam_id"])
    op.create_index("ix_quiz_attempts_created", "quiz_attempts", ["created_at"])

    # Study sessions table
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "exam_id",
            sa.String(36),
            sa.ForeignKey("exams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("cards_reviewed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_questions_answered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_study_sessions_date", "study_sessions", ["session_date"])
    op.create_index("ix_study_sessions_exam", "study_sessions", ["exam_id"])


def downgrade() -> None:
    op.drop_table("study_sessions")
    op.drop_table("quiz_attempts")
    op.drop_table("exams")
