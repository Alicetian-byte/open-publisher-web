"""revisions API 集成测试：版本历史查询 + 用户编辑保存新版本。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_revision_crud_flow(client: TestClient):
    # 先创建一个项目
    res = client.post("/api/projects", json={"name": "Test Product"})
    assert res.status_code == 201
    project_id = res.json()["id"]

    # 项目初始无版本
    res = client.get(f"/api/projects/{project_id}/revisions")
    assert res.status_code == 200
    assert res.json() == []

    # 用户编辑保存第一条
    res = client.post(
        f"/api/projects/{project_id}/revisions",
        json={"content": "第一版内容", "platform": "twitter", "tone": "casual"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["version"] == 1
    assert body["source"] == "user_edited"
    first_id = body["id"]

    # 再保存第二条，版本号自增
    res = client.post(
        f"/api/projects/{project_id}/revisions",
        json={"content": "第二版内容"},
    )
    assert res.status_code == 201
    assert res.json()["version"] == 2

    # 版本历史新版本在前
    res = client.get(f"/api/projects/{project_id}/revisions")
    assert res.status_code == 200
    versions = [r["version"] for r in res.json()]
    assert versions == [2, 1]

    # 单条查询
    res = client.get(f"/api/revisions/{first_id}")
    assert res.status_code == 200
    assert res.json()["content"] == "第一版内容"

    # 空内容应被拒绝
    res = client.post(f"/api/projects/{project_id}/revisions", json={"content": ""})
    assert res.status_code == 422

    # 404
    res = client.get("/api/revisions/nonexistent")
    assert res.status_code == 404


class FakeOptimizeLLM:
    """AI 优化端点的测试替身。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    api_key_configured = True

    def complete_json(self, system: str, user: str, *, temperature: float = 0.7) -> dict:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        return {"content": "优化后的推文内容。", "notes": "更精简了"}


class FakeNoKeyLLM:
    api_key_configured = False


def test_optimize_revision_flow(client: TestClient):
    import app.api.revisions as revisions_mod

    fake = FakeOptimizeLLM()
    app.dependency_overrides[revisions_mod.get_llm_client] = lambda: fake
    try:
        res = client.post("/api/projects", json={"name": "Opt Product"})
        project_id = res.json()["id"]
        res = client.post(
            f"/api/projects/{project_id}/revisions",
            json={"content": "原始推文", "platform": "twitter", "tone": "casual"},
        )
        revision_id = res.json()["id"]

        # 正常优化：产出新版本
        res = client.post(
            f"/api/revisions/{revision_id}/optimize",
            json={"direction": "shorter"},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["version"] == 2
        assert body["source"] == "ai_optimized"
        assert body["content"] == "优化后的推文内容。"
        assert body["platform"] == "twitter"
        assert len(fake.calls) == 1

        # 未知方向：422 且不调用 LLM
        res = client.post(
            f"/api/revisions/{revision_id}/optimize",
            json={"direction": "nope"},
        )
        assert res.status_code == 422
        assert len(fake.calls) == 1

        # 404
        res = client.post(
            "/api/revisions/nonexistent/optimize",
            json={"direction": "shorter"},
        )
        assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(revisions_mod.get_llm_client, None)


def test_optimize_requires_llm_key(client: TestClient):
    import app.api.revisions as revisions_mod

    app.dependency_overrides[revisions_mod.get_llm_client] = lambda: FakeNoKeyLLM()
    try:
        res = client.post("/api/projects", json={"name": "NoKey Product"})
        project_id = res.json()["id"]
        res = client.post(
            f"/api/projects/{project_id}/revisions",
            json={"content": "原始推文"},
        )
        revision_id = res.json()["id"]

        res = client.post(
            f"/api/revisions/{revision_id}/optimize",
            json={"direction": "shorter"},
        )
        assert res.status_code == 503
    finally:
        app.dependency_overrides.pop(revisions_mod.get_llm_client, None)
