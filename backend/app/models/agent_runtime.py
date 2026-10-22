"""Agent 运行日志模型：蓝本 agent-runtime MIGRATION_V1 的 MySQL 迁移。

对应蓝本 storage/schema.ts 的 agent_sessions / agent_runs /
agent_run_events / tool_executions 四张表，字段语义保持一致。
"""

from sqlalchemy import CHAR, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    article_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    article_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    base_revision_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[object] = mapped_column(DateTime, nullable=True)


class AgentRunEvent(Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_agent_run_events_run_seq"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[object] = mapped_column(DateTime, nullable=True)
