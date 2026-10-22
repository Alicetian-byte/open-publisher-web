"""管理员旧数据 owner 回填 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.article import Article
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
    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seed(factory):
    with factory() as db:
        ArticleStore(db).commit(
            article_id="orphan-article", base_revision_id=None,
            base_content_hash=None, title="旧文章",
            markdown="# 旧文章", reason="seed",
        )
        db.add(MediaAsset(
            id="orphan-media", name="旧素材", alt="", visual_description="",
            usage_hint="", generation_prompt="", tags=[], description_source="manual",
            mime="image/png", source="data:image/png;base64,iVBORw0KGgo=", origin="upload",
        ))
        db.commit()


def test_claim_orphans_and_summary(client, factory, seed):
    summary = client.get("/api/admin/ownership/orphans").json()
    assert summary["articles"] == 1
    assert summary["mediaAssets"] == 1

    claimed = client.post("/api/admin/ownership/claim-orphans", json={}).json()
    assert claimed["ownerUserId"] == "u-admin"
    assert claimed["claimed"]["articles"] == 1
    assert claimed["claimed"]["mediaAssets"] == 1

    with factory() as db:
        assert db.get(Article, "orphan-article").owner_user_id == "u-admin"
        assert db.get(MediaAsset, "orphan-media").owner_user_id == "u-admin"

    summary = client.get("/api/admin/ownership/orphans").json()
    assert summary["articles"] == 0
    assert summary["mediaAssets"] == 0
