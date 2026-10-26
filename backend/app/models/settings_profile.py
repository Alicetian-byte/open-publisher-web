"""模型档案：蓝本 TextModelProfile / model-profile.ts 的 Web 版。

蓝本 profile 通过 secretRef（env://）引用密钥；Web 版等价为
api_key_env —— 指向后端进程环境变量名，密钥永不入库、不下发前端。
"""

from sqlalchemy import Boolean, DateTime, Integer, String, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="custom")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_env: Mapped[str] = mapped_column(String(120), nullable=False, default="LLM_API_KEY")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class ImageConfig(Base):
    """生图模型配置：全局单行（id 固定 "global"）。

    与 ModelProfile 同一密钥约定：只存环境变量名，密钥本体
    永不入库、不下发前端。未建行时回退 IMAGE_* 环境变量，
    再回退文本 LLM 配置。
    """

    __tablename__ = "image_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_env: Mapped[str] = mapped_column(String(120), nullable=False, default="IMAGE_API_KEY")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    updated_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class WorkspacePreference(Base):
    __tablename__ = "workspace_preferences"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
