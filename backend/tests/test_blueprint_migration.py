"""蓝本后端迁移测试：文章存储乐观并发 + 发布 outbox 状态机。

使用 SQLite 内存库（测试专用），只测服务层语义，不依赖 MySQL。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.article import Article, ArticleRevision
from app.models.publishing import (
    PublishAttempt,
    PublishJob,
    PublishPlan,
    PublishReceipt,
    PublishVariant,
)
from app.services.article_store import ArticleConflictError, ArticleStore
from app.services.publish_outbox import PublishOutboxService, recover_interrupted


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    session = factory()
    yield session
    session.close()


# ---------- ArticleStore ----------


def test_article_create_and_update_versions(db):
    store = ArticleStore(db)
    first = store.commit(
        article_id="a1", base_revision_id=None, base_content_hash=None,
        title="v1 title", markdown="# hello", reason="create",
    )
    assert first["currentRevisionId"] is not None
    assert first["contentHash"].startswith("sha256:")

    second = store.commit(
        article_id="a1", base_revision_id=first["currentRevisionId"],
        base_content_hash=first["contentHash"],
        title="v2 title", markdown="# hello world", reason="edit",
    )
    revisions = store.list_revisions("a1")
    assert len(revisions) == 2
    assert revisions[0]["isCurrent"] is True
    assert revisions[0]["parentRevisionId"] == first["currentRevisionId"]
    assert second["currentRevisionId"] != first["currentRevisionId"]


def test_article_optimistic_concurrency_conflict(db):
    store = ArticleStore(db)
    first = store.commit(
        article_id="a2", base_revision_id=None, base_content_hash=None,
        title="t", markdown="one", reason="create",
    )
    store.commit(
        article_id="a2", base_revision_id=first["currentRevisionId"],
        base_content_hash=first["contentHash"],
        title="t", markdown="two", reason="second",
    )
    # 用旧 base 提交：必须冲突（蓝本 ARTICLE_CONFLICT 语义）
    with pytest.raises(ArticleConflictError):
        store.commit(
            article_id="a2", base_revision_id=first["currentRevisionId"],
            base_content_hash=first["contentHash"],
            title="t", markdown="three", reason="stale",
        )


def test_article_restore_creates_new_revision(db):
    store = ArticleStore(db)
    v1 = store.commit(
        article_id="a3", base_revision_id=None, base_content_hash=None,
        title="t", markdown="one", reason="create",
    )
    store.commit(
        article_id="a3", base_revision_id=v1["currentRevisionId"],
        base_content_hash=v1["contentHash"],
        title="t", markdown="two", reason="edit",
    )
    restored = store.restore_revision("a3", v1["currentRevisionId"])
    assert restored["markdown"] == "one"
    revisions = store.list_revisions("a3")
    assert len(revisions) == 3
    # 历史不可变：v1 仍是 v1
    detail = store.read_revision("a3", v1["currentRevisionId"])
    assert detail["markdown"] == "one"


# ---------- PublishOutboxService ----------


def _make_plan(db, service):
    store = ArticleStore(db)
    article = store.commit(
        article_id="pub-1", base_revision_id=None, base_content_hash=None,
        title="发布测试", markdown="# body", reason="create",
    )
    plan = service.create_plan(
        revision_id=article["currentRevisionId"], title="发布测试",
        markdown="# body",
        targets=[{"platform": "twitter", "accountRef": "@me", "deliveryMode": "dry_run"}],
    )
    return plan


def test_publish_full_flow_dry_run(db):
    service = PublishOutboxService(db)
    plan = _make_plan(db, service)
    assert plan["status"] == "draft"
    assert plan["approvalStatus"] == "pending"

    approved = service.approve(plan["planId"], "user:web")
    assert approved["approvalStatus"] == "approved"
    assert approved["approvalBindingHash"] is not None

    queued = service.enqueue(plan["planId"])
    assert queued["status"] == "queued"
    assert len(queued["jobs"]) == 1
    job = queued["jobs"][0]
    assert job["state"] == "pending"
    assert job["idempotencyKey"].startswith("sha256:")

    done = service.process(job["id"])
    assert done["status"] == "completed"
    assert done["jobs"][0]["state"] == "succeeded"
    assert done["jobs"][0]["remoteId"].startswith("dry-run:")


def test_publish_enqueue_requires_approval(db):
    service = PublishOutboxService(db)
    plan = _make_plan(db, service)
    with pytest.raises(PublishPlanError := __import__(
        "app.services.publish_outbox", fromlist=["PublishPlanError"]
    ).PublishPlanError):
        service.enqueue(plan["planId"])


def test_publish_idempotent_enqueue(db):
    service = PublishOutboxService(db)
    plan = _make_plan(db, service)
    service.approve(plan["planId"], "user:web")
    first = service.enqueue(plan["planId"])
    second = service.enqueue(plan["planId"])
    assert len(first["jobs"]) == 1
    assert len(second["jobs"]) == 1
    assert first["jobs"][0]["id"] == second["jobs"][0]["id"]


def test_recovery_marks_in_progress_unknown(db):
    service = PublishOutboxService(db)
    plan = _make_plan(db, service)
    service.approve(plan["planId"], "user:web")
    queued = service.enqueue(plan["planId"])
    job_id = queued["jobs"][0]["id"]

    # 模拟 runtime 崩溃：job 卡在 in_progress，attempt 卡在 in_progress
    job = db.get(PublishJob, job_id)
    job.state = "in_progress"
    db.add(PublishAttempt(
        id="attempt:x", job_id=job_id, attempt_number=1,
        operation="dry_run", state="in_progress", request_json="{}",
        started_at=job.created_at,
    ))
    db.commit()

    recover_interrupted(db)

    refreshed = service.get_plan(plan["planId"])
    assert refreshed["status"] == "needs_attention"
    assert refreshed["jobs"][0]["state"] == "unknown"
    assert refreshed["jobs"][0]["reconcileRequired"] is True

    # dry_run 可核验成功
    reconciled = service.reconcile(job_id)
    assert reconciled["jobs"][0]["state"] == "succeeded"


def test_resolve_unknown_draft_missing_allows_retry(db):
    service = PublishOutboxService(db)

    class NeverReconcile:
        def deliver(self, **kwargs):
            raise __import__(
                "app.services.publish_outbox", fromlist=["PublishPlanError"]
            ).PublishPlanError("timeout, outcome unknown")

        def reconcile(self, **kwargs):
            return None

    flaky = PublishOutboxService(db, delivery=NeverReconcile())
    plan = _make_plan(db, service)
    service.approve(plan["planId"], "user:web")
    queued = service.enqueue(plan["planId"])
    job_id = queued["jobs"][0]["id"]

    # 用 flaky delivery 处理 → failed_terminal？不：PublishPlanError 走 failed_terminal。
    # 真实 unknown 场景由 recovery 制造：
    job = db.get(PublishJob, job_id)
    job.state = "in_progress"
    db.commit()
    recover_interrupted(db)

    # 用户确认草稿其实没建 → 回到 pending 可重试
    resolved = service.resolve_unknown(job_id, "draft_missing")
    assert resolved["jobs"][0]["state"] == "pending"

    # 换正常 delivery 重试成功
    ok = service.process(job_id)
    assert ok["jobs"][0]["state"] == "succeeded"
