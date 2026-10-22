"""设置 API：模型档案管理 + 连通性测试与模型列表发现。

蓝本 model-profile / model-test-service / model-discovery 的 Web 版：
- 多 profile 增删改查与激活（is_default）
- 密钥永不入库、不下发前端：profile 只存环境变量名
- test / discover 使用当前激活 profile（无则回退全局环境变量）
"""

import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_admin, require_user
from app.db.session import get_db
from app.models.user import AppUser
from app.models.settings_profile import ModelProfile
from app.services.model_profile_service import get_active_profile, resolve_llm_config

router = APIRouter(prefix="/settings", tags=["settings"])


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = "custom"
    baseUrl: str = Field(min_length=1, max_length=500)
    modelId: str = Field(min_length=1, max_length=200)
    apiKeyEnv: str = Field(default="LLM_API_KEY", max_length=120)
    timeoutSeconds: int = Field(default=120, ge=1, le=1800)
    isDefault: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: str | None = None
    baseUrl: str | None = Field(default=None, min_length=1, max_length=500)
    modelId: str | None = Field(default=None, min_length=1, max_length=200)
    apiKeyEnv: str | None = Field(default=None, max_length=120)
    timeoutSeconds: int | None = Field(default=None, ge=1, le=1800)
    isDefault: bool | None = None


def _owned_profile(db: Session, profile_id: str, user: AppUser) -> ModelProfile | None:
    profile = db.get(ModelProfile, profile_id)
    if profile is None or (
        profile.owner_user_id is not None and profile.owner_user_id != user.id
    ):
        return None
    return profile


def _profile_out(profile: ModelProfile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "provider": profile.provider,
        "baseUrl": profile.base_url,
        "modelId": profile.model_id,
        "apiKeyEnv": profile.api_key_env,
        "keyConfigured": bool(os.environ.get(profile.api_key_env)),
        "timeoutSeconds": profile.timeout_seconds,
        "isDefault": profile.is_default,
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
        "ownerId": profile.owner_user_id,
    }


@router.get("/model")
def model_status(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    resolved = resolve_llm_config()
    return {
        "baseUrl": resolved["base_url"],
        "model": resolved["model"],
        "keyConfigured": bool(resolved["api_key"]),
        "timeoutSeconds": resolved["timeout_seconds"],
        "profileId": resolved["profileId"],
        "profileName": resolved["profileName"],
        "apiKeyEnv": resolved["apiKeyEnv"],
    }


@router.get("/image")
def image_status():
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "baseUrl": settings.image_base_url or settings.llm_base_url,
        "model": settings.image_model,
        "keyConfigured": bool(settings.image_api_key or settings.llm_api_key),
        "keySource": "IMAGE_API_KEY" if settings.image_api_key else "LLM_API_KEY",
        "timeoutSeconds": settings.image_timeout_seconds,
    }


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    from sqlalchemy import or_

    profiles = db.query(ModelProfile).filter(or_(
        ModelProfile.owner_user_id == user.id,
        ModelProfile.owner_user_id.is_(None),
    )).order_by(ModelProfile.created_at.desc()).all()
    return {"profiles": [_profile_out(p) for p in profiles]}


@router.post("/profiles", status_code=201, dependencies=[Depends(require_admin)])
def create_profile(
    body: ProfileCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    exists = db.query(ModelProfile).filter(
        ModelProfile.name == body.name,
        ModelProfile.owner_user_id == user.id,
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="同名模型档案已存在")
    # 第一个档案自动成为默认，避免空默认状态
    is_default = body.isDefault or not db.query(ModelProfile).filter(
        ModelProfile.owner_user_id == user.id,
    ).first()
    profile = ModelProfile(
        id=f"mp-{uuid.uuid4().hex[:32]}",
        name=body.name,
        provider=body.provider,
        base_url=body.baseUrl,
        model_id=body.modelId,
        api_key_env=body.apiKeyEnv,
        timeout_seconds=body.timeoutSeconds,
        is_default=is_default,
        owner_user_id=user.id,
    )
    if is_default:
        db.query(ModelProfile).filter(ModelProfile.owner_user_id == user.id).update(
            {ModelProfile.is_default: False},
        )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _profile_out(profile)


@router.patch("/profiles/{profile_id}", dependencies=[Depends(require_admin)])
def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    profile = _owned_profile(db, profile_id, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="模型档案不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("isDefault"):
        db.query(ModelProfile).filter(ModelProfile.owner_user_id == user.id).update(
            {ModelProfile.is_default: False},
        )
    mapping = {
        "name": "name",
        "provider": "provider",
        "baseUrl": "base_url",
        "modelId": "model_id",
        "apiKeyEnv": "api_key_env",
        "timeoutSeconds": "timeout_seconds",
        "isDefault": "is_default",
    }
    for key, column in mapping.items():
        if key in data and data[key] is not None:
            setattr(profile, column, data[key])
    db.commit()
    db.refresh(profile)
    return _profile_out(profile)


@router.post("/profiles/{profile_id}/activate", dependencies=[Depends(require_admin)])
def activate_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    profile = _owned_profile(db, profile_id, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="模型档案不存在")
    db.query(ModelProfile).filter(ModelProfile.owner_user_id == user.id).update(
        {ModelProfile.is_default: False},
    )
    profile.is_default = True
    db.commit()
    return _profile_out(profile)


@router.delete("/profiles/{profile_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    profile = _owned_profile(db, profile_id, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="模型档案不存在")
    was_default = profile.is_default
    db.delete(profile)
    db.commit()
    if was_default:
        remaining = db.query(ModelProfile).order_by(ModelProfile.created_at.desc()).first()
        if remaining:
            remaining.is_default = True
            db.commit()
    return None


def _resolved_llm():
    from app.agents.llm_client import LLMClient

    return LLMClient()


@router.post("/model/test", dependencies=[Depends(require_admin)])
def model_test(db: Session = Depends(get_db)):
    """发一条最小请求验证连通性（蓝本 model-test-service 语义，走激活 profile）。"""
    llm = _resolved_llm()
    if not llm._api_key or llm._api_key == "sk-not-configured":
        raise HTTPException(
            status_code=501,
            detail=f"未配置密钥：请设置环境变量（当前来源：{llm.profile_name or '全局 LLM_API_KEY'}）",
        )
    started = time.monotonic()
    try:
        reply = llm.complete(
            "你是连通性探测器。", "回复两个字：正常", temperature=0,
        ).strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from None
    return {
        "ok": True,
        "latencyMs": int((time.monotonic() - started) * 1000),
        "model": llm.model,
        "profileName": llm.profile_name,
        "reply": reply[:50],
    }


@router.get("/models", dependencies=[Depends(require_admin)])
def discover_models(db: Session = Depends(get_db)):
    """拉取 /models 列表（蓝本 model-discovery 语义，走激活 profile）。"""
    from openai import OpenAI

    resolved = resolve_llm_config()
    if not resolved["api_key"]:
        raise HTTPException(status_code=501, detail="未配置 LLM_API_KEY")
    client = OpenAI(
        api_key=resolved["api_key"],
        base_url=resolved["base_url"],
        timeout=resolved["timeout_seconds"],
    )
    try:
        models = [m.id for m in client.models.list()]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"模型列表拉取失败：{exc}") from None
    return {"models": sorted(models)}
