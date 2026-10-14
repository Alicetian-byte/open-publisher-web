"""运行相关 Pydantic DTO。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunCreateRequest(BaseModel):
    """可选的补充输入（如本次指定的平台/语气）。"""

    input: dict[str, Any] = {}


class RunCreatedResponse(BaseModel):
    id: str
    project_id: str
    status: str


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    artifact_type: str
    title: str | None
    content_json: dict[str, Any]
    created_at: datetime


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    run_id: str | None
    content: str
    platform: str | None
    tone: str | None
    score: float | None
    risk_level: str
    version: int
    is_final: bool
    source: str
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    current_node: str | None
    error_message: str | None
    llm_calls: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class RunDetailResponse(RunOut):
    artifacts: list[ArtifactOut] = []
    revisions: list[RevisionOut] = []
