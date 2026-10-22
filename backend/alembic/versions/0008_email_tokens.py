"""email tokens table

Revision ID: 0008_email_tokens
Revises: 0007_auth_users
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0008_email_tokens"
down_revision = "0007_auth_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("app_users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.create_table(
        "email_tokens",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_email_tokens_user_purpose", "email_tokens", ["user_id", "purpose"])


def downgrade() -> None:
    op.drop_index("ix_email_tokens_user_purpose", table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_column("app_users", "email_verified_at")
    op.drop_column("app_users", "email_verified")
