"""article templates table

Revision ID: 0004_article_templates
Revises: 0003_blueprint_runtime
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0004_article_templates"
down_revision = "0003_blueprint_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_templates",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("style_profile", sa.JSON(), nullable=False),
        sa.Column("structure_profile", sa.JSON(), nullable=False),
        sa.Column("layout_profile", sa.JSON(), nullable=False),
        sa.Column("fixed_blocks", sa.JSON(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("usage_instructions", sa.Text(), nullable=False),
        sa.Column("is_built_in", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("reference_markdown", sa.Text(), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("article_templates")
