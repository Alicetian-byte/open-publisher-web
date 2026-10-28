"""视觉配图链路测试：规划（素材匹配/生图提示词）+ 应用（插图落新版本）。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.media import MediaAsset
from app.services.article_store import ArticleConflictError, ArticleStore
from app.services.visual_service import VisualService

MARKDOWN = """# 测试文章标题

开篇导语，介绍整体背景。

## 产品架构

系统由三个服务组成，流程从采集到渲染。

## 数据对比

与上一版本相比，导出速度差异明显。

## 结语

持续迭代。
"""


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
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def prevent_visual_planner_network(monkeypatch):
    """单测不允许依赖真实模型；需要模型规划用例会再次覆写此类。"""
    from app.agents import llm_client

    class NoKeyLLM:
        api_key_configured = False

    monkeypatch.setattr(llm_client, "LLMClient", NoKeyLLM)


@pytest.fixture()
def article(factory):
    with factory() as db:
        return ArticleStore(db).commit(
            article_id="article-visual",
            base_revision_id=None,
            base_content_hash=None,
            title="测试文章",
            markdown=MARKDOWN,
            reason="seed",
        )


def _add_asset(factory, *, asset_id: str, alt: str) -> None:
    with factory() as db:
        db.add(MediaAsset(
            id=asset_id, name=f"素材-{asset_id}", alt=alt, usage_hint="",
            mime="image/png", source="data:image/png;base64,iVBORw0KGgo=",
            origin="upload",
        ))
        db.commit()


def test_plan_matches_asset_and_generates_prompts(factory, article):
    _add_asset(factory, asset_id="a-arch", alt="产品架构流程图：服务组成与数据流")
    with factory() as db:
        service = VisualService(db)
        plan = service.plan(
            markdown=MARKDOWN, target_count=2, asset_ids=["a-arch"],
        )

    assert plan["targetCount"] == 2
    assert [p["id"] for p in plan["placements"]] == ["illustration-1", "illustration-2"]
    architecture = plan["placements"][0]
    assert architecture["source"] == "existing_asset"
    assert architecture["assetId"] == "a-arch"
    assert architecture["candidates"][0]["assetId"] == "a-arch"
    for placement in plan["placements"]:
        assert placement["anchorHeading"]
        assert placement["generationPrompt"]
        assert "文字" in placement["generationPrompt"]


def test_plan_without_assets_all_generate(factory, article):
    with factory() as db:
        plan = VisualService(db).plan(markdown=MARKDOWN, target_count=3)
    assert plan["targetCount"] == 3
    assert all(p["source"] == "generate" for p in plan["placements"])


def test_plan_uses_model_and_falls_back(factory, article, monkeypatch):
    from app.agents import llm_client

    class FakeLLM:
        model = "planner-model"
        api_key_configured = True

        @staticmethod
        def complete_json(*args, **kwargs):
            return {
                "placements": [
                    {
                        "anchorHeading": "数据对比",
                        "anchorExcerpt": "导出速度差异",
                        "purpose": "说明性能差异",
                        "visualType": "comparison",
                        "source": "generate",
                        "assetId": None,
                        "selectionReason": "对比图最直观。",
                        "alt": "导出速度对比",
                        "generationPrompt": "简洁左右对比示意图，无文字。",
                    },
                ],
            }

    monkeypatch.setattr(llm_client, "LLMClient", FakeLLM)
    with factory() as db:
        plan = VisualService(db).plan(markdown=MARKDOWN, target_count=1)
    assert plan["planner"] == "model"
    assert plan["plannerModel"] == "planner-model"
    assert plan["placements"][0]["anchorHeading"] == "数据对比"
    assert plan["placements"][0]["visualType"] == "comparison"

    class BadLLM:
        model = "bad-model"
        api_key_configured = True

        @staticmethod
        def complete_json(*args, **kwargs):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(llm_client, "LLMClient", BadLLM)
    with factory() as db:
        plan = VisualService(db).plan(markdown=MARKDOWN, target_count=1)
    assert plan["planner"] == "deterministic"
    assert len(plan["placements"]) == 1


def test_apply_inserts_assets_and_commits_revision(factory, article):
    _add_asset(factory, asset_id="a-1", alt="数据对比图")
    with factory() as db:
        plan = VisualService(db).plan(
            markdown=MARKDOWN, target_count=2, asset_ids=["a-1"],
        )
        # 第一张强制走生图路径，覆盖两条插入分支
        placements = plan["placements"]
        placements[0] = {
            **placements[0], "source": "generate",
            "generationPrompt": "一幅极简示意图",
        }
        generated: dict = {}

        def fake_generate(*, prompt: str, size: str = "1024x1024", image_profile_id: str | None = None):
            generated["prompt"] = prompt
            return {
                "id": "gen-1", "name": "生成图", "alt": prompt[:200],
                "usageHint": "AI 生成", "mime": "image/png",
                "source": "data:image/png;base64,iVBORw0KGgo=",
                "origin": "generated", "createdAt": "2026-10-19T00:00:00",
            }

        service = VisualService(db)
        service.media.generate = fake_generate  # type: ignore[method-assign]
        result = service.apply(
            article_id="article-visual",
            base_revision_id=article["currentRevisionId"],
            base_content_hash=article["contentHash"],
            placements=placements,
        )

    assert result["insertedCount"] == 2
    assert result["skipped"] == []
    assert generated["prompt"] == "一幅极简示意图"
    markdown = result["article"]["markdown"]
    assert "asset://a-1" in markdown
    assert "asset://gen-1" in markdown
    assert result["article"]["currentRevisionId"] != article["currentRevisionId"]
    assert "## 数据对比" in markdown


def test_apply_rejects_stale_revision(factory, article):
    with factory() as db:
        service = VisualService(db)
        with pytest.raises(ArticleConflictError):
            service.apply(
                article_id="article-visual",
                base_revision_id="stale-revision",
                base_content_hash=article["contentHash"],
                placements=[{
                    "id": "illustration-1", "source": "generate",
                    "generationPrompt": "p", "alt": "配图",
                }],
            )


def test_visual_plan_api_returns_hash_binding(client, article):
    res = client.post("/api/articles/article-visual/visual-plan", json={
        "targetCount": 2, "assetIds": [], "materialMatchThreshold": 40,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["sourceRevisionId"] == article["currentRevisionId"]
    assert body["sourceContentHash"] == article["contentHash"]
    assert len(body["placements"]) == 2


def test_visual_apply_api_creates_new_revision(client, factory, article, monkeypatch):
    def fake_generate(self, *, prompt: str, size: str = "1024x1024", image_profile_id: str | None = None):
        return {
            "id": "gen-api", "name": "生成图", "alt": prompt[:200],
            "usageHint": "AI 生成", "mime": "image/png",
            "source": "data:image/png;base64,iVBORw0KGgo=",
            "origin": "generated", "createdAt": "2026-10-19T00:00:00",
        }

    from app.services import media_service

    monkeypatch.setattr(media_service.MediaService, "generate", fake_generate)
    plan = client.post("/api/articles/article-visual/visual-plan", json={
        "targetCount": 1, "assetIds": [],
    }).json()
    res = client.post("/api/articles/article-visual/visual-apply", json={
        "baseRevisionId": article["currentRevisionId"],
        "baseContentHash": article["contentHash"],
        "placements": plan["placements"],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["insertedCount"] == 1
    assert "asset://gen-api" in body["article"]["markdown"]

    state = client.get("/api/articles/article-visual").json()
    assert state["currentRevisionId"] == body["article"]["currentRevisionId"]

