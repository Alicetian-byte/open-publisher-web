"""模型档案服务：多 profile 解析（蓝本 model-profile + secret-provider 的 Web 等价）。

企业级密钥约定（2026-10-26 起生效）：
- 密钥密文入库：app_secrets 表，Fernet 信封加密，主密钥走 SECRET_ENCRYPTION_KEY 环境变量；
- 环境变量保留为回退/开发路径：DB 密文 > 环境变量 > 全局回退；
- 明文永不入库、永不回显前端（管理端只见掩码尾号 keyHint）。
"""

import os
import uuid

from sqlalchemy.orm import Session

from app.core import secret_box
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.settings_profile import ImageConfig, ModelProfile
from app.services.secret_store import (
    SECRET_ID_IMAGE_GLOBAL,
    SECRET_ID_LLM_GLOBAL,
    get_secret,
    get_secret_meta,
    profile_secret_id,
)


def get_active_profile(db: Session, owner_user_id: str | None = None) -> ModelProfile | None:
    query = db.query(ModelProfile).filter(ModelProfile.is_default.is_(True))
    if owner_user_id:
        query = query.filter(ModelProfile.owner_user_id == owner_user_id)
    return query.order_by(ModelProfile.created_at.desc()).first()


def _env_key_source(env_value: str, settings_api_key: str) -> tuple[str, str]:
    """环境变量路径的 keySource/keyHint。"""
    if env_value:
        return "env", secret_box.mask(env_value)
    if settings_api_key:
        return "env", secret_box.mask(settings_api_key)
    return "none", ""


