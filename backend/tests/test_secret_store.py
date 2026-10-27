"""企业级密钥存储（app_secrets + secret_store）单元与 API 测试。"""

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import secret_box
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.settings_profile import ModelProfile
from app.services import secret_store


@pytest.fixture()
def secret_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(secret_engine):
    test_sessionmaker = sessionmaker(bind=secret_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_encrypt_decrypt_roundtrip():
    token = secret_box.encrypt("sk-test-abcdef123456")
    assert token != "sk-test-abcdef123456"
    assert "sk-test" not in token
    assert secret_box.decrypt(token) == "sk-test-abcdef123456"


def test_mask_keeps_last_four():
    assert secret_box.mask("sk-1234567890") == "****7890"
    assert secret_box.mask("abc") == "****"
    assert secret_box.mask("") == ""


def test_set_get_delete_with_audit(secret_engine):
    factory = sessionmaker(bind=secret_engine)
    with factory() as db:
        secret_store.set_secret(db, secret_store.SECRET_ID_LLM_GLOBAL, "sk-roundtrip-9999", actor="u-admin")
        assert secret_store.get_secret(db, secret_store.SECRET_ID_LLM_GLOBAL) == "sk-roundtrip-9999"
        meta = secret_store.get_secret_meta(db, secret_store.SECRET_ID_LLM_GLOBAL)
        assert meta is not None
        assert meta["keyHint"] == "****9999"
        assert meta["keyVersion"] == 1

        # 覆盖更新：版本自增
        secret_store.set_secret(db, secret_store.SECRET_ID_LLM_GLOBAL, "sk-rotated-8888", actor="u-admin")
        meta = secret_store.get_secret_meta(db, secret_store.SECRET_ID_LLM_GLOBAL)
        assert meta["keyVersion"] == 2
        assert secret_store.get_secret(db, secret_store.SECRET_ID_LLM_GLOBAL) == "sk-rotated-8888"

        from app.models.app_secret import SecretAudit
        actions = [a.action for a in db.query(SecretAudit).filter(
            SecretAudit.secret_id == secret_store.SECRET_ID_LLM_GLOBAL).all()]
        assert actions == ["set", "set"]

        # 删除并回退
        assert secret_store.delete_secret(db, secret_store.SECRET_ID_LLM_GLOBAL, actor="u-admin") is True
        assert secret_store.get_secret(db, secret_store.SECRET_ID_LLM_GLOBAL) is None
        actions = [a.action for a in db.query(SecretAudit).filter(
            SecretAudit.secret_id == secret_store.SECRET_ID_LLM_GLOBAL).all()]
        assert actions == ["set", "set", "delete"]


def test_decrypt_failure_falls_back_to_none(secret_engine, monkeypatch):
    factory = sessionmaker(bind=secret_engine)
    with factory() as db:
        secret_store.set_secret(db, "llm:global", "sk-will-orphan")
    # 换一个随机主密钥，模拟主密钥轮换后旧密文不可解
    monkeypatch.setattr(secret_box, "get_fernet", lambda: Fernet(Fernet.generate_key()))
    with factory() as db:
        assert secret_store.get_secret(db, "llm:global") is None


def test_profile_resolution_prefers_db_secret(secret_engine):
    factory = sessionmaker(bind=secret_engine)
    with factory() as db:
        profile = ModelProfile(
            id="mp-sectest",
            name="DB Key Profile",
            provider="custom",
            base_url="https://api.example.com/v1",
            model_id="test-model",
            timeout_seconds=30,
            is_default=True,
        )
        db.add(profile)
        db.commit()

        # 未录入密钥：无数据库密钥 → keySource none
        resolved = secret_store  # noqa: F841 - 占位保持可读
        from app.services.model_profile_service import resolve_llm_profile_config
        config = resolve_llm_profile_config(db, profile_id="mp-sectest")
        assert config["keySource"] == "none"

        # 录入 DB 密钥后按档案密钥解析
        secret_store.set_secret(db, secret_store.profile_secret_id("mp-sectest"), "sk-from-db-7777")
        config = resolve_llm_profile_config(db, profile_id="mp-sectest")
        assert config["api_key"] == "sk-from-db-7777"
        assert config["keySource"] == "db"
        assert config["keyHint"] == "****7777"


def test_key_api_endpoints_mask_plaintext(client, secret_engine):
    # 录入
    res = client.put("/api/settings/llm/key", json={"apiKey": "sk-enterprise-4242"})
    assert res.status_code == 200
    body = res.json()
    assert body["keyConfigured"] is True
    assert body["keySource"] == "db"
    assert body["keyHint"] == "****4242"
    assert "sk-enterprise" not in res.text

    # 更新（版本自增）
    res = client.put("/api/settings/llm/key", json={"apiKey": "sk-enterprise-4243"})
    assert res.json()["keyVersion"] == 2

    # 档案密钥
    res = client.post("/api/settings/profiles", json={
        "name": "Profile With Key", "baseUrl": "https://api.example.com/v1", "modelId": "m1",
    })
    assert res.status_code == 201
    pid = res.json()["id"]
    assert res.json()["keyConfigured"] is False
    res = client.put(f"/api/settings/profiles/{pid}/key", json={"apiKey": "sk-profile-1111"})
    assert res.json()["keySource"] == "db"
    assert "sk-profile" not in res.text
    res = client.get("/api/settings/profiles")
    target = next(p for p in res.json()["profiles"] if p["id"] == pid)
    assert target["keyConfigured"] is True and target["keyHint"] == "****1111"

    # 删除回退
    res = client.delete(f"/api/settings/profiles/{pid}/key")
    assert res.json()["keyConfigured"] is False
    res = client.delete("/api/settings/llm/key")
    assert res.json()["keyConfigured"] is False


def test_key_api_requires_minimum_length(client):
    res = client.put("/api/settings/llm/key", json={"apiKey": "ab"})
    assert res.status_code == 422
