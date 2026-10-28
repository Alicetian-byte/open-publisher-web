"""微信发布通道测试：凭据加密 + Markdown→HTML + API mock。"""

import json
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.publish_outbox import PublishOutboxService, PublishPlanError
from app.services.wechat_publisher import (
    WeChatOfficialDelivery,
    load_credentials,
    save_credentials,
    clear_credentials,
    markdown_to_wechat_html,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def test_credentials_roundtrip(db):
    assert not load_credentials(db).configured
    save_credentials(db, app_id="wx123", app_secret="sec456")
    creds = load_credentials(db)
    assert creds.configured
    assert creds.app_id == "wx123"
    clear_credentials(db)
    assert not load_credentials(db).configured


def test_markdown_to_html():
    html = markdown_to_wechat_html("# Title\n\n**bold** and *italic*\n\n- a\n- b\n\n> quote\n\n---")
    assert "<h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<li>a</li>" in html
    assert "<blockquote" in html
    assert "<hr" in html


def test_markdown_image_and_link():
    html = markdown_to_wechat_html("![alt text](https://example.com/img.png)\n\n[click](https://example.com)")
    assert '<img src="https://example.com/img.png"' in html
    assert '<a href="https://example.com">' in html


def test_deliver_without_credentials_raises(db):
    delivery = WeChatOfficialDelivery(db)
    with pytest.raises(PublishPlanError, match="凭据未配置"):
        delivery.deliver(
            idempotency_key="test-key", platform="weixin", account_ref="",
            title="Test", markdown="# Hello", mode="wechat_sync_draft",
        )


def test_deliver_unsupported_platform(db):
    save_credentials(db, app_id="wx123", app_secret="sec456")
    delivery = WeChatOfficialDelivery(db)
    with pytest.raises(PublishPlanError, match="只支持 weixin"):
        delivery.deliver(
            idempotency_key="test-key", platform="xiaohongshu", account_ref="",
            title="Test", markdown="# Hello", mode="wechat_sync_draft",
        )


def test_deliver_creates_draft(db, monkeypatch):
    save_credentials(db, app_id="wx123", app_secret="sec456")
    delivery = WeChatOfficialDelivery(db)

    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "fake-token", "expires_in": 7200}
    mock_token_response.raise_for_status = MagicMock()

    mock_draft_response = MagicMock()
    mock_draft_response.json.return_value = {"media_id": "draft-media-123"}
    mock_draft_response.raise_for_status = MagicMock()

    def mock_post(url, **kwargs):
        if "/draft/add" in url:
            return mock_draft_response
        raise ValueError(f"unexpected POST {url}")

    monkeypatch.setattr("httpx.get", lambda *a, **kw: mock_token_response)
    monkeypatch.setattr("httpx.post", mock_post)

    result = delivery.deliver(
        idempotency_key="test-key", platform="weixin", account_ref="test-author",
        title="测试文章", markdown="# 测试标题\n\n正文内容", mode="wechat_sync_draft",
    )
    assert result["remoteId"] == "draft-media-123"
    assert result["details"]["draftOnly"] is True


def test_outbox_wechat_mode_end_to_end(db, monkeypatch):
    from app.services.article_store import ArticleStore
    store = ArticleStore(db)
    article = store.commit(
        article_id="article-wx-test", base_revision_id=None, base_content_hash=None,
        title="微信发布测试", markdown="# 微信测试\n\n内容", reason="seed",
    )
    save_credentials(db, app_id="wx123", app_secret="sec456")

    service = PublishOutboxService(db)
    plan = service.create_plan(
        revision_id=article["currentRevisionId"], title="微信发布测试",
        markdown="# 微信测试\n\n内容",
        targets=[{"platform": "weixin", "accountRef": "test-author",
                  "deliveryMode": "wechat_sync_draft"}],
    )
    assert plan["status"] == "draft"

    plan = service.approve(plan["planId"], "test-user")
    assert plan["approvalStatus"] == "approved"

    plan = service.enqueue(plan["planId"])
    assert plan["status"] == "queued"
    assert len(plan["jobs"]) == 1
    assert plan["jobs"][0]["operation"] == "wechat_sync_draft"

    # Mock the WeChat API calls
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "fake-token", "expires_in": 7200}
    mock_token_response.raise_for_status = MagicMock()
    mock_draft_response = MagicMock()
    mock_draft_response.json.return_value = {"media_id": "wx-draft-abc"}
    mock_draft_response.raise_for_status = MagicMock()
    monkeypatch.setattr("httpx.get", lambda *a, **kw: mock_token_response)
    monkeypatch.setattr("httpx.post", lambda *a, **kw: mock_draft_response)

    plan = service.process(plan["jobs"][0]["id"])
    assert plan["jobs"][0]["state"] == "succeeded"
    assert plan["jobs"][0]["remoteId"] == "wx-draft-abc"
