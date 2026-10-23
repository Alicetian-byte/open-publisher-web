"""image config singleton table

Revision ID: 0013_image_config
Revises: 0012_assistant_sessions
Create Date: 2026-10-23

"""
from alembic import op
import sqlalchemy as sa


revision = "0013_image_config"
down_revision = "0012_assistant_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_configs",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("api_key_env", sa.String(length=120), nullable=False, server_default="IMAGE_API_KEY"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("image_configs")
