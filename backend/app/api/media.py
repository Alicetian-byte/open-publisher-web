"""素材库 API：列表 / 上传 / 生成 / 删除 / 原始内容。"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.db.session import get_db
from app.models.user import AppUser
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


class MediaUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    mime: str = Field(min_length=1, max_length=100)
    dataUrl: str = Field(min_length=1)
    alt: str = Field(default="", max_length=500)
    usageHint: str = Field(default="", max_length=500)
    visualDescription: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class MediaUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    alt: str | None = Field(default=None, max_length=500)
    visualDescription: str | None = Field(default=None, max_length=2000)
    usageHint: str | None = Field(default=None, max_length=500)
    generationPrompt: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = Field(default=None, max_length=20)


class MediaGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    size: str = "1024x1024"


@router.get("")
def list_media(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
    search: str | None = Query(default=None, max_length=200),
    origin: str | None = Query(default=None, pattern="^(upload|generated)$"),
    tag: str | None = Query(default=None, max_length=50),
    sort: str = Query(default="created_desc", pattern="^(created_desc|created_asc|name_asc|name_desc)$"),
):
    return {
        "assets": MediaService(db).list(
            owner_user_id=user.id,
            search=search, origin=origin, tag=tag, sort=sort,
        )
    }


@router.post("", status_code=201)
def upload_media(
    body: MediaUploadRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    try:
        return MediaService(db).add_upload(
            name=body.name, mime=body.mime, data_url=body.dataUrl,
            alt=body.alt, usage_hint=body.usageHint,
            visual_description=body.visualDescription, tags=body.tags,
            owner_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/generate", status_code=201)
def generate_media(
    body: MediaGenerateRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    return MediaService(db).generate(
        prompt=body.prompt, size=body.size, owner_user_id=user.id,
    )


@router.delete("/{asset_id}", status_code=204)
def delete_media(
    asset_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    try:
        MediaService(db).delete(asset_id, owner_user_id=user.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="asset not found") from None


@router.patch("/{asset_id}")
def update_media(
    asset_id: str,
    body: MediaUpdateRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    try:
        return MediaService(db).update(
            asset_id,
            owner_user_id=user.id,
            name=body.name, alt=body.alt,
            visual_description=body.visualDescription,
            usage_hint=body.usageHint,
            generation_prompt=body.generationPrompt,
            tags=body.tags,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="asset not found") from None


@router.get("/{asset_id}/raw")
def raw_media(
    asset_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_user),
):
    row = MediaService(db).get(asset_id, owner_user_id=user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="asset not found")
    if row.source.startswith("data:"):
        header, b64 = row.source.split(",", 1)
        import base64

        data = base64.b64decode(b64)
        return Response(content=data, media_type=row.mime)
    raise HTTPException(status_code=404, detail="remote asset has no local raw content")
