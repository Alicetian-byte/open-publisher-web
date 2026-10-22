"""add user ownership to core resources

Revision ID: 0010_user_ownership
Revises: 0009_email_login_revert
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0010_user_ownership"
down_revision = "0009_email_login_revert"
branch_labels = None
depends_on = None


_TARGETS = [
    ("articles", "ix_articles_owner_user_id"),
    ("article_templates", "ix_article_templates_owner_user_id"),
    ("media_assets", "ix_media_assets_owner_user_id"),
    ("agent_runs", "ix_agent_runs_owner_user_id"),
    ("publish_plans", "ix_publish_plans_owner_user_id"),
    ("model_profiles", "ix_model_profiles_owner_user_id"),
]


def upgrade() -> None:
    for table, index_name in _TARGETS:
        op.add_column(
            table,
            sa.Column("owner_user_id", sa.String(length=64), nullable=True),
        )
        op.create_index(index_name, table, ["owner_user_id"])


def downgrade() -> None:
    for table, index_name in _TARGETS:
        op.drop_index(index_name, table_name=table)
        op.drop_column(table, "owner_user_id")
