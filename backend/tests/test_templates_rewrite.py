"""模板服务 / 提取 / 改写候选测试（FakeLLM）。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.run_journal import RunJournal
from app.services.template_service import TemplateService, seed_builtin_templates
from app.services.writer_service import WriterService  # noqa: F401


class FakeJSONLLM:
    def __init__(self, data):
        self.data = data

    def complete(self, system, user, **kwargs):
        return "ok"

    def complete_json(self, system, user, **kwargs):
        return self.data


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    session = factory()
    seed_builtin_templates(session)
    yield session
    session.close()


def test_builtin_template_seeded(db):
    templates = TemplateService(db).list()
    builtin = [t for t in templates if t["isBuiltIn"]]
    assert len(builtin) == 1
    assert builtin[0]["id"] == "product-promotion"
    assert builtin[0]["name"] == "产品推广"
    assert "{{" in builtin[0]["markdown"] or builtin[0]["markdown"]


def test_custom_template_create_and_delete(db):
    service = TemplateService(db)
    created = service.create_custom(
        name="我的模板", description="d", category="自定义",
        markdown="# {{标题}}\n\n正文",
    )
    assert created["isBuiltIn"] is False
    assert created["mode"] == "scaffold"
    service.delete(created["id"])
    assert created["id"] not in [t["id"] for t in service.list()]
    with pytest.raises(ValueError):
        service.delete("product-promotion")


def test_extract_template_creates_reference_mode(db):
    service = TemplateService(db)
    original = service.create_custom.__wrapped__ if hasattr(
        service.create_custom, "__wrapped__"
    ) else None
    # 直接注入 LLM：TemplateService.extract_from_article 内部 new LLMClient，
    # 这里 monkeypatch
    import app.agents.llm_client as llm_mod

    class FakeLLMClient:
        def complete_json(self, system, user, **kwargs):
            assert "只提供结构" in system
            return {
                "name": "提取模板",
                "description": "来自参考文章",
                "markdown": "# {{开场}}\n\n{{正文}}",
                "variables": ["开场", "正文"],
                "usageInstructions": "照结构填。",
            }

    original = llm_mod.LLMClient
    llm_mod.LLMClient = FakeLLMClient
    try:
        created = service.extract_from_article("# 参考文章\n\n内容")
    finally:
        llm_mod.LLMClient = original
    assert created["mode"] == "reference"
    assert created["sourceFingerprint"].startswith("sha256:")
    assert created["referenceMarkdown"].startswith("# 参考文章")


def test_rewrite_candidate_flow(db):
    from app.services.rewrite_service import RewriteService

    class FakeLLM:
        model = "fake-model"

        def complete_json(self, system, user, **kwargs):
            assert "绝不能声称" in system
            return {"replacements": ["改好的第一段"], "summary": "润色开头"}

    service = RewriteService(db, llm=FakeLLM())
    run = service.start_rewrite(
        article_id="a1", markdown="原文", instruction="润色开头",
        selected_texts=["第一段原文"],
    )
    import time

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = RunJournal(db).get_run(run["id"])
        if current["status"] in ("completed", "failed", "stopped", "interrupted"):
            break
        time.sleep(0.02)
    assert current["status"] == "completed"
    events = RunJournal(db).events_after(run["id"], 0)
    ready = [e for e in events if e["type"] == "rewrite.candidate_ready"]
    assert len(ready) == 1
    assert ready[0]["payload"]["replacements"] == ["改好的第一段"]


def test_template_profile_update(db):
    service = TemplateService(db)
    created = service.create_custom(
        name="画像模板", description="d", category="自定义",
        markdown="# {{标题}}\n\n正文",
    )
    updated = service.update(
        created["id"],
        name="画像模板 2",
        style_profile={"tone": "克制的实操分享"},
        structure_profile={"sectionOrder": ["hook", "proof", "next"]},
        layout_profile={"paragraphLength": "三到五句"},
        fixed_blocks=[{"name": "免责声明", "content": "本文为演示", "position": "end"}],
        variables=["标题", "正文"],
    )
    assert updated["name"] == "画像模板 2"
    assert updated["styleProfile"]["tone"] == "克制的实操分享"
    assert updated["structureProfile"]["sectionOrder"] == ["hook", "proof", "next"]
    assert updated["layoutProfile"]["paragraphLength"] == "三到五句"
    assert updated["fixedBlocks"][0]["name"] == "免责声明"
    assert updated["variables"] == ["标题", "正文"]
    with pytest.raises(ValueError):
        service.update("product-promotion", name="尝试改内置")
