"""模型档案（model-profile）API 与解析测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.settings_profile import ModelProfile
from app.services.model_profile_service import resolve_llm_config


@pytest.fixture()
def profile_engine():
    """StaticPool 内存库：TestClient 工作线程与主线程共享同一连接。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(profile_engine):
    test_sessionmaker = sessionmaker(bind=profile_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_profile_crud_and_activation(client):
    # 初始为空：走全局配置
    res = client.get("/api/settings/profiles")
    assert res.status_code == 200
    assert res.json() == {"profiles": []}

    # 创建第一个档案：自动成为默认
    res = client.post(
        "/api/settings/profiles",
        json={
            "name": "DeepSeek 官方",
            "baseUrl": "https://api.deepseek.com/v1",
            "modelId": "deepseek-chat",
        },
    )
    assert res.status_code == 201
    first = res.json()
    assert first["isDefault"] is True
    assert first["keyConfigured"] is False  # 密钥本体不在环境里，档案只存变量名

    # 创建第二个档案：不自动默认
    res = client.post(
        "/api/settings/profiles",
        json={
            "name": "SiliconFlow",
            "baseUrl": "https://api.siliconflow.cn/v1",
            "modelId": "Qwen/Qwen2.5-72B-Instruct",
        },
    )
    second = res.json()
    assert second["isDefault"] is False

    # 激活第二个
    res = client.post(f"/api/settings/profiles/{second['id']}/activate")
    assert res.status_code == 200
    assert res.json()["isDefault"] is True

    # 激活状态互斥
    statuses = {p["name"]: p["isDefault"] for p in client.get("/api/settings/profiles").json()["profiles"]}
    assert statuses == {"DeepSeek 官方": False, "SiliconFlow": True}

    # 更新
    res = client.patch(
        f"/api/settings/profiles/{second['id']}",
        json={"timeoutSeconds": 60},
    )
    assert res.status_code == 200
    assert res.json()["timeoutSeconds"] == 60

    # 删除默认档案后自动回落到剩余最新档案
    res = client.delete(f"/api/settings/profiles/{second['id']}")
    assert res.status_code == 204
    profiles = client.get("/api/settings/profiles").json()["profiles"]
    assert len(profiles) == 1
    assert profiles[0]["isDefault"] is True

    # 同名冲突 409
    res = client.post(
        "/api/settings/profiles",
        json={"name": "DeepSeek 官方", "baseUrl": "https://x/v1", "modelId": "m"},
    )
    assert res.status_code == 409


def test_resolve_llm_config_prefers_active_profile(profile_engine):
    import app.services.model_profile_service as svc
    from app.services import secret_store

    # 注入测试 session 工厂
    from sqlalchemy.orm import sessionmaker as _sm

    test_factory = _sm(bind=profile_engine)
    svc.SessionLocal = lambda: test_factory()

    session = _sm(bind=profile_engine)()
    profile = ModelProfile(
        id="mp-test",
        name="测试档案",
        base_url="https://profile.example/v1",
        model_id="profile-model",
        timeout_seconds=30,
        is_default=True,
    )
    session.add(profile)
    session.commit()

    secret_store.set_secret(
        session, secret_store.profile_secret_id("mp-test"), "pk-test-123"
    )
    config = resolve_llm_config()
    assert config["profileId"] == "mp-test"
    assert config["base_url"] == "https://profile.example/v1"
    assert config["model"] == "profile-model"
    assert config["api_key"] == "pk-test-123"
    assert config["keySource"] == "db"
    assert config["timeout_seconds"] == 30

    # 档案密钥删除后，没有全局数据库密钥就是未配置。
    secret_store.delete_secret(session, secret_store.profile_secret_id("mp-test"))
    config = resolve_llm_config()
    assert config["api_key"] == ""
    assert config["keySource"] == "none"
    session.close()
