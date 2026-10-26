"""owner_user_id 隔离审计回归（F-013）：

- 他人文章：读 404、写/恢复 403。
- 共享文章（owner NULL）：登录用户可读可写（历史共享协作规则）。
- 他人素材：列表不可见、详情/原图 404。
- 共享素材：所有人可读；写操作仅管理员，普通用户 403。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import require_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.media import MediaAsset
from app.services.article_store import ArticleStore


@pytest.fixture()
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture()
def client(factory):
    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login_as(client, user_id, role="user"):
    app.dependency_overrides[require_user] = lambda: type(
        "TestUser", (), {"id": user_id, "role": role},
    )()


def _media(owner):
    return MediaAsset(
        id=f"media-{owner or 'shared'}", name="素材", alt="",
        visual_description="", usage_hint="", generation_prompt="",
        tags=[], description_source="manual", mime="image/png",
        source="data:image/png;base64,iVBORw0KGgo=", origin="upload",
        owner_user_id=owner,
    )


def test_owned_article_isolated_across_users(client, factory):
    with factory() as db:
        store = ArticleStore(db)
        store.commit(article_id="a-owned", base_revision_id=None,
                     base_content_hash=None, title="A 的文章",
                     markdown="# A", reason="seed", owner_user_id="u-a")
        db.add(_media("u-a"))
        db.commit()

    # 用户 B：读不到、写不了他人文章
    login_as(client, "u-b")
    assert client.get("/api/articles/a-owned").status_code == 404
    article = None
    with factory() as db:
        article = ArticleStore(db).read("a-owned", "u-a")
    res = client.post("/api/articles", json={
        "articleId": "a-owned",
        "baseRevisionId": article["currentRevisionId"],
        "baseContentHash": article["contentHash"],
        "title": "劫持", "markdown": "# hijack", "reason": "attack",
    })
    assert res.status_code == 403

    # 用户 B 看不到他人素材
    assert client.get("/api/media").json()["assets"] == []
    assert client.get("/api/media/media-u-a/raw").status_code == 404


def test_shared_article_readable_and_writable(client, factory):
    with factory() as db:
        ArticleStore(db).commit(article_id="a-shared", base_revision_id=None,
                                base_content_hash=None, title="共享文章",
                                markdown="# shared", reason="seed")
    login_as(client, "u-b")
    assert client.get("/api/articles/a-shared").status_code == 200


def test_shared_media_readonly_for_users_admin_can_write(client, factory):
    with factory() as db:
        db.add(_media(None))
        db.commit()

    # 普通用户：可读，不可改/删
    login_as(client, "u-b")
    assert client.get("/api/media").json()["assets"][0]["id"] == "media-shared"
    assert client.patch("/api/media/media-shared", json={"alt": "x"}).status_code == 403
    assert client.delete("/api/media/media-shared").status_code == 403

    # 管理员：可以写共享素材
    login_as(client, "u-admin", role="admin")
    assert client.patch("/api/media/media-shared", json={"alt": "管理员改"}).status_code == 200


def test_owned_media_owner_can_write(client, factory):
    with factory() as db:
        db.add(_media("u-b"))
        db.commit()
    login_as(client, "u-b")
    assert client.patch("/api/media/media-u-b", json={"alt": "自己的"}).status_code == 200

