"""project ownership column

Revision ID: 0014_project_ownership
Revises: 0013_image_config
Create Date: 2026-10-24

"""
from alembic import op
import sqlalchemy as sa


revision = "0014_project_ownership"
down_revision = "0013_image_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("owner_user_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_projects_owner_user_id", "projects", ["owner_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_column("projects", "owner_user_id")
