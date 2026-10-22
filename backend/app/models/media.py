"""素材库：蓝本 MediaAsset / image-service 的数据库版。"""

from sqlalchemy import DateTime, JSON, String, Text, text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    alt: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    visual_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    usage_hint: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    generation_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description_source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    # data URL 或远程 https URL；蓝本 MediaAsset.uri 的 Web 等价
    source: Mapped[str] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="upload")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
