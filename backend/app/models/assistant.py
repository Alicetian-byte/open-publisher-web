"""ArticleAssistant 会话持久化模型。

- assistant_sessions：一个会话绑定一篇文章（可选）和一个用户；
- assistant_messages：不可变对话记录，便于恢复和审计。
"""

from sqlalchemy import CHAR, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssistantSession(Base):
    __tablename__ = "assistant_sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    article_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="编辑助手")
    active_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("assistant_sessions.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
