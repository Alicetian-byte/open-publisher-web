"""推文版本相关 DTO。"""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.run import RevisionOut


class RevisionCreateRequest(BaseModel):
    """用户编辑保存为新版本。"""

    content: str = Field(min_length=1)
    platform: str | None = None
    tone: str | None = None


class RevisionOptimizeRequest(BaseModel):
    """AI 一键优化的方向。"""

    direction: str = Field(default="shorter")
    model_config = ConfigDict(json_schema_extra={"example": {"direction": "shorter"}})


__all__ = ["RevisionCreateRequest", "RevisionOptimizeRequest", "RevisionOut"]
