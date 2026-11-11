"""Chat history tables for Ask sessions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

chat_role = postgresql.ENUM("user", "assistant", name="chat_role", create_type=False)


def upgrade() -> None:
    chat_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_sessions_updated", "chat_sessions", ["updated_at"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", chat_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("passages", postgresql.JSONB(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("notice", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_updated", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    chat_role.drop(op.get_bind(), checkfirst=True)
