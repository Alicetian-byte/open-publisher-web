"""blueprint runtime tables: articles, agent runtime, publish outbox

把蓝本 agent-runtime 的 SQLite schema（MIGRATION_V1 + MIGRATION_V2）与
文件版 ArticleStore 收敛为 MySQL 表。

Revision ID: 0003_blueprint_runtime
Revises: 0002_workflow_tables
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0003_blueprint_runtime"
down_revision = "0002_workflow_tables"
branch_labels = None
depends_on = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    # --- 蓝本文件版 ArticleStore → 数据库版 ---
    op.create_table(
        "articles",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("current_revision_id", mysql.CHAR(36), nullable=True),
        sa.Column("content_hash", sa.String(length=80), nullable=True),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=_NOW,
            onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_table(
        "article_revisions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("article_id", mysql.CHAR(36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", mysql.CHAR(36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_article_revisions_article_id", "article_revisions", ["article_id"])

    # --- 蓝本 MIGRATION_V1：agent 运行日志 ---
    op.create_table(
        "agent_sessions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("article_id", mysql.CHAR(36), nullable=True),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_sessions_article_id", "agent_sessions", ["article_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("article_id", mysql.CHAR(36), nullable=True),
        sa.Column("session_id", mysql.CHAR(36), nullable=True),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("base_revision_id", mysql.CHAR(36), nullable=True),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_runs_article_id", "agent_runs", ["article_id"])

    op.create_table(
        "agent_run_events",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("run_id", mysql.CHAR(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_run_events_run_seq"),
    )
    op.create_index("ix_agent_run_events_run_id", "agent_run_events", ["run_id", "sequence"])

    op.create_table(
        "tool_executions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("run_id", mysql.CHAR(36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tool_executions_run_id", "tool_executions", ["run_id"])

    # --- 蓝本 MIGRATION_V2：发布 outbox ---
    op.create_table(
        "publish_plans",
        sa.Column("id", mysql.VARCHAR(64), primary_key=True),
        sa.Column("revision_id", mysql.CHAR(36), nullable=False),
        sa.Column("revision_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("approval_binding_hash", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "publish_variants",
        sa.Column("id", mysql.VARCHAR(64), primary_key=True),
        sa.Column("plan_id", mysql.VARCHAR(64), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("account_ref", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("target_hash", sa.String(length=80), nullable=False),
    )
    op.create_index("ix_publish_variants_plan_id", "publish_variants", ["plan_id"])

    op.create_table(
        "publish_jobs",
        sa.Column("id", mysql.VARCHAR(64), primary_key=True),
        sa.Column("plan_id", mysql.VARCHAR(64), nullable=False),
        sa.Column("variant_id", mysql.VARCHAR(64), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("account_ref", sa.String(length=200), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("remote_id", sa.String(length=300), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("reconcile_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_publish_jobs_plan_id", "publish_jobs", ["plan_id"])

    op.create_table(
        "publish_attempts",
        sa.Column("id", mysql.VARCHAR(64), primary_key=True),
        sa.Column("job_id", mysql.VARCHAR(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_publish_attempts_job_seq"),
    )
    op.create_index("ix_publish_attempts_job_id", "publish_attempts", ["job_id", "attempt_number"])

    op.create_table(
        "publish_receipts",
        sa.Column("id", mysql.VARCHAR(64), primary_key=True),
        sa.Column("job_id", mysql.VARCHAR(64), nullable=False, unique=True),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("remote_id", sa.String(length=300), nullable=False),
        sa.Column("remote_url", sa.String(length=500), nullable=True),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("publish_receipts")
    op.drop_table("publish_attempts")
    op.drop_table("publish_jobs")
    op.drop_index("ix_publish_variants_plan_id", table_name="publish_variants")
    op.drop_table("publish_variants")
    op.drop_table("publish_plans")
    op.drop_index("ix_tool_executions_run_id", table_name="tool_executions")
    op.drop_table("tool_executions")
    op.drop_index("ix_agent_run_events_run_id", table_name="agent_run_events")
    op.drop_table("agent_run_events")
    op.drop_index("ix_agent_runs_article_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_sessions_article_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
    op.drop_index("ix_article_revisions_article_id", table_name="article_revisions")
    op.drop_table("article_revisions")
    op.drop_table("articles")
