"""发布计划 API：蓝本 /v2/publish 契约的 FastAPI 移植。

状态机：draft -> approve（绑定哈希防篡改）-> enqueue（生成幂等 jobs）
-> process（dry_run 无副作用回执）-> reconcile / resolve-unknown。
真实平台投递第二阶段接入，delivery 目前只有蓝本的 DryRunDelivery。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.db.session import get_db
from app.models.user import AppUser
from app.schemas.blueprint import (
    PublishApproveRequest,
    PublishPlanRequest,
    PublishResolveRequest,
)
from sqlalchemy import select

from app.models.publishing import PublishJob, PublishPlan
from app.services.publish_outbox import PublishOutboxService, PublishPlanError

router = APIRouter(prefix="/publish", tags=["publish"])


def _service(db: Session) -> PublishOutboxService:
    return PublishOutboxService(db)


def _owned_job(db: Session, job_id: str, user: AppUser) -> None:
    job = db.get(PublishJob, job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "PUBLISH_JOB_NOT_FOUND"})
    _owned_plan(db, job.plan_id, user)


def _owned_plan(db: Session, plan_id: str, user: AppUser) -> PublishPlan:
    plan = db.get(PublishPlan, plan_id)
    if plan is None or (
        plan.owner_user_id is not None and plan.owner_user_id != user.id
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "PUBLISH_PLAN_NOT_FOUND"})
    return plan


def _error(exc: PublishPlanError, code: str, status_code: int, retryable: bool):
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc), "retryable": retryable},
    )


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    query = select(PublishPlan).order_by(PublishPlan.updated_at.desc())
    query = query.where(PublishPlan.owner_user_id == user.id)
    plans = db.scalars(query).all()
    service = PublishOutboxService(db)
    return {"plans": [service.get_plan(p.id) for p in plans]}


@router.post("/plans", status_code=201)
def create_plan(
    body: PublishPlanRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    try:
        return _service(db).create_plan(
            revision_id=body.revisionId, title=body.title,
            markdown=body.markdown,
            targets=[t.model_dump() for t in body.targets],
            owner_user_id=user.id,
        )
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_PLAN_REJECTED", 400, False) from None


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    _owned_plan(db, plan_id, user)
    try:
        return _service(db).get_plan(plan_id)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_PLAN_NOT_FOUND", 404, False) from None


@router.post("/plans/{plan_id}/approve")
def approve_plan(
    plan_id: str,
    body: PublishApproveRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    _owned_plan(db, plan_id, user)
    try:
        return _service(db).approve(plan_id, body.actorId)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_APPROVAL_REJECTED", 409, True) from None


@router.post("/plans/{plan_id}/enqueue")
def enqueue_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    _owned_plan(db, plan_id, user)
    try:
        return _service(db).enqueue(plan_id)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_ENQUEUE_REJECTED", 409, True) from None


@router.post("/jobs/{job_id}/process")
def process_job(job_id: str, db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    _owned_job(db, job_id, user)
    try:
        return _service(db).process(job_id)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_JOB_REJECTED", 409, True) from None


@router.post("/jobs/{job_id}/reconcile")
def reconcile_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    _owned_job(db, job_id, user)
    try:
        return _service(db).reconcile(job_id)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_RECONCILIATION_REJECTED", 409, True) from None


@router.post("/jobs/{job_id}/resolve-unknown")
def resolve_unknown_job(
    job_id: str,
    body: PublishResolveRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    _owned_job(db, job_id, user)
    try:
        return _service(db).resolve_unknown(job_id, body.resolution)
    except PublishPlanError as exc:
        raise _error(exc, "PUBLISH_UNKNOWN_RESOLUTION_REJECTED", 409, False) from None
