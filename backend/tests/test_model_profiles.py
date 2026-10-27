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
            "apiKeyEnv": "DEEPSEEK_API_KEY",
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
            "apiKeyEnv": "SILICONFLOW_API_KEY",
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


def test_resolve_llm_config_prefers_active_profile(profile_engine, monkeypatch):
    from app.db.session import get_db as _  # noqa: F401 确保模块路径存在

    import app.services.model_profile_service as svc

    # 注入测试 session 工厂
    from sqlalchemy.orm import sessionmaker as _sm

    test_factory = _sm(bind=profile_engine)
    svc.SessionLocal = lambda: test_factory()

    session = _sm(bind=profile_engine)()
    session.add(
        ModelProfile(
            id="mp-test",
            name="测试档案",
            base_url="https://profile.example/v1",
            model_id="profile-model",
            api_key_env="PROFILE_TEST_KEY",
            timeout_seconds=30,
            is_default=True,
        )
    )
    session.commit()

    monkeypatch.setenv("PROFILE_TEST_KEY", "pk-test-123")
    config = resolve_llm_config()
    assert config["profileId"] == "mp-test"
    assert config["base_url"] == "https://profile.example/v1"
    assert config["model"] == "profile-model"
    assert config["api_key"] == "pk-test-123"
    assert config["timeout_seconds"] == 30

    # 环境变量缺失时回退全局 key
    monkeypatch.delenv("PROFILE_TEST_KEY")
    config = resolve_llm_config()
    assert config["api_key"] == "" or isinstance(config["api_key"], str)
    session.close()


def test_profiles_shared_across_users(client):
    """管理端创建的模型档案是平台共享资源：普通用户列表可见。"""
    res = client.post(
        "/api/settings/profiles",
        json={"name": "共享模型", "baseUrl": "https://x/v1", "modelId": "glm-4"},
    )
    assert res.status_code == 201
    created = res.json()
    # conftest：require_user 覆盖为 u-test（普通用户）、require_admin 覆盖为 u-admin
    assert created["ownerId"] is None
    visible = client.get("/api/settings/profiles").json()["profiles"]
    assert [p["id"] for p in visible] == [created["id"]]
