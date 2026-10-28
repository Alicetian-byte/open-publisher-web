"""视觉规划服务：蓝本 visual-planning-service 的模型驱动版。

蓝本分两层：文本模型产出结构化 placement；模型不可用时降级为本地
确定性规划器。Web 版沿用同一契约，默认优先调用文本模型，失败或未
配置密钥时自动降级为确定性规划器：
- 每个位置对素材做 0-1000 相似度打分，取前 5 个候选；
- 最高分 >= materialMatchThreshold * 10 时 source=existing_asset，
  否则 source=generate 并生成可复现的生图提示词；
- apply 阶段绑定 baseRevisionId + baseContentHash（乐观并发），
  生成的图立即进入素材库，正文以 asset:// 引用插入并落新版本。
"""

from __future__ import annotations

import json
import re
import unicodedata
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import MediaAsset
from app.services.article_store import ArticleConflictError, ArticleStore
from app.services.media_service import MediaService

MAX_PLACEMENTS = 6
MAX_CANDIDATES = 5

_VISUAL_FORM = {
    "scene": "一个象征性主体构成克制的编辑场景",
    "flowchart": "最多三个象征性对象用方向箭头连接",
    "comparison": "左右均衡构图，用物体与颜色对比两种状态",
    "timeline": "从左到右的时间推进，用物件间距表现顺序",
}

_TYPE_HINTS = (
    (("对比", "相比", "差异", "vs", "versus"), "comparison"),
    (("流程", "步骤", "架构", "pipeline"), "flowchart"),
    (("时间线", "历史", "演进", "阶段"), "timeline"),
)


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower()


def _tokens(value: str) -> set[str]:
    """中英混合分词：ASCII 词 + CJK 二元组。"""
    normalized = _normalize(value)
    tokens: set[str] = set(re.findall(r"[a-z0-9]+", normalized))
    cjk = re.sub(r"[^\u4e00-\u9fff]+", "", normalized)
    tokens.update(cjk[i : i + 2] for i in range(len(cjk) - 1))
    return tokens


def _similarity(left: str, right: str) -> int:
    """包含度相似分（0-1000）：素材描述相对目标内容的覆盖率。

    蓝本启发式同样以"素材描述能解释位置内容"为目标；用
    |A∩B| / min(|A|,|B|) 比 Jaccard 更符合长正文 vs 短素材描述的场景。
    """
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0
    return round(1000 * len(a & b) / min(len(a), len(b)))


def _visual_type(text: str) -> str:
    lowered = _normalize(text)
    for hints, visual_type in _TYPE_HINTS:
        if any(hint in lowered for hint in hints):
            return visual_type
    return "scene"


def _excerpt(text: str, limit: int = 60) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]


class MarkdownBlock:
    __slots__ = ("heading", "text", "excerpt", "start_line", "end_line")

    def __init__(self, *, heading: str | None, text: str,
                 start_line: int, end_line: int):
        self.heading = heading
        self.text = text
        self.excerpt = _excerpt(text) or _excerpt(heading or "", 60)
        self.start_line = start_line
        self.end_line = end_line


def split_markdown_blocks(markdown: str) -> list[MarkdownBlock]:
    """按标题切分内容块；记录行号供插图定位。"""
    blocks: list[MarkdownBlock] = []
    heading: str | None = None
    heading_line = 0
    body: list[str] = []
    body_start = 0

    def flush(end_line: int) -> None:
        text = "\n".join(body).strip()
        if heading is not None or text:
            blocks.append(MarkdownBlock(
                heading=heading, text=text,
                start_line=heading_line, end_line=end_line,
            ))

    for index, line in enumerate(markdown.splitlines()):
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+\S", stripped):
            flush(index - 1)
            heading = re.sub(r"^#+\s*", "", stripped)
            heading_line = index
            body = []
            body_start = index + 1
        elif not (heading is None and not body and not stripped):
            body.append(line)
    flush(len(markdown.splitlines()) - 1)
    # body_start 允许未被使用也保持结构清晰
    _ = body_start
    return blocks


def _choose_blocks(blocks: list[MarkdownBlock], count: int) -> list[MarkdownBlock]:
    """确定性选点：优先信息量最大的正文块（文本更长者），按文中顺序返回。

    蓝本由文本模型挑选位置；确定性降级版用"内容丰富的小节更需要配图"
    作为可解释规则，避免把插图集中到篇首导语或一句话结语。
    """
    content = [b for b in blocks if b.text or (b.heading and b.start_line > 0)]
    if not content:
        return []
    n = max(0, min(count, len(content), MAX_PLACEMENTS))
    if n == 0:
        return []
    ranked = sorted(content, key=lambda b: -len(b.text))
    return sorted(ranked[:n], key=lambda b: b.start_line)


