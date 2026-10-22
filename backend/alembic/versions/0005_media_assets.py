"""media assets table

Revision ID: 0005_media_assets
Revises: 0004_article_templates
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0005_media_assets"
down_revision = "0004_article_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("alt", sa.String(length=500), nullable=False),
        sa.Column("usage_hint", sa.String(length=500), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("source", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("media_assets")
