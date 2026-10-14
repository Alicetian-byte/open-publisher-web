import uuid

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def uuid_pk() -> Mapped[str]:
    return mapped_column(CHAR(36), primary_key=True, default=_generate_uuid)


def created_at_column() -> Mapped[object]:
    return mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )


class TweetRun(Base):
    """一次 LangGraph 推文生成工作流运行。"""

    __tablename__ = "tweet_runs"

    id: Mapped[str] = uuid_pk()
    project_id: Mapped[str] = mapped_column(
        CHAR(36), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    current_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    started_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[object] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = created_at_column()

