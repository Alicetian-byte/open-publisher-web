"""设置 API：模型档案管理 + 密钥加密存储 + 连通性测试与模型列表发现。

蓝本 model-profile / model-test-service / model-discovery 的 Web 版：
- 多 profile 增删改查与激活（is_default）
- 企业级密钥存储（2026-10-26 起）：密钥密文入库 app_secrets（Fernet 信封加密，
  主密钥走 SECRET_ENCRYPTION_KEY 环境变量），环境变量仅作回退/开发路径；
  密钥明文永不入库、永不回显前端，管理端只见掩码尾号 keyHint
- test / discover 使用当前激活 profile（无则回退全局配置）
"""

import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import secret_box
from app.core.auth import require_admin, require_user
from app.db.session import get_db
from app.models.user import AppUser
from app.models.settings_profile import ModelProfile
from app.services import secret_store
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


class KeyPayload(BaseModel):
    """密钥录入：明文只在请求体里出现一次，入库即加密，永不回显。"""

    apiKey: str = Field(min_length=4, max_length=4096)


def _owned_profile(db: Session, profile_id: str, user: AppUser) -> ModelProfile | None:
    profile = db.get(ModelProfile, profile_id)
    if profile is None or (
        profile.owner_user_id is not None and profile.owner_user_id != user.id
    ):
        return None
    return profile


def _profile_key_fields(db: Session, profile: ModelProfile) -> dict:
    """profile 密钥状态：DB 密文 > 环境变量 > 未配置（只返回掩码）。"""
    meta = secret_store.get_secret_meta(db, secret_store.profile_secret_id(profile.id))
    if meta is not None:
        return {
            "keyConfigured": True,
            "keySource": "db",
            "keyHint": meta.get("keyHint", ""),
        }
    env_value = os.environ.get(profile.api_key_env, "")
    if env_value:
        return {
            "keyConfigured": True,
            "keySource": "env",
            "keyHint": secret_box.mask(env_value),
        }
    return {"keyConfigured": False, "keySource": "none", "keyHint": ""}


def _profile_out(profile: ModelProfile, db: Session) -> dict:
    key = _profile_key_fields(db, profile)
    return {
        "id": profile.id,
        "name": profile.name,
        "provider": profile.provider,
        "baseUrl": profile.base_url,
        "modelId": profile.model_id,
        "apiKeyEnv": profile.api_key_env,
        "timeoutSeconds": profile.timeout_seconds,
        "isDefault": profile.is_default,
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
        "ownerId": profile.owner_user_id,
        **key,
    }


@router.get("/model")
def model_status(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    resolved = resolve_llm_config()
    return {
        "baseUrl": resolved["base_url"],
        "model": resolved["model"],
        "keyConfigured": bool(resolved["api_key"]),
        "keySource": resolved.get("keySource", "none"),
        "keyHint": resolved.get("keyHint", ""),
        "timeoutSeconds": resolved["timeout_seconds"],
        "profileId": resolved["profileId"],
        "profileName": resolved["profileName"],
        "apiKeyEnv": resolved["apiKeyEnv"],
    }


@router.get("/image", dependencies=[Depends(require_admin)])
def image_status(db: Session = Depends(get_db)):
    """管理端生图配置状态（DB > 环境变量 > 文本 LLM 回退）。"""
    return _image_out(db)


@router.get("/image-models")
def list_image_models(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    """创作端可选的已配置生图模型（只读，不含密钥本体）。"""
    from app.models.settings_profile import ImageConfig

    rows = db.query(ImageConfig).order_by(ImageConfig.updated_at.desc()).all()
    models = []
    for row in rows:
        meta = secret_store.get_secret_meta(db, secret_store.SECRET_ID_IMAGE_GLOBAL)
        env_value = os.environ.get(row.api_key_env, "")
        models.append(
            {
                "id": row.id,
                "name": row.model_id,
                "model": row.model_id,
                "keyConfigured": bool(meta is not None or env_value),
                "keySource": "db" if meta is not None else ("env" if env_value else "none"),
                "keyHint": (meta or {}).get("keyHint", "") or secret_box.mask(env_value),
            }
        )
    return {"models": models}


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db), user: AppUser = Depends(require_user)):
    from sqlalchemy import or_

    profiles = db.query(ModelProfile).filter(or_(
        ModelProfile.owner_user_id == user.id,
        ModelProfile.owner_user_id.is_(None),
    )).order_by(ModelProfile.created_at.desc()).all()
    return {"profiles": [_profile_out(p, db) for p in profiles]}


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
    return _profile_out(profile, db)


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
    return _profile_out(profile, db)


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
    return _profile_out(profile, db)


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


