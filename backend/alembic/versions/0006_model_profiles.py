"""model profiles table

Revision ID: 0006_model_profiles
Revises: 0005_media_assets
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_model_profiles"
down_revision = "0005_media_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_profiles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="custom"),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("api_key_env", sa.String(length=120), nullable=False, server_default="LLM_API_KEY"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_profiles")