def resolve_llm_config() -> dict:
    """解析当前生效的 LLM 配置；DB 密钥 > profile 环境变量 > 全局密钥回退。"""
    settings = get_settings()
    source, hint = _env_key_source("", settings.llm_api_key)
    config = {
        "profileId": None,
        "profileName": None,
        "apiKeyEnv": "LLM_API_KEY",
        "api_key": settings.llm_api_key,
        "keySource": source,
        "keyHint": hint,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "timeout_seconds": settings.llm_timeout_seconds,
    }
    try:
        with SessionLocal() as db:
            global_meta = get_secret_meta(db, SECRET_ID_LLM_GLOBAL) or {}
            global_key = get_secret(db, SECRET_ID_LLM_GLOBAL)
            profile = get_active_profile(db)
            if profile is None:
                if global_key:
                    config.update(
                        {
                            "api_key": global_key,
                            "keySource": "db",
                            "keyHint": global_meta.get("keyHint", ""),
                        }
                    )
                return config
            pid = profile_secret_id(profile.id)
            profile_meta = get_secret_meta(db, pid) or {}
            profile_key = get_secret(db, pid)
            env_value = os.environ.get(profile.api_key_env, "")
            if profile_key:
                key_source, key_hint = "db", profile_meta.get("keyHint", "")
            elif env_value:
                key_source, key_hint = _env_key_source(env_value, "")
            elif global_key:
                key_source, key_hint = "db", global_meta.get("keyHint", "")
            else:
                key_source, key_hint = _env_key_source("", settings.llm_api_key)
            config.update(
                {
                    "profileId": profile.id,
                    "profileName": profile.name,
                    "apiKeyEnv": profile.api_key_env,
                    "api_key": profile_key or env_value or global_key or settings.llm_api_key,
                    "keySource": key_source,
                    "keyHint": key_hint,
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
    source, hint = _env_key_source("", settings.llm_api_key)
    config = {
        "profileId": None,
        "profileName": None,
        "apiKeyEnv": "LLM_API_KEY",
        "api_key": settings.llm_api_key,
        "keySource": source,
        "keyHint": hint,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "timeout_seconds": settings.llm_timeout_seconds,
    }
    if not profile_id:
        active = get_active_profile(db, owner_user_id)
        profile_id = active.id if active else None
    if not profile_id:
        global_key = get_secret(db, SECRET_ID_LLM_GLOBAL)
        if global_key:
            global_meta = get_secret_meta(db, SECRET_ID_LLM_GLOBAL) or {}
            config.update(
                {"api_key": global_key, "keySource": "db", "keyHint": global_meta.get("keyHint", "")}
            )
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
    pid = profile_secret_id(profile.id)
    profile_meta = get_secret_meta(db, pid) or {}
    profile_key = get_secret(db, pid)
    global_meta = get_secret_meta(db, SECRET_ID_LLM_GLOBAL) or {}
    global_key = get_secret(db, SECRET_ID_LLM_GLOBAL)
    env_value = os.environ.get(profile.api_key_env, "")
    if profile_key:
        key_source, key_hint = "db", profile_meta.get("keyHint", "")
    elif env_value:
        key_source, key_hint = _env_key_source(env_value, "")
    elif global_key:
        key_source, key_hint = "db", global_meta.get("keyHint", "")
    else:
        key_source, key_hint = _env_key_source("", settings.llm_api_key)
    config.update(
        {
            "profileId": profile.id,
            "profileName": profile.name,
            "apiKeyEnv": profile.api_key_env,
            "api_key": profile_key or env_value or global_key or settings.llm_api_key,
            "keySource": key_source,
            "keyHint": key_hint,
            "base_url": profile.base_url,
            "model": profile.model_id,
            "timeout_seconds": profile.timeout_seconds,
        }
    )
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


def resolve_image_config(
    db: Session | None = None,
    *,
    profile_id: str | None = None,
) -> dict:
    """解析生图配置：DB 密钥 > IMAGE_* 环境变量 > 全局 LLM 密钥回退。

    密钥优先级：app_secrets[image:global] > IMAGE_API_KEY 环境变量
    > app_secrets[llm:global] > Settings（IMAGE_API_KEY > LLM_API_KEY）。
    profile_id 非空时优先取对应配置行；行不存在时回退全局默认行。
    """
    settings = get_settings()
    env_fallback_key = settings.image_api_key or settings.llm_api_key
    source, hint = _env_key_source("", env_fallback_key)
    config = {
        "apiKeyEnv": "IMAGE_API_KEY",
        "api_key": env_fallback_key,
        "keySource": source,
        "keyHint": hint,
        "base_url": settings.image_base_url or settings.llm_base_url,
        "model": settings.image_model,
        "timeout_seconds": settings.image_timeout_seconds or settings.llm_timeout_seconds,
        "source": "env" if (settings.image_api_key or settings.image_base_url) else "fallback",
        "profileId": None,
    }
    try:
        if db is None:
            with SessionLocal() as session:
                row = session.get(ImageConfig, profile_id or IMAGE_CONFIG_ID)
                if row is None and profile_id:
                    row = session.get(ImageConfig, IMAGE_CONFIG_ID)
                _apply_image_row(config, session, row, settings)
        else:
            row = db.get(ImageConfig, profile_id or IMAGE_CONFIG_ID)
            if row is None and profile_id:
                row = db.get(ImageConfig, IMAGE_CONFIG_ID)
            _apply_image_row(config, db, row, settings)
    except Exception:  # noqa: BLE001 - 表不存在等场景回退环境变量配置
        return config
    return config


def _apply_image_row(
    config: dict,
    db: Session,
    row: ImageConfig | None,
    settings,
) -> None:
    """把 DB 生图配置行叠加进 config（含密钥三级回退）。"""
    if row is not None:
        env_value = os.environ.get(row.api_key_env, "")
        config.update(
            {
                "apiKeyEnv": row.api_key_env,
                "base_url": row.base_url,
                "model": row.model_id,
                "timeout_seconds": row.timeout_seconds,
                "source": "db",
                "profileId": row.id,
            }
        )
    else:
        env_value = os.environ.get("IMAGE_API_KEY", "")
    image_secret_meta = get_secret_meta(db, SECRET_ID_IMAGE_GLOBAL) or {}
    image_secret = get_secret(db, SECRET_ID_IMAGE_GLOBAL)
    llm_secret_meta = get_secret_meta(db, SECRET_ID_LLM_GLOBAL) or {}
    llm_secret = get_secret(db, SECRET_ID_LLM_GLOBAL)
    if image_secret:
        key_source, key_hint = "db", image_secret_meta.get("keyHint", "")
    elif env_value:
        key_source, key_hint = _env_key_source(env_value, "")
    elif llm_secret:
        key_source, key_hint = "db", llm_secret_meta.get("keyHint", "")
    else:
        key_source, key_hint = _env_key_source(
            "", settings.image_api_key or settings.llm_api_key
        )
    config.update(
        {
            "api_key": image_secret
            or env_value
            or llm_secret
            or settings.image_api_key
            or settings.llm_api_key,
            "keySource": key_source,
            "keyHint": key_hint,
        }
    )
