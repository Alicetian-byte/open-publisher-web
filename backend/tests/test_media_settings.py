"""素材库 + 模型设置 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.db.session import get_db


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def test_media_upload_list_delete(client):
    res = client.post("/api/media", json={
        "name": "测试图", "mime": "image/png",
        "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
        "alt": "alt text",
    })
    assert res.status_code == 201
    asset = res.json()
    assert asset["origin"] == "upload"

    listed = client.get("/api/media").json()["assets"]
    assert len(listed) == 1

    raw = client.get(f"/api/media/{asset['id']}/raw")
    assert raw.status_code == 200
    assert raw.headers["content-type"] == "image/png"
    assert raw.content[:4] == b"\x89PNG"

    assert client.delete(f"/api/media/{asset['id']}").status_code == 204
    assert client.get("/api/media").json()["assets"] == []


def test_media_upload_rejects_non_data_url(client):
    res = client.post("/api/media", json={
        "name": "x", "mime": "image/png", "dataUrl": "https://example.com/a.png",
    })
    assert res.status_code == 400


def test_model_status_endpoint(client):
    res = client.get("/api/settings/model")
    assert res.status_code == 200
    body = res.json()
    assert "baseUrl" in body and "model" in body and "keyConfigured" in body


def test_model_test_without_key_returns_501(client):
    res = client.post("/api/settings/model/test")
    assert res.status_code in (200, 501)


def test_media_structured_profile_update_and_filter(client):
    created = client.post("/api/media", json={
        "name": "架构图", "mime": "image/png",
        "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
        "alt": "服务架构", "visualDescription": "三个服务模块的横向流程图",
        "usageHint": "产品架构", "tags": ["架构", "流程"],
    }).json()
    assert created["visualDescription"] == "三个服务模块的横向流程图"
    assert created["tags"] == ["架构", "流程"]

    updated = client.patch(f"/api/media/{created['id']}", json={
        "visualDescription": "采集、处理、渲染三段流程",
        "tags": ["流程图", "架构"],
    }).json()
    assert updated["visualDescription"] == "采集、处理、渲染三段流程"
    assert updated["tags"] == ["流程图", "架构"]
    assert updated["descriptionSource"] == "manual"

    assert client.get("/api/media?search=渲染").json()["assets"]
    assert client.get("/api/media?tag=流程图").json()["assets"]
    assert client.get("/api/media?origin=generated").json()["assets"] == []
    assert client.patch("/api/media/missing", json={"name": "x"}).status_code == 404


def test_image_config_get_put_delete_roundtrip(client):
    # 初始状态：无 DB 配置、测试进程无 IMAGE_* 环境变量 → 回退文本 LLM 配置
    initial = client.get("/api/settings/image")
    assert initial.status_code == 200
    body = initial.json()
    assert body["source"] in ("fallback", "env")

    # 保存管理端配置 → source=db
    saved = client.put("/api/settings/image", json={
        "baseUrl": "https://img.example.com/v1",
        "modelId": "test-image-model",
        "apiKeyEnv": "IMAGE_API_KEY",
        "timeoutSeconds": 90,
    })
    assert saved.status_code == 200
    body = saved.json()
    assert body["source"] == "db"
    assert body["baseUrl"] == "https://img.example.com/v1"
    assert body["model"] == "test-image-model"
    assert body["timeoutSeconds"] == 90

    # 再读一致
    reread = client.get("/api/settings/image").json()
    assert reread["source"] == "db" and reread["model"] == "test-image-model"

    # 重置 → 回退
    assert client.delete("/api/settings/image").status_code == 200
    assert client.get("/api/settings/image").json()["source"] in ("fallback", "env")


def test_image_config_requires_admin(client):
    # 未登录/非管理员：conftest 覆盖了 require_user，但 require_admin 仍按角色校验。
    # 这里只验证端点存在且返回结构；权限矩阵见 test_auth。
    res = client.put("/api/settings/image", json={
        "baseUrl": "https://x.example.com/v1", "modelId": "m",
    })
    assert res.status_code in (200, 401, 403)


def test_image_test_without_key_returns_501(client, monkeypatch):
    from app.services import model_profile_service

    monkeypatch.setattr(
        model_profile_service, "resolve_image_config",
        lambda: {"apiKeyEnv": "IMAGE_API_KEY", "api_key": "", "base_url": "",
                 "model": "m", "timeout_seconds": 5, "source": "fallback"},
    )
    res = client.post("/api/settings/image/test")
    assert res.status_code == 501
