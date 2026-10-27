"""图片服务：蓝本 image-service 的 Web 版。

- 上传：前端读文件为 data URL 存库（浏览器能力，替代桌面文件系统）
- 生成：调用 OpenAI 兼容 images API（base_url 复用 LLM 配置）；
  未配置 Key 时返回 501，明确提示（蓝本同样要求密钥走服务端）
"""

from __future__ import annotations

import base64
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import MediaAsset


class MediaService:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self,
        owner_user_id: str | None = None,
        *,
        search: str | None = None,
        origin: str | None = None,
        tag: str | None = None,
        sort: str = "created_desc",
    ) -> list[dict]:
        query = select(MediaAsset)
        if owner_user_id:
            from sqlalchemy import or_

            query = query.where(or_(
                MediaAsset.owner_user_id == owner_user_id,
                MediaAsset.owner_user_id.is_(None),
            ))
        if search:
            needle = search.strip().lower()
            if needle:
                query = query.where(
                    MediaAsset.name.ilike(f"%{needle}%")
                    | MediaAsset.alt.ilike(f"%{needle}%")
                    | MediaAsset.visual_description.ilike(f"%{needle}%")
                    | MediaAsset.usage_hint.ilike(f"%{needle}%")
                )
        if origin:
            query = query.where(MediaAsset.origin == origin)
        orders = {
            "created_desc": MediaAsset.created_at.desc(),
            "created_asc": MediaAsset.created_at.asc(),
            "name_asc": MediaAsset.name.asc(),
            "name_desc": MediaAsset.name.desc(),
        }
        query = query.order_by(orders.get(sort, MediaAsset.created_at.desc()))
        rows = self.db.scalars(query).all()
        if tag:
            wanted = tag.strip().lower()
            rows = [
                row for row in rows
                if wanted in {str(item).lower() for item in (row.tags or [])}
            ]
        return [self._out(row) for row in rows]

    def get(self, asset_id: str, owner_user_id: str | None = None) -> MediaAsset | None:
        row = self.db.get(MediaAsset, asset_id)
        if row is None or (owner_user_id and row.owner_user_id is not None and row.owner_user_id != owner_user_id):
            return None
        return row

    def add_upload(self, *, name: str, mime: str, data_url: str,
                   alt: str = "", usage_hint: str = "",
                   visual_description: str = "", tags: list[str] | None = None,
                   owner_user_id: str | None = None) -> dict:
        if not data_url.startswith("data:"):
            raise ValueError("上传必须为 data URL")
        row = MediaAsset(
            id=uuid4().hex, name=name.strip() or "未命名素材", alt=alt,
            visual_description=visual_description,
            usage_hint=usage_hint, mime=mime, source=data_url, origin="upload",
            tags=self._clean_tags(tags or []), description_source="manual",
            owner_user_id=owner_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return self._out(row)

    def add_generated(self, *, b64_json: str, mime: str, prompt: str,
                      owner_user_id: str | None = None) -> dict:
        data_url = f"data:{mime};base64,{b64_json}"
        row = MediaAsset(
            id=uuid4().hex, name=f"生成图：{prompt[:60]}", alt=prompt[:200],
            visual_description=prompt[:1000],
            usage_hint="AI 生成", mime=mime, source=data_url, origin="generated",
            generation_prompt=prompt, tags=["AI 生成"],
            description_source="generation_prompt",
            owner_user_id=owner_user_id,
        )
        self.db.add(row)
        self.db.commit()
        return self._out(row)

    def delete(self, asset_id: str, owner_user_id: str | None = None) -> None:
        row = self.get(asset_id, owner_user_id)
        if row is None:
            raise KeyError("asset not found")
        self.db.delete(row)
        self.db.commit()

    def generate(self, *, prompt: str, size: str = "1024x1024",
                 owner_user_id: str | None = None,
                 image_profile_id: str | None = None) -> dict:
        """OpenAI 兼容 images API；密钥来自数据库加密存储。"""
        from fastapi import HTTPException

        from app.services.model_profile_service import resolve_image_config

        resolved = resolve_image_config(db=self.db, profile_id=image_profile_id)
        if not resolved["api_key"]:
            raise HTTPException(
                status_code=501,
                detail="图片生成需要先在管理端配置生图模型并录入数据库加密密钥",
            )
        from openai import OpenAI

        client = OpenAI(
            api_key=resolved["api_key"],
            base_url=resolved["base_url"],
            timeout=resolved["timeout_seconds"],
        )
        try:
            result = client.images.generate(model=resolved["model"], prompt=prompt,
                                            size=size, n=1)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"图片生成失败：{exc}") from None
        item = result.data[0]
        if item.b64_json:
            return self.add_generated(
                b64_json=item.b64_json, mime="image/png", prompt=prompt,
                owner_user_id=owner_user_id,
            )

        # 部分兼容网关返回临时 URL。这里在生成完成后由后端立即落成本地数据，
        # 避免正文引用 /api/media/{id}/raw 时出现远端 404、鉴权失效或临时链接过期。
        if item.url:
            import base64

            import httpx
            try:
                response = httpx.get(
                    str(item.url),
                    follow_redirects=True,
                    timeout=30,
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=502,
                    detail=f"图片生成成功，但下载结果失败：{exc}",
                ) from None
            mime = response.headers.get("content-type", "image/png").split(";", 1)[0].strip()
            if not mime.startswith("image/") or not response.content:
                raise HTTPException(status_code=502, detail="图片生成返回的不是有效图片")
            if len(response.content) > 20 * 1024 * 1024:
                raise HTTPException(status_code=502, detail="生成的图片超过 20MB，无法入库")
            return self.add_generated(
                b64_json=base64.b64encode(response.content).decode("ascii"),
                mime=mime,
                prompt=prompt,
                owner_user_id=owner_user_id,
            )
        raise HTTPException(status_code=502, detail="图片生成没有返回内容")

    def update(
        self,
        asset_id: str,
        *,
        owner_user_id: str | None = None,
        name: str | None = None,
        alt: str | None = None,
        visual_description: str | None = None,
        usage_hint: str | None = None,
        generation_prompt: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        row = self.get(asset_id, owner_user_id)
        if row is None:
            raise KeyError("asset not found")
        if name is not None:
            row.name = name.strip() or row.name
        if alt is not None:
            row.alt = alt.strip()
        if visual_description is not None:
            row.visual_description = visual_description.strip()
        if usage_hint is not None:
            row.usage_hint = usage_hint.strip()
        if generation_prompt is not None:
            row.generation_prompt = generation_prompt.strip()
        if tags is not None:
            row.tags = self._clean_tags(tags)
        if any(value is not None for value in (visual_description, alt)):
            row.description_source = "manual" if not row.description_source else row.description_source
        self.db.commit()
        self.db.refresh(row)
        return self._out(row)

    @staticmethod
    def _clean_tags(tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))[:20]

    @staticmethod
    def _out(row: MediaAsset) -> dict:
        return {
            "id": row.id, "name": row.name, "alt": row.alt,
            "visualDescription": row.visual_description,
            "usageHint": row.usage_hint,
            "generationPrompt": row.generation_prompt,
            "tags": row.tags or [],
            "descriptionSource": row.description_source,
            "mime": row.mime, "source": row.source, "origin": row.origin,
            "createdAt": row.created_at.isoformat(),
        }
