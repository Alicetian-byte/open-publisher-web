from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(max_length=120)
    description: str = ""
    website_url: str | None = None
    github_url: str | None = None
    target_audience: str = ""
    selling_points: list[str] = Field(default_factory=list)
    goals: str = ""
    tone: str = "professional"
    platforms: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    website_url: str | None = None
    github_url: str | None = None
    target_audience: str | None = None
    selling_points: list[str] | None = None
    goals: str | None = None
    tone: str | None = None
    platforms: list[str] | None = None
    status: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    website_url: str | None
    github_url: str | None
    target_audience: str
    selling_points: list[Any]
    goals: str
    tone: str
    platforms: list[Any]
    status: str
    created_at: datetime
    updated_at: datetime
