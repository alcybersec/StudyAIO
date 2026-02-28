"""chunk_embedding_1536_to_384

Revision ID: a2b3c4d5e6f7
Revises: c73364432b98
Create Date: 2026-02-28 20:00:00.000000

Switch Chunk.embedding from Vector(1536) to Vector(384) to match
sentence-transformers all-MiniLM-L6-v2 output dimensions.
Existing embeddings are dropped (re-index required).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'c73364432b98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing embeddings (incompatible dimensions) and change column type
    op.execute("UPDATE chunks SET embedding = NULL")
    op.alter_column(
        'chunks',
        'embedding',
        existing_type=Vector(1536),
        type_=Vector(384),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE chunks SET embedding = NULL")
    op.alter_column(
        'chunks',
        'embedding',
        existing_type=Vector(384),
        type_=Vector(1536),
        existing_nullable=True,
    )
