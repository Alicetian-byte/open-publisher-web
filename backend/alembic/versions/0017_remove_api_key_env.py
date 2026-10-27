"""remove api_key_env legacy columns

Revision ID: 0017_remove_api_key_env
Revises: 0016_workspace_preferences
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_remove_api_key_env"
down_revision = "0016_workspace_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("model_profiles", "api_key_env")
    op.drop_column("image_configs", "api_key_env")


def downgrade() -> None:
    op.add_column(
        "model_profiles",
        sa.Column(
            "api_key_env",
            sa.String(length=120),
            nullable=False,
            server_default="LLM_API_KEY",
        ),
    )
    op.add_column(
        "image_configs",
        sa.Column(
            "api_key_env",
            sa.String(length=120),
            nullable=False,
            server_default="IMAGE_API_KEY",
        ),
    )
