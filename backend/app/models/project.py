import uuid

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    """产品项目：一次推文创作工作的顶层对象。"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_audience: Mapped[str] = mapped_column(Text, default="")
    selling_points: Mapped[list] = mapped_column(JSON, default=list)
    goals: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(String(50), default="professional")
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