# ---------- 密钥管理（DB 加密存储；主密钥走 SECRET_ENCRYPTION_KEY 环境变量） ----------


def _key_status_out(db: Session, secret_id: str, env_fallback: str = "") -> dict:
    meta = secret_store.get_secret_meta(db, secret_id)
    if meta is not None:
        return {
            "keyConfigured": True,
            "keySource": "db",
            "keyHint": meta.get("keyHint", ""),
            "keyVersion": meta.get("keyVersion"),
        }
    if env_fallback:
        return {
            "keyConfigured": True,
            "keySource": "env",
            "keyHint": secret_box.mask(env_fallback),
            "keyVersion": None,
        }
    return {"keyConfigured": False, "keySource": "none", "keyHint": "", "keyVersion": None}


@router.put("/llm/key", dependencies=[Depends(require_admin)])
def set_llm_key(
    body: KeyPayload,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """录入/更新全局 LLM 密钥（加密入库，覆盖 llm:global）。"""
    from app.core.config import get_settings

    secret_store.set_secret(
        db, secret_store.SECRET_ID_LLM_GLOBAL, body.apiKey.strip(), actor=user.id
    )
    return _key_status_out(db, secret_store.SECRET_ID_LLM_GLOBAL, get_settings().llm_api_key)


@router.delete("/llm/key", dependencies=[Depends(require_admin)])
def delete_llm_key(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """删除全局 LLM 密钥（回退环境变量）。"""
    from app.core.config import get_settings

    secret_store.delete_secret(db, secret_store.SECRET_ID_LLM_GLOBAL, actor=user.id)
    return _key_status_out(db, secret_store.SECRET_ID_LLM_GLOBAL, get_settings().llm_api_key)


@router.put("/profiles/{profile_id}/key", dependencies=[Depends(require_admin)])
def set_profile_key(
    profile_id: str,
    body: KeyPayload,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """录入/更新档案级密钥（加密入库，优先级高于该档案的环境变量）。"""
    profile = _owned_profile(db, profile_id, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="模型档案不存在")
    secret_store.set_secret(
        db, secret_store.profile_secret_id(profile.id), body.apiKey.strip(), actor=user.id
    )
    return _key_status_out(db, secret_store.profile_secret_id(profile.id))


@router.delete("/profiles/{profile_id}/key", dependencies=[Depends(require_admin)])
def delete_profile_key(
    profile_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """删除档案级密钥（回退该档案的环境变量 / 全局配置）。"""
    profile = _owned_profile(db, profile_id, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="模型档案不存在")
    secret_store.delete_secret(db, secret_store.profile_secret_id(profile.id), actor=user.id)
    return _key_status_out(db, secret_store.profile_secret_id(profile.id))


@router.put("/image/key", dependencies=[Depends(require_admin)])
def set_image_key(
    body: KeyPayload,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """录入/更新全局生图密钥（加密入库，覆盖 image:global）。"""
    from app.core.config import get_settings

    secret_store.set_secret(
        db, secret_store.SECRET_ID_IMAGE_GLOBAL, body.apiKey.strip(), actor=user.id
    )
    return _key_status_out(
        db, secret_store.SECRET_ID_IMAGE_GLOBAL, get_settings().image_api_key
    )


@router.delete("/image/key", dependencies=[Depends(require_admin)])
def delete_image_key(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    """删除全局生图密钥（回退环境变量 / 文本模型密钥）。"""
    from app.core.config import get_settings

    secret_store.delete_secret(db, secret_store.SECRET_ID_IMAGE_GLOBAL, actor=user.id)
    return _key_status_out(
        db, secret_store.SECRET_ID_IMAGE_GLOBAL, get_settings().image_api_key
    )


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
            detail="未配置密钥：请在管理端录入密钥（DB 加密存储），或设置后端环境变量",
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
        raise HTTPException(status_code=501, detail="未配置密钥：请在管理端录入或设置环境变量")
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


class ImageConfigUpdate(BaseModel):
    """管理端生图配置；密钥走独立的 /image/key 接口，本体永不回显。"""

    baseUrl: str = Field(min_length=1, max_length=500)
    modelId: str = Field(min_length=1, max_length=200)
    apiKeyEnv: str = Field(default="IMAGE_API_KEY", max_length=120)
    timeoutSeconds: int = Field(default=180, ge=1, le=1800)


def _image_out(db: Session | None = None) -> dict:
    from app.core.config import get_settings

    from app.services.model_profile_service import resolve_image_config

    resolved = resolve_image_config(db)
    return {
        "baseUrl": resolved["base_url"],
        "model": resolved["model"],
        "apiKeyEnv": resolved["apiKeyEnv"],
        "keyConfigured": bool(resolved["api_key"]),
        "keySource": resolved.get("keySource", "none"),
        "keyHint": resolved.get("keyHint", ""),
        "timeoutSeconds": resolved["timeout_seconds"],
        "source": resolved["source"],
    }


@router.put("/image", dependencies=[Depends(require_admin)])
def update_image_config(
    body: ImageConfigUpdate,
    db: Session = Depends(get_db),
):
    """保存全局生图配置（单行 upsert，id 固定 global）。"""
    from app.models.settings_profile import ImageConfig
    from app.services.model_profile_service import IMAGE_CONFIG_ID

    row = db.get(ImageConfig, IMAGE_CONFIG_ID)
    if row is None:
        row = ImageConfig(id=IMAGE_CONFIG_ID)
        db.add(row)
    row.base_url = body.baseUrl.strip()
    row.model_id = body.modelId.strip()
    row.api_key_env = body.apiKeyEnv.strip() or "IMAGE_API_KEY"
    row.timeout_seconds = body.timeoutSeconds
    db.commit()
    db.refresh(row)
    return _image_out(db)


@router.delete("/image", dependencies=[Depends(require_admin)])
def reset_image_config(db: Session = Depends(get_db)):
    """删除 DB 覆盖，回退 IMAGE_* 环境变量 / 文本 LLM 配置。"""
    from app.models.settings_profile import ImageConfig
    from app.services.model_profile_service import IMAGE_CONFIG_ID

    row = db.get(ImageConfig, IMAGE_CONFIG_ID)
    if row is not None:
        db.delete(row)
        db.commit()
    return _image_out(db)


@router.post("/image/test", dependencies=[Depends(require_admin)])
def test_image_config():
    """生一张最小测试图验证生图链路连通性。"""
    from openai import OpenAI

    from app.services.model_profile_service import resolve_image_config

    resolved = resolve_image_config()
    if not resolved["api_key"]:
        raise HTTPException(
            status_code=501,
            detail="未配置密钥：请在管理端录入生图密钥，或设置 IMAGE_API_KEY 环境变量",
        )
    started = time.monotonic()
    client = OpenAI(
        api_key=resolved["api_key"],
        base_url=resolved["base_url"],
        timeout=resolved["timeout_seconds"],
    )
    try:
        result = None
        last_exc: Exception | None = None
        for size in ("512x512", "1024x1024"):
            try:
                result = client.images.generate(
                    model=resolved["model"],
                    prompt="connection test: a tiny minimal blue flower, flat illustration",
                    size=size, n=1,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if result is None:
            raise last_exc if last_exc else RuntimeError("image test failed")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"生图调用失败：{exc}") from None
    item = result.data[0] if result.data else None
    if not item or not (item.b64_json or item.url):
        raise HTTPException(status_code=502, detail="生图调用没有返回内容")
    return {
        "ok": True,
        "latencyMs": int((time.monotonic() - started) * 1000),
        "model": resolved["model"],
    }
