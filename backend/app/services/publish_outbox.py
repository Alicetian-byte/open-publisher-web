"""发布 Outbox：蓝本 PublishOutboxService 的 Python 移植。

保持蓝本状态机不变：
- plan: draft -> approved -> queued -> running / completed / needs_attention
- job:  pending -> in_progress -> succeeded / failed_retryable /
        failed_terminal / unknown -> reconciling -> ...
- 幂等键 = hash(publisher-v1:plan:variant:platform:account:payloadHash)，
  UNIQUE 约束保证同一内容不会被重复投递
- 审批绑定哈希（approval_binding_hash）保证"审批后内容没被偷偷改过"

第一阶段不接真实平台（PROJECT_PLAN 明确），delivery 只实现蓝本的
DryRunDelivery（无副作用回执），WechatSync 桥留到第二阶段。
"""

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import ArticleRevision
from app.models.publishing import (
    PublishAttempt,
    PublishJob,
    PublishPlan,
    PublishReceipt,
    PublishVariant,
)


class PublishPlanError(Exception):
    """发布计划操作被拒绝（400/409 由 API 层映射）。"""


def _hash(value) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DryRunDelivery:
    """蓝本 DryRunDelivery：显式无副作用的本地回执，用于走通审批/重试/回执链路。"""

    def deliver(self, *, idempotency_key: str, platform: str, account_ref: str,
                title: str, markdown: str, mode: str) -> dict:
        if mode != "dry_run":
            raise PublishPlanError("dry_run 通道收到不支持的投递模式")
        return {
            "remoteId": f"dry-run:{idempotency_key}",
            "details": {
                "mode": "dry_run",
                "platform": platform,
                "accountRef": account_ref,
                "title": title,
                "markdownLength": len(markdown),
                "draftOnly": True,
                "notice": "本地 dry-run 回执，未创建任何平台内容。",
            },
        }

    def reconcile(self, *, idempotency_key: str, platform: str, mode: str) -> dict | None:
        return {
            "remoteId": f"dry-run:{idempotency_key}",
            "details": {"mode": "dry_run_reconcile", "draftOnly": True,
                        "notice": "dry-run 回执已核验。"},
        }