def _candidates_for(block: MarkdownBlock, assets: list[MediaAsset]) -> list[dict]:
    query = f"{block.heading or ''}\n{block.text}"
    scored = sorted(
        (
            {
                "assetId": asset.id,
                # 只用语义字段匹配；name 是管理用标签，会稀释相似度
                "score": _similarity(query, (
                    f"{asset.alt} {asset.visual_description} "
                    f"{asset.usage_hint} {' '.join(asset.tags or [])}"
                )),
                "description": _excerpt(asset.alt or asset.name, 120),
            }
            for asset in assets
        ),
        key=lambda item: (-item["score"], item["assetId"]),
    )
    return scored[:MAX_CANDIDATES]


def _generation_prompt(block: MarkdownBlock) -> str:
    visual_type = _visual_type(block.text)
    summary = _excerpt(block.text or block.heading or "文章核心观点", 160)
    return (
        f"为文章小节「{block.heading or '核心观点'}」创作一幅编辑插图。"
        f"核心内容：{summary}。"
        f"构图：{_VISUAL_FORM[visual_type]}。"
        "风格：柔和手绘线条、扁平形状、马卡龙配色；"
        "画面中不出现任何文字、字母、数字或水印。"
    )


def _alt_for(block: MarkdownBlock, ordinal: int) -> str:
    base = _excerpt(block.heading or "文章配图", 60)
    return re.sub(r"[\[\]\r\n]", " ", base).strip() or f"文章配图 {ordinal}"


def _clean_text(value: object, limit: int = 900) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _match_block(
    placement: dict, blocks: list[MarkdownBlock],
) -> MarkdownBlock | None:
    """按模型给出的标题/摘录反查正文块；精确命中优先，其次包含度。"""
    heading = _clean_text(placement.get("anchorHeading") or placement.get("afterHeading"))
    excerpt = _clean_text(placement.get("anchorExcerpt") or placement.get("position"))
    if heading:
        exact = [b for b in blocks if b.heading == heading]
        if exact:
            return exact[0]
    for block in blocks:
        haystack = f"{block.heading or ''}\n{block.text}"
        if excerpt and excerpt in haystack:
            return block
        if heading and heading in haystack:
            return block
    scored = sorted(
        blocks,
        key=lambda block: max(
            _similarity(excerpt, f"{block.heading or ''}\n{block.text}"),
            _similarity(heading, block.heading or "") if heading else 0,
        ),
        reverse=True,
    )
    return scored[0] if scored and (excerpt or heading) else None


def _visual_model_prompt(
    blocks: list[MarkdownBlock], assets: list[MediaAsset], target_count: int,
    material_match_threshold: int,
) -> tuple[str, str]:
    asset_briefs = [
        {
            "id": asset.id, "alt": asset.alt,
            "description": _clean_text(asset.visual_description or asset.alt, 240),
            "usage": _clean_text(asset.usage_hint, 120),
            "tags": asset.tags or [],
        }
        for asset in assets
    ]
    section_briefs = [
        {
            "heading": block.heading,
            "excerpt": block.excerpt,
            "content": _clean_text(block.text, 900),
        }
        for block in blocks
    ]
    system = (
        "You are the planning phase of the article illustrator. "
        "Return a strict JSON object with a placements array. Do not create images. "
        "Each placement teaches one concrete relationship, comparison, process, "
        "framework or timeline. Prefer sparse explanatory visuals over decorative posters. "
        "Never ask for paragraphs, tables, UI screenshots or many labels inside the image. "
        "Use an existing asset only when its metadata serves the visual need, and at most once. "
        "Otherwise use generate. Return exactly the requested number of placements."
    )
    user = json.dumps({
        "targetCount": target_count,
        "materialMatchThreshold": material_match_threshold * 10,
        "sections": section_briefs,
        "assets": asset_briefs,
        "placementSchema": {
            "anchorHeading": "Section heading or null",
            "anchorExcerpt": "A short verbatim excerpt used to locate the insertion point",
            "purpose": "Why this visual helps readers",
            "visualType": "scene | flowchart | comparison | timeline",
            "source": "existing_asset | generate",
            "assetId": "Asset id for existing_asset, otherwise null",
            "selectionReason": "Short reason",
            "alt": "Concise image alt text",
            "generationPrompt": "Concrete visual brief; no text, letters, numbers or watermark",
        },
    }, ensure_ascii=False)
    return system, user


