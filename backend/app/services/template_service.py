"""模板服务：蓝本 TemplatesPage / template-service 的 Web 版。

- 内置"产品推广"模板来自蓝本 product-promotion.v1.json 原文（启动时 seed）
- 自定义模板落库；内置模板不可删除
- extract：把一篇参考文章的结构提炼成模板（蓝本模板提取思想的简化实现，
  输出 MarkdownTemplate 子集，参考文章只作表达源不进正文）
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template import ArticleTemplate

_BUILTIN_JSON = Path(__file__).resolve().parent.parent / "data" / "product-promotion.v1.json"


def _doc_template() -> dict:
    raw = json.loads(_BUILTIN_JSON.read_text(encoding="utf-8"))
    template = raw["template"]
    template["id"] = "product-promotion"
    template["name"] = "产品推广"
    template["category"] = "产品推广"
    template["isBuiltIn"] = True
    template["mode"] = "scaffold"
    return template


def seed_builtin_templates(db: Session) -> None:
    """幂等：不存在才插入内置模板。"""
    t = _doc_template()
    if db.get(ArticleTemplate, t["id"]) is None:
        db.add(ArticleTemplate(
            id=t["id"], name=t["name"], description=t.get("description", ""),
            category=t["category"], markdown=t["markdown"],
            style_profile=t.get("styleProfile", {}),
            structure_profile=t.get("structureProfile", {}),
            layout_profile=t.get("layoutProfile", {}),
            fixed_blocks=t.get("fixedBlocks", []),
            variables=t.get("variables", []),
            usage_instructions=t.get("usageInstructions", ""),
            is_built_in=True, mode="scaffold",
        ))
        db.commit()


def _out(t: ArticleTemplate) -> dict:
    return {
        "id": t.id, "name": t.name, "description": t.description,
        "category": t.category, "markdown": t.markdown,
        "styleProfile": t.style_profile, "structureProfile": t.structure_profile,
        "layoutProfile": t.layout_profile, "fixedBlocks": t.fixed_blocks,
        "variables": t.variables, "usageInstructions": t.usage_instructions,
        "isBuiltIn": t.is_built_in, "mode": t.mode,
        "referenceMarkdown": t.reference_markdown,
        "sourceFingerprint": t.source_fingerprint,
        "ownerId": t.owner_user_id,
    }


class TemplateService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, owner_user_id: str | None = None) -> list[dict]:
        query = select(ArticleTemplate).order_by(ArticleTemplate.id)
        if owner_user_id:
            from sqlalchemy import or_

            query = query.where(or_(
                ArticleTemplate.owner_user_id == owner_user_id,
                ArticleTemplate.owner_user_id.is_(None),
                ArticleTemplate.is_built_in.is_(True),
            ))
        rows = self.db.scalars(query).all()
        return [_out(t) for t in rows]

    def create_custom(self, *, name: str, description: str, category: str,
                      markdown: str, usage_instructions: str = "",
                      reference_markdown: str | None = None,
                      owner_user_id: str | None = None) -> dict:
        if not name.strip() or not markdown.strip():
            raise ValueError("模板名称与正文不能为空")
        fingerprint = None
        mode = "scaffold"
        if reference_markdown:
            mode = "reference"
            fingerprint = "sha256:" + hashlib.sha256(
                reference_markdown.encode("utf-8")).hexdigest()
        existing = self.db.scalars(select(ArticleTemplate.id)).all()
        owner_token = owner_user_id[:8] if owner_user_id else "shared"
        base = f"custom-{owner_token}-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        template_id = base if base not in existing else f"{base}-{len(existing) + 1}"
        row = ArticleTemplate(
            id=template_id, name=name.strip(), description=description,
            category=category or "自定义", markdown=markdown,
            usage_instructions=usage_instructions,
            is_built_in=False, mode=mode,
            reference_markdown=reference_markdown,
            source_fingerprint=fingerprint,
            owner_user_id=owner_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return _out(row)

    def update(
        self,
        template_id: str,
        *,
        owner_user_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        markdown: str | None = None,
        usage_instructions: str | None = None,
        style_profile: dict | None = None,
        structure_profile: dict | None = None,
        layout_profile: dict | None = None,
        fixed_blocks: list | None = None,
        variables: list[str] | None = None,
    ) -> dict:
        row = self.db.get(ArticleTemplate, template_id)
        if row is None or (owner_user_id and row.owner_user_id != owner_user_id):
            raise KeyError("template not found")
        if row.is_built_in:
            raise ValueError("内置模板不可修改")
        if name is not None:
            row.name = name.strip() or row.name
        if description is not None:
            row.description = description.strip()
        if category is not None:
            row.category = category.strip() or row.category
        if markdown is not None and markdown.strip():
            row.markdown = markdown
        if usage_instructions is not None:
            row.usage_instructions = usage_instructions.strip()
        if style_profile is not None:
            row.style_profile = style_profile
        if structure_profile is not None:
            row.structure_profile = structure_profile
        if layout_profile is not None:
            row.layout_profile = layout_profile
        if fixed_blocks is not None:
            row.fixed_blocks = fixed_blocks
        if variables is not None:
            row.variables = [item.strip() for item in variables if item.strip()]
        self.db.commit()
        self.db.refresh(row)
        return _out(row)

    def delete(self, template_id: str, owner_user_id: str | None = None) -> None:
        row = self.db.get(ArticleTemplate, template_id)
        if row is None or (owner_user_id and row.owner_user_id != owner_user_id):
            raise KeyError("template not found")
        if row.is_built_in:
            raise ValueError("内置模板不可删除")
        self.db.delete(row)
        self.db.commit()

    def extract_from_article(self, markdown: str, owner_user_id: str | None = None) -> dict:
        """蓝本模板提取：参考文章作为"表达源"，提炼结构骨架为模板。"""
        from app.agents.llm_client import LLMClient

        system = (
            "你是文章模板提取器。参考文章只提供结构与表达方式，绝不提取其中的"
            "产品名、数字、案例等事实内容。只输出 JSON 对象，字段：\n"
            '- name: 模板名（简短中文）\n'
            '- description: 一句话说明适用场景\n'
            '- markdown: 模板骨架（保留章节结构，具体事实全部替换为 {{变量}} 占位符）\n'
            '- styleProfile: {tone, readerRelationship, forbiddenPatterns, preferredEvidence}\n'
            '- structureProfile: {sectionOrder, sectionPurposes, transitionStyle, ctaPosition}\n'
            '- layoutProfile: {headingLevelRule, paragraphLength, listUsage, emphasisStyle}\n'
            '- fixedBlocks: 每一项 {name, content, position}，没有就传 []\n'
            "- variables: 占位符名列表\n"
            "- usageInstructions: 使用说明（两三句）\n"
            "不要输出 JSON 以外内容。"
        )
        llm = LLMClient()
        if not getattr(llm, "api_key_configured", True):
            raise ValueError(
                "未配置模型 API Key：请到设置页激活模型档案，"
                "并确认后端容器已注入档案对应的环境变量。"
            )
        data = llm.complete_json(system, f"参考文章：\n\n{markdown[:120_000]}")
        return self.create_custom(
            name=str(data.get("name", "提取模板")),
            description=str(data.get("description", "")),
            category="提取",
            markdown=str(data.get("markdown", "")),
            usage_instructions=str(data.get("usageInstructions", "")),
            reference_markdown=markdown,
            owner_user_id=owner_user_id,
        )
        # create_custom 不接收画像参数；提取结果在返回前补齐，保持单一建模板入口。
        from app.models.template import ArticleTemplate as _Template
        row = self.db.get(_Template, result["id"])
        if row is not None:
            row.style_profile = data.get("styleProfile") if isinstance(data.get("styleProfile"), dict) else {}
            row.structure_profile = data.get("structureProfile") if isinstance(data.get("structureProfile"), dict) else {}
            row.layout_profile = data.get("layoutProfile") if isinstance(data.get("layoutProfile"), dict) else {}
            row.fixed_blocks = data.get("fixedBlocks") if isinstance(data.get("fixedBlocks"), list) else []
            row.variables = data.get("variables") if isinstance(data.get("variables"), list) else []
            self.db.commit()
            return _out(row)
        return result
