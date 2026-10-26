"""app secrets: encrypted key storage + audit

Revision ID: 0015_app_secrets
Revises: 0014_project_ownership
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa


revision = "0015_app_secrets"
down_revision = "0014_project_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_secrets",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "app_secret_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("secret_id", sa.String(length=120), nullable=False, index=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_secret_audit")
    op.drop_table("app_secrets")
