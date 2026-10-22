"""文章存储模型：蓝本 ArticleStore（文件版）的 MySQL 等价实现。

蓝本把文章存为 article.md + article.json + revisions/ 目录，靠
from sqlalchemy import CHAR, DateTime, Integer, String, Text, text

.pending-commit.json 日志做崩溃恢复；Web 版统一收敛进数据库：
- articles 表保存当前状态（乐观并发：current_revision_id + content_hash）
- article_revisions 表是不可变版本链（parent_revision_id 链式）
"""

from sqlalchemy import CHAR, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    current_revision_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[object] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )


class ArticleRevision(Base):
    __tablename__ = "article_revisions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    article_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
