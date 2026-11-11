"""Local embeddings: 768-dim vectors, HNSW index, per-source embedding status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

embedding_status = postgresql.ENUM("pending", "done", name="embedding_status", create_type=False)


def upgrade() -> None:
    # No embeddings were ever written at 1536 dims, so the column can be recreated.
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(768), nullable=True))
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)"
    )

    embedding_status.create(op.get_bind(), checkfirst=True)
    op.add_column("sources", sa.Column("embedding_status", embedding_status, nullable=True))
    op.add_column(
        "sources", sa.Column("embedding_attempted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE sources SET embedding_status = 'pending' WHERE status = 'ready'")
    op.create_index(
        "ix_sources_embedding_pending",
        "sources",
        ["embedding_attempted_at"],
        postgresql_where=sa.text("embedding_status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_sources_embedding_pending", table_name="sources")
    op.drop_column("sources", "embedding_attempted_at")
    op.drop_column("sources", "embedding_status")
    embedding_status.drop(op.get_bind(), checkfirst=True)
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding")
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(1536), nullable=True))