class PublishOutboxService:
    def __init__(self, db: Session, delivery: DryRunDelivery | None = None):
        self.db = db
        self._dry_run_delivery = delivery or DryRunDelivery()
        self._wechat_delivery: "WeChatOfficialDelivery | None" = None

    @property
    def delivery(self):
        """按当前 job 的 operation 分发到对应的 delivery 后端。"""
        return self._dry_run_delivery  # kept for backward compat; process() dispatches explicitly

    def _delivery_for(self, mode: str):
        if mode == "wechat_sync_draft":
            if self._wechat_delivery is None:
                from app.services.wechat_publisher import WeChatOfficialDelivery
                self._wechat_delivery = WeChatOfficialDelivery(self.db)
            return self._wechat_delivery
        return self._dry_run_delivery

    # ---------- 查询 ----------

    def get_plan(self, plan_id: str) -> dict:
        plan = self.db.get(PublishPlan, plan_id)
        if plan is None:
            raise PublishPlanError("publish plan not found")
        variants = self.db.scalars(
            select(PublishVariant).where(PublishVariant.plan_id == plan_id)
        ).all()
        jobs = self.db.scalars(
            select(PublishJob).where(PublishJob.plan_id == plan_id).order_by(PublishJob.created_at)
        ).all()
        return {
            "planId": plan.id,
            "revisionId": plan.revision_id,
            "status": plan.status,
            "approvalStatus": plan.approval_status,
            "approvalBindingHash": plan.approval_binding_hash,
            "createdAt": plan.created_at.isoformat(),
            "updatedAt": plan.updated_at.isoformat(),
            "variants": [
                {"id": v.id, "platform": v.platform, "accountRef": v.account_ref,
                 "title": v.title, "contentHash": v.content_hash}
                for v in variants
            ],
            "jobs": [
                {"id": j.id, "planId": j.plan_id, "variantId": j.variant_id,
                 "platform": j.platform, "accountRef": j.account_ref,
                 "operation": j.operation, "idempotencyKey": j.idempotency_key,
                 "payloadHash": j.payload_hash, "state": j.state,
                 "remoteId": j.remote_id, "lastError": j.last_error,
                 "reconcileRequired": j.reconcile_required,
                 "createdAt": j.created_at.isoformat(),
                 "updatedAt": j.updated_at.isoformat()}
                for j in jobs
            ],
        }

    # ---------- 创建 / 审批 / 入队 ----------

    def create_plan(self, *, revision_id: str, title: str, markdown: str,
                    targets: list[dict],
                    owner_user_id: str | None = None) -> dict:
        if not targets:
            raise PublishPlanError("publish plan requires at least one target")
        revision = self.db.get(ArticleRevision, revision_id)
        if revision is None:
            raise PublishPlanError("publish revision not found")

        plan_id = f"plan:{uuid4().hex}"
        revision_hash = _hash(markdown)
        now = _now()

        modes: dict[str, str] = {}
        rows = []
        for target in targets:
            platform = str(target.get("platform", "")).strip().lower()
            account_ref = str(target.get("accountRef", "")).strip()
            variant_title = str(target.get("title") or title).strip()
            delivery_mode = str(target.get("deliveryMode", "dry_run"))
            if not platform or not account_ref or not variant_title:
                raise PublishPlanError("publish target platform, accountRef, and title are required")
            if delivery_mode not in ("dry_run", "wechat_sync_draft"):
                raise PublishPlanError(f"unsupported delivery mode: {delivery_mode}")
            variant_id = f"variant:{uuid4().hex}"
            content_hash = _hash({"platform": platform, "markdown": markdown})
            target_hash = _hash({
                "platform": platform, "accountRef": account_ref, "title": variant_title,
                "contentHash": content_hash, "deliveryMode": delivery_mode,
            })
            modes[variant_id] = delivery_mode
            rows.append(PublishVariant(
                id=variant_id, plan_id=plan_id, platform=platform,
                account_ref=account_ref, title=variant_title,
                markdown="<!-- open-publisher variant:" + platform + " -->\n\n" + markdown.strip() + "\n",
                content_hash=content_hash, target_hash=target_hash,
            ))

        if len({mode for mode in modes.values()}) != 1:
            raise PublishPlanError("all targets in one publish plan must use the same delivery mode")

        plan = PublishPlan(
            id=plan_id, revision_id=revision_id, revision_hash=revision_hash,
            status="draft", approval_status="pending",
            plan_json=json.dumps({"modes": modes}, ensure_ascii=False),
            owner_user_id=owner_user_id,
            created_at=now, updated_at=now,
        )
        self.db.add(plan)
        for variant in rows:
            self.db.add(variant)
        self.db.commit()
        return self.get_plan(plan_id)

    def _binding(self, plan: PublishPlan) -> str:
        target_hashes = sorted(
            self.db.scalars(
                select(PublishVariant.target_hash).where(PublishVariant.plan_id == plan.id)
            ).all()
        )
        return _hash({"revisionId": plan.revision_id, "revisionHash": plan.revision_hash,
                      "targetHashes": target_hashes})

    def approve(self, plan_id: str, actor_id: str) -> dict:
        if not actor_id.strip():
            raise PublishPlanError("publish approval actor cannot be blank")
        plan = self.db.get(PublishPlan, plan_id)
        if plan is None:
            raise PublishPlanError("publish plan not found")
        if plan.status not in ("draft", "approved"):
            raise PublishPlanError("publish plan cannot be approved in its current state")
        plan.status = "approved"
        plan.approval_status = "approved"
        plan.approval_binding_hash = self._binding(plan)
        plan.updated_at = _now()
        self.db.commit()
        return self.get_plan(plan_id)

    def enqueue(self, plan_id: str) -> dict:
        plan = self.db.get(PublishPlan, plan_id)
        if plan is None:
            raise PublishPlanError("publish plan not found")
        binding = self._binding(plan)
        if plan.approval_status != "approved" or plan.approval_binding_hash != binding:
            raise PublishPlanError("publish plan must be explicitly approved without content changes")
        now = _now()
        configuration = json.loads(plan.plan_json)
        modes = configuration.get("modes", {})
        variants = self.db.scalars(
            select(PublishVariant).where(PublishVariant.plan_id == plan_id)
        ).all()
        for variant in variants:
            mode = modes.get(variant.id, "dry_run")
            payload = {"mode": mode, "variantId": variant.id, "contentHash": variant.content_hash}
            payload_hash = _hash(payload)
            idempotency_key = _hash(
                "publisher-v1:" + plan_id + ":" + variant.id + ":" + variant.platform
                + ":" + variant.account_ref + ":" + payload_hash
            )
            exists = self.db.scalar(
                select(PublishJob.id).where(PublishJob.idempotency_key == idempotency_key)
            )
            if exists:
                continue
            self.db.add(PublishJob(
                id="job:" + uuid4().hex, plan_id=plan_id, variant_id=variant.id,
                platform=variant.platform, account_ref=variant.account_ref,
                operation=mode, idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                payload_json=json.dumps(payload, ensure_ascii=False),
                state="pending", reconcile_required=False,
                created_at=now, updated_at=now,
            ))
        plan.status = "queued"
        plan.updated_at = now
        self.db.commit()
        return self.get_plan(plan_id)

    # ---------- 执行 / 核验 / 未知消解 ----------

    def _next_attempt_number(self, job_id: str) -> int:
        last = self.db.scalar(
            select(PublishAttempt.attempt_number)
            .where(PublishAttempt.job_id == job_id)
            .order_by(PublishAttempt.attempt_number.desc())
            .limit(1)
        )
        return (last or 0) + 1

    def process(self, job_id: str) -> dict:
        job = self.db.get(PublishJob, job_id)
        if job is None:
            raise PublishPlanError("publish job not found")
        if job.state not in ("pending", "failed_retryable"):
            raise PublishPlanError("only pending or retryable jobs can be processed")

        variant = self.db.get(PublishVariant, job.variant_id)
        if variant is None:
            raise PublishPlanError("publish variant not found")

        attempt_number = self._next_attempt_number(job_id)
        started_at = _now()
        job.state = "in_progress"
        job.updated_at = started_at
        self.db.add(PublishAttempt(
            id="attempt:" + uuid4().hex, job_id=job_id, attempt_number=attempt_number,
            operation=job.operation, state="in_progress",
            request_json=json.dumps({
                "idempotencyKey": job.idempotency_key, "platform": job.platform,
                "accountRef": job.account_ref, "title": variant.title, "mode": job.operation,
            }, ensure_ascii=False),
            started_at=started_at,
        ))
        self.db.commit()

        try:
            delivery = self._delivery_for(job.operation)
            result = delivery.deliver(
                idempotency_key=job.idempotency_key, platform=job.platform,
                account_ref=job.account_ref, title=variant.title,
                markdown=variant.markdown, mode=job.operation,
            )
        except PublishPlanError as exc:
            completed_at = _now()
            job.state = "failed_terminal"
            job.last_error = str(exc)
            job.reconcile_required = False
            job.updated_at = completed_at
            self._finish_attempt(job_id, attempt_number, state="failed", error=str(exc),
                                 completed_at=completed_at)
            self.db.commit()
            self._refresh_plan(job.plan_id)
            return self.get_plan(job.plan_id)

        completed_at = _now()
        job.state = "succeeded"
        job.remote_id = result["remoteId"]
        job.last_error = None
        job.reconcile_required = False
        job.updated_at = completed_at
        self._upsert_receipt(job_id, variant.platform, result, job.payload_hash, completed_at)
        self._finish_attempt(job_id, attempt_number, state="succeeded",
                             response=json.dumps(result, ensure_ascii=False),
                             completed_at=completed_at)
        self.db.commit()
        self._refresh_plan(job.plan_id)
        return self.get_plan(job.plan_id)

    def reconcile(self, job_id: str) -> dict:
        job = self.db.get(PublishJob, job_id)
        if job is None:
            raise PublishPlanError("publish job not found")
        if job.state != "unknown" or not job.reconcile_required:
            raise PublishPlanError(
                "only UNKNOWN publish jobs that require reconciliation can be reconciled"
            )
        variant = self.db.get(PublishVariant, job.variant_id)
        if variant is None:
            raise PublishPlanError("publish variant not found")

        attempt_number = self._next_attempt_number(job_id)
        started_at = _now()
        job.state = "reconciling"
        job.updated_at = started_at
        self.db.add(PublishAttempt(
            id="attempt:" + uuid4().hex, job_id=job_id, attempt_number=attempt_number,
            operation="reconcile", state="in_progress",
            request_json=json.dumps({
                "idempotencyKey": job.idempotency_key, "platform": job.platform,
                "mode": job.operation,
            }, ensure_ascii=False),
            started_at=started_at,
        ))
        self.db.commit()

        delivery = self._delivery_for(job.operation)
        result = delivery.reconcile(
            idempotency_key=job.idempotency_key, platform=job.platform, mode=job.operation,
        )
        completed_at = _now()
        if result:
            job.state = "succeeded"
            job.remote_id = result["remoteId"]
            job.last_error = None
            job.reconcile_required = False
            receipt_details = dict(result["details"], reconciled=True)
            self._upsert_receipt(job_id, variant.platform, result, job.payload_hash,
                                 completed_at, details_override=receipt_details)
            self._finish_attempt(job_id, attempt_number, state="succeeded",
                                 response=json.dumps(result, ensure_ascii=False),
                                 completed_at=completed_at)
        else:
            # 与蓝本一致：查不到远端结果就保持 UNKNOWN，绝不自动重试，避免重复草稿
            job.state = "unknown"
            job.reconcile_required = True
            job.last_error = (
                "当前发布通道不支持按幂等键查询草稿。请在 " + variant.platform +
                " 草稿箱确认是否已创建草稿；系统不会自动重试。"
            )
            self._finish_attempt(job_id, attempt_number, state="unknown",
                                 completed_at=completed_at)
        job.updated_at = completed_at
        self.db.commit()
        self._refresh_plan(job.plan_id)
        return self.get_plan(job.plan_id)

    def resolve_unknown(self, job_id: str, resolution: str) -> dict:
        if resolution not in ("draft_exists", "draft_missing"):
            raise PublishPlanError("resolution must be draft_exists or draft_missing")
        job = self.db.get(PublishJob, job_id)
        if job is None:
            raise PublishPlanError("publish job not found")
        if job.state != "unknown":
            raise PublishPlanError("only UNKNOWN jobs can be resolved")
        completed_at = _now()
        if resolution == "draft_exists":
            job.state = "succeeded"
            job.reconcile_required = False
            job.last_error = None
            job.remote_id = job.remote_id or ("user-confirmed:" + job.idempotency_key[:16])
            job.updated_at = completed_at
        else:
            # 草稿未创建：回到 pending，可安全重试
            job.state = "pending"
            job.reconcile_required = False
            job.last_error = None
            job.updated_at = completed_at
        self.db.commit()
        self._refresh_plan(job.plan_id)
        return self.get_plan(job.plan_id)

    # ---------- 内部 ----------

    def _upsert_receipt(self, job_id: str, platform: str, result: dict,
                        payload_hash: str, created_at, details_override=None) -> None:
        receipt = self.db.scalar(select(PublishReceipt).where(PublishReceipt.job_id == job_id))
        if receipt is None:
            receipt = PublishReceipt(id="receipt:" + uuid4().hex, job_id=job_id)
            self.db.add(receipt)
        receipt.platform = platform
        receipt.status = "draft_saved"
        receipt.remote_id = result["remoteId"]
        receipt.remote_url = result.get("remoteUrl")
        receipt.payload_hash = payload_hash
        details = details_override if details_override is not None else result["details"]
        receipt.details_json = json.dumps(details, ensure_ascii=False)
        receipt.created_at = created_at

    def _finish_attempt(self, job_id: str, attempt_number: int, *, state: str,
                        completed_at, response: str | None = None,
                        error: str | None = None) -> None:
        attempt = self.db.scalar(
            select(PublishAttempt).where(
                PublishAttempt.job_id == job_id,
                PublishAttempt.attempt_number == attempt_number,
            )
        )
        if attempt is None:
            return
        attempt.state = state
        attempt.response_json = response
        attempt.error = error
        attempt.completed_at = completed_at

    def _refresh_plan(self, plan_id: str) -> None:
        states = self.db.scalars(
            select(PublishJob.state).where(PublishJob.plan_id == plan_id)
        ).all()
        if any(s in ("unknown", "failed_terminal") for s in states):
            status = "needs_attention"
        elif states and all(s == "succeeded" for s in states):
            status = "completed"
        elif any(s == "in_progress" for s in states):
            status = "running"
        else:
            status = "queued"
        plan = self.db.get(PublishPlan, plan_id)
        if plan is not None:
            plan.status = status
            plan.updated_at = _now()
            self.db.commit()


