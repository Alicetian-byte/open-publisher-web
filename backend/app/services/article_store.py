"""文章存储：蓝本 ArticleStore 的数据库版移植。

蓝本用文件系统 + .pending-commit.json 日志实现"不可变版本 + 乐观并发"；
Web 版把同一语义收敛进 MySQL：
- commit() 带乐观并发校验（baseRevisionId + baseContentHash），冲突抛
  ArticleConflictError（API 层映射 409）
- 版本一旦落库不可变；restore 产生指向旧内容的新版本，不篡改历史
- 内容哈希与蓝本一致：sha256:<hex>
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.article import Article, ArticleRevision


class ArticlePermissionError(Exception):
    """非属主对他人文章的写入请求。"""


class ArticleConflictError(Exception):
    """乐观并发冲突，等价蓝本 ARTICLE_CONFLICT。"""

    code = "ARTICLE_CONFLICT"


def content_hash(markdown: str) -> str:
    return f"sha256:{hashlib.sha256(markdown.encode('utf-8')).hexdigest()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleStore:
    """与蓝本 ArticleStore 相同的公开语义，存储换成 SQLAlchemy 会话。"""

    def __init__(self, db: Session):
        self.db = db

    def commit(
        self,
        *,
        article_id: str,
        base_revision_id: str | None,
        base_content_hash: str | None,
        title: str,
        markdown: str,
        reason: str,
        owner_user_id: str | None = None,
    ) -> dict:
        new_hash = content_hash(markdown)
        article = self.db.get(Article, article_id)

        if article is None:
            if base_revision_id is not None or base_content_hash is not None:
                raise ArticleConflictError(
                    "Article creation cannot use an existing base revision"
                )
            article = Article(
                id=article_id, title=title, markdown=markdown,
                content_hash=new_hash, updated_at=_now(),
                owner_user_id=owner_user_id,
            )
            parent_id = None
            revision_number = 1
            self.db.add(article)
        else:
            if article.owner_user_id is not None and owner_user_id is not None \
                    and article.owner_user_id != owner_user_id:
                raise ArticlePermissionError("article owned by another user")
            if (
                article.current_revision_id != base_revision_id
                or article.content_hash != base_content_hash
            ):
                raise ArticleConflictError("Article changed after this operation started")
            if article.content_hash == new_hash and article.title == title:
                # 内容与标题都没变：不产生空版本
                return self._state(article, markdown)
            last = self.db.scalar(
                select(func.max(ArticleRevision.revision_number)).where(
                    ArticleRevision.article_id == article_id
                )
            )
            revision_number = (last or 0) + 1
            parent_id = article.current_revision_id
            article.title = title
            article.markdown = markdown
            article.content_hash = new_hash
            article.updated_at = _now()

        revision = ArticleRevision(
            id=uuid4().hex,
            article_id=article_id,
            revision_number=revision_number,
            parent_revision_id=parent_id,
            title=title,
            markdown=markdown,
            content_hash=new_hash,
            reason=reason,
        )
        self.db.add(revision)
        article.current_revision_id = revision.id
        self.db.commit()
        self.db.refresh(article)
        return self._state(article, markdown)

    def read(self, article_id: str, owner_user_id: str | None = None) -> dict | None:
        article = self.db.get(Article, article_id)
        if article is None or (owner_user_id and article.owner_user_id is not None and article.owner_user_id != owner_user_id):
            return None
        return self._state(article, article.markdown)

    def list(self, owner_user_id: str | None = None) -> list[dict]:
        query = select(Article).order_by(Article.updated_at.desc())
        if owner_user_id:
            from sqlalchemy import or_

            query = query.where(or_(
                Article.owner_user_id == owner_user_id,
                Article.owner_user_id.is_(None),
            ))
        articles = self.db.scalars(query).all()
        return [self._state(a, a.markdown) for a in articles]

    def list_revisions(self, article_id: str, owner_user_id: str | None = None) -> list[dict] | None:
        article = self.db.get(Article, article_id)
        if article is None or (owner_user_id and article.owner_user_id is not None and article.owner_user_id != owner_user_id):
            return None
        revisions = self.db.scalars(
            select(ArticleRevision)
            .where(ArticleRevision.article_id == article_id)
            .order_by(ArticleRevision.revision_number.desc())
        ).all()
        return [
            {
                "articleId": r.article_id,
                "revisionId": r.id,
                "revisionNumber": r.revision_number,
                "parentRevisionId": r.parent_revision_id,
                "title": r.title,
                "contentHash": r.content_hash,
                "createdAt": r.created_at.isoformat(),
                "reason": r.reason,
                "isCurrent": r.id == article.current_revision_id,
            }
            for r in revisions
        ]

    def read_revision(self, article_id: str, revision_id: str, owner_user_id: str | None = None) -> dict | None:
        r = self.db.get(ArticleRevision, revision_id)
        if r is None or r.article_id != article_id:
            return None
        article = self.db.get(Article, article_id)
        if article is None or (owner_user_id and article.owner_user_id is not None and article.owner_user_id != owner_user_id):
            return None
        return {
            "articleId": r.article_id,
            "revisionId": r.id,
            "revisionNumber": r.revision_number,
            "parentRevisionId": r.parent_revision_id,
            "title": r.title,
            "markdown": r.markdown,
            "contentHash": r.content_hash,
            "createdAt": r.created_at.isoformat(),
            "reason": r.reason,
            "isCurrent": article is not None and r.id == article.current_revision_id,
        }

    def restore_revision(self, article_id: str, revision_id: str, owner_user_id: str | None = None) -> dict | None:
        """恢复 = 以旧版本内容提交一个新版本（与蓝本一致，不改历史）。"""
        target = self.read_revision(article_id, revision_id, owner_user_id)
        if target is None:
            return None
        current = self.read(article_id)
        if current and current["currentRevisionId"] == revision_id:
            return current
        return self.commit(
            article_id=article_id,
            base_revision_id=current["currentRevisionId"] if current else None,
            base_content_hash=current["contentHash"] if current else None,
            title=target["title"],
            markdown=target["markdown"],
            reason=f"restore revision {revision_id}",
            owner_user_id=owner_user_id,
        )

    @staticmethod
    def _state(article: Article, markdown: str) -> dict:
        return {
            "articleId": article.id,
            "title": article.title,
            "currentRevisionId": article.current_revision_id,
            "contentHash": article.content_hash,
            "markdown": markdown,
            "updatedAt": article.updated_at.isoformat() if article.updated_at else None,
            "ownerId": article.owner_user_id,
        }
