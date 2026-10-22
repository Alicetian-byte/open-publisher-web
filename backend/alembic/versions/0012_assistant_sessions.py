"""assistant sessions and messages

Revision ID: 0012_assistant_sessions
Revises: 0011_media_profiles
Create Date: 2026-10-20

"""
from alembic import op
import sqlalchemy as sa


revision = "0012_assistant_sessions"
down_revision = "0011_media_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_sessions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("article_id", sa.CHAR(36), nullable=True),
        sa.Column("owner_user_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("active_profile_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_assistant_sessions_article_id", "assistant_sessions", ["article_id"])
    op.create_index("ix_assistant_sessions_owner_user_id", "assistant_sessions", ["owner_user_id"])
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("session_id", sa.CHAR(36), sa.ForeignKey("assistant_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_assistant_messages_session_id", "assistant_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_sessions_owner_user_id", table_name="assistant_sessions")
    op.drop_index("ix_assistant_sessions_article_id", table_name="assistant_sessions")
    op.drop_table("assistant_sessions")
