"""发布 Outbox 模型：蓝本 agent-runtime MIGRATION_V2 的 MySQL 迁移。

对应蓝本 publish_plans_v2 / publish_variants_v2 / publish_jobs_v2 /
publish_attempts_v2 / publish_receipts_v2。状态机与幂等键语义保持一致：
- job.state: pending / in_progress / succeeded / failed_retryable /
  failed_terminal / unknown / reconciling / cancelled
- plan.approval_status: pending / approved / rejected / not_required
- plan.status: draft / approved / queued / running / completed / needs_attention
"""

from sqlalchemy import CHAR, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublishPlan(Base):
    __tablename__ = "publish_plans"

    id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    revision_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    revision_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    approval_binding_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False)


class PublishVariant(Base):
    __tablename__ = "publish_variants"

    id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    target_hash: Mapped[str] = mapped_column(String(80), nullable=False)


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    remote_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconcile_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False)


class PublishAttempt(Base):
    __tablename__ = "publish_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_publish_attempts_job_seq"),)

    id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[object] = mapped_column(DateTime, nullable=True)


class PublishReceipt(Base):
    __tablename__ = "publish_receipts"

    id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    remote_id: Mapped[str] = mapped_column(String(300), nullable=False)
    remote_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False)
