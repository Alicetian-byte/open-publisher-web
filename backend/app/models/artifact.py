import uuid

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.run import created_at_column, uuid_pk


class TweetArtifact(Base):
    """工作流中某个 Agent 节点的结构化输出（不可变）。"""

    __tablename__ = "tweet_artifacts"

    id: Mapped[str] = uuid_pk()
    run_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[object] = created_at_column()
