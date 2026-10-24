"""管理员维护 API：多用户迁移与旧数据归属回填。

背景：多用户能力上线前后存在 `owner_user_id IS NULL` 的共享旧数据。
此端点由管理员显式执行，把这些孤儿资源归属到指定用户，避免误删或越权编辑。
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.models.agent_runtime import AgentRun
from app.models.article import Article
from app.models.assistant import AssistantSession
from app.models.media import MediaAsset
from app.models.project import Project
from app.models.publishing import PublishPlan
from app.models.settings_profile import ModelProfile
from app.models.template import ArticleTemplate
from app.models.user import AppUser

router = APIRouter(prefix="/admin", tags=["admin"])


class OwnershipClaimRequest(BaseModel):
    ownerUserId: str | None = Field(default=None, max_length=64)


@router.post("/ownership/claim-orphans")
def claim_orphan_resources(
    body: OwnershipClaimRequest,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_admin),
):
    owner_id = body.ownerUserId or admin.id
    if owner_id != admin.id:
        owner = db.get(AppUser, owner_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="目标用户不存在")

    counts = {}
    counts["projects"] = db.execute(
        update(Project)
        .where(Project.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["articles"] = db.execute(
        update(Article)
        .where(Article.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["customTemplates"] = db.execute(
        update(ArticleTemplate)
        .where(
            ArticleTemplate.owner_user_id.is_(None),
            ArticleTemplate.is_built_in.is_(False),
        )
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["mediaAssets"] = db.execute(
        update(MediaAsset)
        .where(MediaAsset.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["assistantSessions"] = db.execute(
        update(AssistantSession)
        .where(AssistantSession.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["agentRuns"] = db.execute(
        update(AgentRun)
        .where(AgentRun.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["publishPlans"] = db.execute(
        update(PublishPlan)
        .where(PublishPlan.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    counts["modelProfiles"] = db.execute(
        update(ModelProfile)
        .where(ModelProfile.owner_user_id.is_(None))
        .values(owner_user_id=owner_id)
    ).rowcount or 0
    db.commit()
    return {"ownerUserId": owner_id, "claimed": counts}


@router.get("/ownership/orphans")
def orphan_summary(
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_admin),
):
    def _count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    from sqlalchemy import select

    return {
        "projects": _count(Project, Project.owner_user_id.is_(None)),
        "articles": _count(Article, Article.owner_user_id.is_(None)),
        "customTemplates": _count(
            ArticleTemplate,
            ArticleTemplate.owner_user_id.is_(None),
            ArticleTemplate.is_built_in.is_(False),
        ),
        "mediaAssets": _count(MediaAsset, MediaAsset.owner_user_id.is_(None)),
        "assistantSessions": _count(AssistantSession, AssistantSession.owner_user_id.is_(None)),
        "agentRuns": _count(AgentRun, AgentRun.owner_user_id.is_(None)),
        "publishPlans": _count(PublishPlan, PublishPlan.owner_user_id.is_(None)),
        "modelProfiles": _count(ModelProfile, ModelProfile.owner_user_id.is_(None)),
    }
