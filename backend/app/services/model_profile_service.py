"""模型档案服务：多 profile 解析（蓝本 model-profile + secret-provider 的 Web 等价）。

- 密钥永不入库：profile 只记录环境变量名（api_key_env），取值时读进程环境。
- 任一环节失败都回退全局 Settings，保证旧部署/测试环境不受影响。
"""

import os
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.settings_profile import ImageConfig, ModelProfile


def get_active_profile(db: Session, owner_user_id: str | None = None) -> ModelProfile | None:
    query = db.query(ModelProfile).filter(ModelProfile.is_default.is_(True))
    if owner_user_id:
        query = query.filter(ModelProfile.owner_user_id == owner_user_id)
    return query.order_by(ModelProfile.created_at.desc()).first()


def resolve_llm_config() -> dict:
    """解析当前生效的 LLM 配置；激活 profile 覆盖全局环境变量。"""
    settings = get_settings()
    config = {
        "profileId": None,
        "profileName": None,
        "apiKeyEnv": "LLM_API_KEY",
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "timeout_seconds": settings.llm_timeout_seconds,
    }
    try:
        with SessionLocal() as db:
            profile = get_active_profile(db)
            if profile is None:
                return config
        env_value = os.environ.get(profile.api_key_env, "")
        config.update(
            {
                "profileId": profile.id,
                "profileName": profile.name,
                "apiKeyEnv": profile.api_key_env,
                "api_key": env_value or settings.llm_api_key,
                "base_url": profile.base_url,
                "model": profile.model_id,
                "timeout_seconds": profile.timeout_seconds,
            }
        )
    except Exception:  # noqa: BLE001 - 表不存在等场景回退全局配置
        return config
    return config


def resolve_llm_profile_config(
    db: Session,
    *,
    profile_id: str | None,
    owner_user_id: str | None = None,
) -> dict:
    """按用户可用档案解析模型；profile_id 为空则回退全局激活档案。"""
    settings = get_settings()
    config = {
        "profileId": None,
        "profileName": None,
        "apiKeyEnv": "LLM_API_KEY",
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "timeout_seconds": settings.llm_timeout_seconds,
    }
    if not profile_id:
        active = get_active_profile(db, owner_user_id)
        profile_id = active.id if active else None
    if not profile_id:
        return config
    profile = db.get(ModelProfile, profile_id)
    if profile is None:
        return config
    if (
        owner_user_id
        and profile.owner_user_id is not None
        and profile.owner_user_id != owner_user_id
    ):
        return config
    env_value = os.environ.get(profile.api_key_env, "")
    config.update({
        "profileId": profile.id,
        "profileName": profile.name,
        "apiKeyEnv": profile.api_key_env,
        "api_key": env_value or settings.llm_api_key,
        "base_url": profile.base_url,
        "model": profile.model_id,
        "timeout_seconds": profile.timeout_seconds,
    })
    return config


def create_profile(
    db: Session,
    *,
    name: str,
    base_url: str,
    model_id: str,
    api_key_env: str,
    provider: str = "custom",
    timeout_seconds: int = 120,
    is_default: bool = False,
    owner_user_id: str | None = None,
) -> ModelProfile:
    if is_default:
        db.query(ModelProfile).update({ModelProfile.is_default: False})
    profile = ModelProfile(
        id=f"mp-{uuid.uuid4().hex[:32]}",
        name=name,
        provider=provider,
        base_url=base_url,
        model_id=model_id,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        is_default=is_default,
        owner_user_id=owner_user_id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


IMAGE_CONFIG_ID = "global"


def get_image_config(db: Session) -> ImageConfig | None:
    return db.get(ImageConfig, IMAGE_CONFIG_ID)


def resolve_image_config(db: Session | None = None) -> dict:
    """解析生图配置：DB 全局配置 > IMAGE_* 环境变量 > 文本 LLM 回退。

    与文本 LLM 相同的密钥约定：api_key_env 只记录环境变量名，
    运行时读取进程环境，密钥本体永不入库。
    """
    settings = get_settings()
    has_env_override = bool(settings.image_api_key or settings.image_base_url)
    config = {
        "apiKeyEnv": "IMAGE_API_KEY",
        "api_key": settings.image_api_key or settings.llm_api_key,
        "base_url": settings.image_base_url or settings.llm_base_url,
        "model": settings.image_model,
        "timeout_seconds": settings.image_timeout_seconds or settings.llm_timeout_seconds,
        "source": "env" if has_env_override else "fallback",
    }
    try:
        if db is None:
            with SessionLocal() as session:
                row = session.get(ImageConfig, IMAGE_CONFIG_ID)
        else:
            row = db.get(ImageConfig, IMAGE_CONFIG_ID)
        if row is not None:
            env_value = os.environ.get(row.api_key_env, "")
            config.update(
                {
                    "apiKeyEnv": row.api_key_env,
                    "api_key": env_value or settings.image_api_key or settings.llm_api_key,
                    "base_url": row.base_url,
                    "model": row.model_id,
                    "timeout_seconds": row.timeout_seconds,
                    "source": "db",
                }
            )
    except Exception:  # noqa: BLE001 - 表不存在等场景回退环境变量配置
        return config
    return config