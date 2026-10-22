"""media structured asset profiles

Revision ID: 0011_media_profiles
Revises: 0010_user_ownership
Create Date: 2026-10-20

"""
from alembic import op
import sqlalchemy as sa


revision = "0011_media_profiles"
down_revision = "0010_user_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("visual_description", sa.Text(), nullable=False),
    )
    op.add_column(
        "media_assets",
        sa.Column("generation_prompt", sa.Text(), nullable=False),
    )
    op.add_column(
        "media_assets",
        sa.Column("tags", sa.JSON(), nullable=True),
    )
    op.execute("UPDATE media_assets SET tags = CAST('[]' AS JSON) WHERE tags IS NULL")
    op.alter_column("media_assets", "tags", existing_type=sa.JSON(), nullable=False)
    op.add_column(
        "media_assets",
        sa.Column("description_source", sa.String(length=30), nullable=False, server_default="manual"),
    )


def downgrade() -> None:
    op.drop_column("media_assets", "description_source")
    op.drop_column("media_assets", "tags")
    op.drop_column("media_assets", "generation_prompt")
    op.drop_column("media_assets", "visual_description")
