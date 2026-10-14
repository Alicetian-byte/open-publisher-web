import uuid

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.run import uuid_pk


class TweetRevision(Base):
    """推文版本：权威稿，每次 AI 生成/优化或用户编辑都产生新版本。"""

    __tablename__ = "tweet_revisions"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), default="low", nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="ai_generated", nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
