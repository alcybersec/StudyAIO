"""Add knowledge graph tables (concepts, concept_relations).

Revision ID: k1l2m3n4o5p6
Revises: i0j1k2l3m4n5
Create Date: 2026-03-05 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | None = "i0j1k2l3m4n5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- concepts --
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("source_artifact_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("source_weeks", JSONB, nullable=False, server_default="[]"),
        sa.Column("mention_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_concepts_user_id", "concepts", ["user_id"])
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"])
    op.create_index("ix_concepts_name", "concepts", ["name"])
    op.create_unique_constraint(
        "uq_concept_user_course_name", "concepts", ["user_id", "course_id", "name"]
    )

    # -- concept_relations --
    op.create_table(
        "concept_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_concept_id",
            sa.String(36),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_concept_id",
            sa.String(36),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column(
            "source_artifact_id",
            sa.String(36),
            sa.ForeignKey("lecture_artifacts.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_concept_relations_source", "concept_relations", ["source_concept_id"]
    )
    op.create_index(
        "ix_concept_relations_target", "concept_relations", ["target_concept_id"]
    )
    op.create_unique_constraint(
        "uq_concept_relation",
        "concept_relations",
        ["source_concept_id", "target_concept_id", "relation_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_concept_relations_target", table_name="concept_relations")
    op.drop_index("ix_concept_relations_source", table_name="concept_relations")
    op.drop_constraint("uq_concept_relation", "concept_relations", type_="unique")
    op.drop_table("concept_relations")

    op.drop_index("ix_concepts_name", table_name="concepts")
    op.drop_index("ix_concepts_course_id", table_name="concepts")
    op.drop_index("ix_concepts_user_id", table_name="concepts")
    op.drop_constraint("uq_concept_user_course_name", "concepts", type_="unique")
    op.drop_table("concepts")
