"""文章与发布 API 的请求模型（对齐蓝本 contracts V2 语义）。"""

from pydantic import BaseModel, Field


class ArticleWriteRequest(BaseModel):
    """蓝本 ArticleWriteRequestV2：乐观并发写入。"""

    articleId: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    baseRevisionId: str | None = None
    baseContentHash: str | None = None
    title: str = Field(min_length=1, max_length=300)
    markdown: str
    reason: str = Field(default="", max_length=300)


class PublishTargetRequest(BaseModel):
    """蓝本 PublishTargetInput：dry_run / wechat_sync_draft。"""

    platform: str = Field(min_length=1, max_length=50)
    accountRef: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    deliveryMode: str = "dry_run"


class PublishPlanRequest(BaseModel):
    revisionId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=300)
    markdown: str
    targets: list[PublishTargetRequest]


class PublishApproveRequest(BaseModel):
    actorId: str = "user:web"


class PublishResolveRequest(BaseModel):
    resolution: str  # draft_exists | draft_missing