def _model_plan(
    blocks: list[MarkdownBlock],
    assets: list[MediaAsset],
    *,
    target_count: int,
    material_match_threshold: int,
) -> tuple[list[dict], str | None] | None:
    """模型驱动规划；不可用/输出不合法时返回 None 以触发规则兜底。"""
    from app.agents.llm_client import LLMClient

    llm = LLMClient()
    if not llm.api_key_configured:
        return None
    system, user = _visual_model_prompt(
        blocks, assets, target_count, material_match_threshold,
    )
    try:
        data = llm.complete_json(system, user, temperature=0.25)
    except Exception:  # noqa: BLE001 - 规划失败必须无感回退
        return None
    candidates = data.get("placements")
    if not isinstance(candidates, list) or len(candidates) != target_count:
        return None

    placements: list[dict] = []
    used_assets: set[str] = set()
    for ordinal, raw in enumerate(candidates, start=1):
        if not isinstance(raw, dict):
            return None
        block = _match_block(raw, blocks)
        if block is None:
            return None
        visual_type = _clean_text(raw.get("visualType"), 40)
        if visual_type not in _VISUAL_FORM:
            visual_type = _visual_type(block.text)
        asset_id = _clean_text(raw.get("assetId"), 100) or None
        candidates_for_block = _candidates_for(block, assets)
        source = "existing_asset" if _clean_text(raw.get("source")) == "existing_asset" else "generate"
        valid_asset = next(
            (c for c in candidates_for_block if c["assetId"] == asset_id),
            None,
        )
        if source == "existing_asset" and (valid_asset is None or asset_id in used_assets):
            source, asset_id = "generate", None
        if source == "existing_asset" and asset_id:
            used_assets.add(asset_id)
        alt = re.sub(r"[\[\]\r\n]", " ", _clean_text(raw.get("alt"), 160)).strip()
        placements.append({
            "id": f"illustration-{ordinal}",
            "anchorHeading": block.heading,
            "anchorExcerpt": block.excerpt,
            "purpose": _clean_text(raw.get("purpose"), 400) or "补充小节说明",
            "visualType": visual_type,
            "source": source,
            "assetId": asset_id,
            "candidates": candidates_for_block,
            "selectionReason": _clean_text(raw.get("selectionReason"), 500) or (
                f"素材与该小节匹配度 {valid_asset['score'] // 10}%。"
                if valid_asset else "没有达到阈值的可用素材，需生成新图。"
            ),
            "alt": alt or _alt_for(block, ordinal),
            "generationPrompt": _clean_text(raw.get("generationPrompt"), 1600)
                or _generation_prompt(block),
        })
    return placements, llm.model


def _fallback_plan(
    chosen: list[MarkdownBlock], assets: list[MediaAsset], *,
    material_match_threshold: int,
) -> list[dict]:
    placements: list[dict] = []
    used_assets: set[str] = set()
    for ordinal, block in enumerate(chosen, start=1):
        candidates = _candidates_for(block, assets)
        default = next(
            (
                c for c in candidates
                if c["score"] >= material_match_threshold * 10
                and c["assetId"] not in used_assets
            ),
            None,
        )
        if default is not None:
            used_assets.add(default["assetId"])
        placements.append({
            "id": f"illustration-{ordinal}",
            "anchorHeading": block.heading,
            "anchorExcerpt": block.excerpt,
            "purpose": "补充小节说明",
            "visualType": _visual_type(block.text),
            "source": "existing_asset" if default else "generate",
            "assetId": default["assetId"] if default else None,
            "candidates": candidates,
            "selectionReason": (
                f"素材与该小节匹配度 {default['score'] // 10}%。"
                if default
                else "没有达到阈值的可用素材，需生成新图。"
            ),
            "alt": _alt_for(block, ordinal),
            "generationPrompt": _generation_prompt(block),
        })
    return placements


