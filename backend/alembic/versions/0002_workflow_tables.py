"""tweet workflow tables: tweet_runs, tweet_artifacts, tweet_revisions

Revision ID: 0002_workflow_tables
Revises: 0001_initial
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0002_workflow_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tweet_runs",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("project_id", mysql.CHAR(36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_node", sa.String(length=50), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_tweet_runs_project_id", "tweet_runs", ["project_id"])

    op.create_table(
        "tweet_artifacts",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("run_id", mysql.CHAR(36), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_tweet_artifacts_run_id", "tweet_artifacts", ["run_id"])

    op.create_table(
        "tweet_revisions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("project_id", mysql.CHAR(36), nullable=False),
        sa.Column("run_id", mysql.CHAR(36), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("tone", sa.String(length=50), nullable=True),
        sa.Column("score", mysql.DECIMAL(5, 2), nullable=True),
        sa.Column("risk_level", sa.String(length=10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("tweet_revisions")
    op.drop_table("tweet_artifacts")
    op.drop_table("tweet_runs")

