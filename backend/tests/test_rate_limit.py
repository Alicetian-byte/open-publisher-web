"""登录限流与令牌有效期（安全加固）测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import rate_limit
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import get_settings


def test_token_expiry_default_reduced_to_2h():
    assert get_settings().access_token_expire_minutes == 120


def test_login_rate_limit_blocks_after_threshold(client, monkeypatch):
    rate_limit._attempts.clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "login_rate_limit_max", 3)
    for _ in range(3):
        res = client.post(
            "/api/auth/login",
            json={"username": "no-such-user", "password": "wrong-password"},
        )
        assert res.status_code == 401
    blocked = client.post(
        "/api/auth/login",
        json={"username": "no-such-user", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    rate_limit._attempts.clear()

@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessionmaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