class VisualService:

    def __init__(self, db: Session):
        self.db = db
        self.store = ArticleStore(db)
        self.media = MediaService(db)

    def plan(
        self,
        *,
        markdown: str,
        target_count: int,
        asset_ids: list[str] | None = None,
        material_match_threshold: int = 40,
    ) -> dict:
        blocks = split_markdown_blocks(markdown)
        chosen = _choose_blocks(blocks, target_count)
        assets: list[MediaAsset] = []
        if asset_ids:
            rows = self.db.scalars(
                select(MediaAsset).where(MediaAsset.id.in_(asset_ids))
            ).all()
            by_id = {row.id: row for row in rows}
            assets = [by_id[asset_id] for asset_id in asset_ids if asset_id in by_id]

        if chosen:
            model_result = _model_plan(
                blocks, assets,
                target_count=len(chosen),
                material_match_threshold=material_match_threshold,
            )
            if model_result:
                placements, provider_model = model_result
                return {
                    "sourceContentHash": None,  # apply 时以前端提交的哈希做并发校验
                    "targetCount": len(placements),
                    "placements": placements,
                    "planner": "model",
                    "plannerModel": provider_model,
                }
        placements = _fallback_plan(
            chosen, assets, material_match_threshold=material_match_threshold,
        )
        return {
            "sourceContentHash": None,  # apply 时以前端提交的哈希做并发校验
            "targetCount": len(placements),
            "placements": placements,
            "planner": "deterministic",
            "plannerModel": None,
        }

    def apply(
        self,
        *,
        article_id: str,
        base_revision_id: str,
        base_content_hash: str,
        placements: list[dict],
        owner_user_id: str | None = None,
        image_model_id: str | None = None,
    ) -> dict:
        article = self.store.read(article_id)
        if article is None:
            raise KeyError("article not found")
        if (
            article["currentRevisionId"] != base_revision_id
            or article["contentHash"] != base_content_hash
        ):
            raise ArticleConflictError("Article changed after this operation started")

        lines = article["markdown"].rstrip().split("\n")
        insertions: list[tuple[int, str]] = []
        skipped: list[dict] = []
        for placement in placements:
            asset_id = placement.get("assetId")
            if placement.get("source") == "generate":
                prompt = (placement.get("generationPrompt") or "").strip()
                if not prompt:
                    skipped.append({"id": placement.get("id"), "reason": "缺少生图提示词"})
                    continue
                try:
                    asset = self.media.generate(
                        prompt=prompt, size="1536x1024",
                        image_profile_id=image_model_id,
                    )
                except Exception as exc:  # noqa: BLE001 - 单张失败不阻塞整篇
                    skipped.append({
                        "id": placement.get("id"),
                        "reason": f"图片生成失败：{exc}",
                    })
                    continue
                asset_id = asset["id"]
            if not asset_id:
                skipped.append({"id": placement.get("id"), "reason": "缺少素材标识"})
                continue
            anchor_line = self._anchor_line(lines, placement)
            if anchor_line is None:
                skipped.append({"id": placement.get("id"), "reason": "未找到插入锚点"})
                continue
            alt = re.sub(r"[\[\]\r\n]", " ", str(placement.get("alt") or "文章配图")).strip()
            insertions.append((
                anchor_line,
                f"![{alt}](asset://{asset_id})",
            ))

        for line_no, markup in sorted(insertions, key=lambda item: item[0], reverse=True):
            lines.insert(line_no + 1, "")
            lines.insert(line_no + 2, markup)
        next_markdown = "\n".join(lines).rstrip() + "\n"

        if not insertions:
            return {
                "article": article,
                "insertedCount": 0,
                "skipped": skipped,
            }

        committed = self.store.commit(
            article_id=article_id,
            base_revision_id=base_revision_id,
            base_content_hash=base_content_hash,
            title=article["title"],
            markdown=next_markdown,
            reason=f"visual-insert {uuid4().hex[:8]}",
            owner_user_id=owner_user_id,
        )
        return {
            "article": committed,
            "insertedCount": len(insertions),
            "skipped": skipped,
        }

    @staticmethod
    def _anchor_line(lines: list[str], placement: dict) -> int | None:
        """定位插图行：优先锚点摘录，其次小节标题，取该内容块末行。"""
        excerpt = (placement.get("anchorExcerpt") or "").strip()
        heading = (placement.get("anchorHeading") or "").strip()

        def block_end(start: int) -> int:
            end = start
            while end + 1 < len(lines) and lines[end + 1].strip():
                end += 1
            return end

        if excerpt:
            for index, line in enumerate(lines):
                if excerpt in line:
                    return block_end(index)
        if heading:
            for index, line in enumerate(lines):
                if re.sub(r"^#+\s*", "", line.strip()) == heading:
                    return block_end(index)
        return None