def recover_interrupted(db: Session) -> None:
    """蓝本 openRuntimeDatabase 的启动恢复逻辑：runtime 重启后，
    内存中的执行结果无法确认，统一标记为 interrupted / unknown。"""
    from app.models.agent_runtime import AgentRun  # 局部导入避免模块级循环

    now = _now()
    error_json = json.dumps({
        "code": "RUNTIME_RESTARTED",
        "message": "The local runtime restarted before this agent run completed.",
        "retryable": True,
    }, ensure_ascii=False)

    runs = db.scalars(
        select(AgentRun).where(AgentRun.status.in_(
            ("pending", "running", "waiting_user", "stopping")
        ))
    ).all()
    for run in runs:
        run.status = "interrupted"
        run.completed_at = run.completed_at or now
        run.error_json = run.error_json or error_json

    attempts = db.scalars(
        select(PublishAttempt).where(PublishAttempt.state == "in_progress")
    ).all()
    for attempt in attempts:
        attempt.state = "unknown"
        attempt.error = attempt.error or (
            "Local runtime restarted while publishing; reconcile before retry."
        )
        attempt.completed_at = attempt.completed_at or now

    jobs = db.scalars(
        select(PublishJob).where(PublishJob.state == "in_progress")
    ).all()
    affected_plan_ids = set()
    for job in jobs:
        job.state = "unknown"
        job.reconcile_required = True
        job.last_error = job.last_error or (
            "Local runtime restarted while publishing; reconcile before retry."
        )
        job.updated_at = now
        affected_plan_ids.add(job.plan_id)

    if affected_plan_ids:
        plans = db.scalars(
            select(PublishPlan).where(PublishPlan.id.in_(affected_plan_ids))
        ).all()
        for plan in plans:
            plan.status = "needs_attention"
            plan.updated_at = now

    db.commit()
