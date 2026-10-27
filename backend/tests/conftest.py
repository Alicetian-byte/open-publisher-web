"""pytest 公共夹具：FakeLLM、FakeEvents、SQLite 内存库。"""

import os

from cryptography.fernet import Fernet
import pytest

# API Key 只支持数据库加密存储；测试也必须配置专用主密钥。
os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import require_admin, require_user
from app.db.base import Base
from app.main import app


@pytest.fixture(autouse=True)
def bypass_api_auth():
    """API 测试默认以普通用户/管理员身份通过路由级鉴权。"""
    app.dependency_overrides[require_user] = lambda: type("TestUser", (), {"id": "u-test", "role": "user"})()
    app.dependency_overrides[require_admin] = lambda: type("TestAdmin", (), {"id": "u-admin", "role": "admin"})()
    yield
    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(require_admin, None)


class FakeLLM:
    """按 system prompt 中的 [NodeName] 标记返回脚本化 JSON。"""

    def __init__(self, responses: dict[str, dict] | None = None, default: dict | None = None):
        self.responses = responses or {}
        self.default = default if default is not None else {}
        self.call_count = 0
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str, *, temperature: float = 0.7) -> dict:
        self.call_count += 1
        for marker, value in self.responses.items():
            if f"[{marker}]" in system:
                self.calls.append(marker)
                return value
        self.calls.append("__default__")
        return self.default


class FakeEvents:
    """无 Redis 的事件发布替身，记录调用供断言。"""

    def __init__(self) -> None:
        self.published: list[dict] = []
        self.statuses: list[str] = []

    def publish(self, event_type: str, **kwargs) -> None:
        self.published.append({"eventType": event_type, **kwargs})

    def set_status(self, status: str, current_node: str | None = None) -> None:
        self.statuses.append(status)

    def request_stop(self) -> None:
        self.published.append({"eventType": "stop.requested"})

    def is_stop_requested(self) -> bool:
        return False


@pytest.fixture()
def db_session_factory():
    """SQLite 内存库 + 全部建表。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def fake_llm_responses() -> dict:
    """覆盖全链路 8 个节点的脚本化响应。"""
    return {
        "Product Analyst": {
            "summary": "面向独立开发者的截图转 API 工具",
            "core_features": ["截图识别", "一键生成接口"],
            "evidence": ["支持 20+ 语言"],
            "differentiators": ["无需注册"],
            "cautions": ["不要夸大识别率"],
        },
        "Audience Analyst": {
            "primary_segment": {
                "name": "独立开发者",
                "pain_points": ["写接口文档耗时"],
                "motivation": "快速出 MVP",
            },
            "secondary_segments": [],
            "language_style": "轻松技术流",
            "hook_preferences": ["效率对比"],
        },
        "Strategy Planner": {
            "angles": [
                {"name": "痛点开场", "hook_type": "question", "cta": "试用链接", "rationale": "直击痛点"},
                {"name": "功能展示", "hook_type": "demo", "cta": "看演示", "rationale": "直观"},
            ],
            "recommended_count": 2,
        },
        "Copywriter": {
            "candidates": [
                {
                    "id": "c1",
                    "angle": "痛点开场",
                    "platform": "twitter",
                    "tone": "professional",
                    "content": "还在手写接口文档？截图丢进来，API 直接生成。",
                    "hashtags": ["#buildinpublic"],
                    "estimated_chars": 30,
                },
                {
                    "id": "c2",
                    "angle": "功能展示",
                    "platform": "twitter",
                    "tone": "casual",
                    "content": "演示：一张截图到可用 API 只需 10 秒。",
                    "hashtags": ["#devtools"],
                    "estimated_chars": 25,
                },
            ]
        },
        "Critic": {
            "reviews": [
                {
                    "candidate_id": "c1",
                    "scores": {"clarity": 85, "appeal": 88, "relevance": 90, "cta_strength": 80},
                    "total": 85.75,
                    "issues": [],
                    "suggestions": [],
                },
                {
                    "candidate_id": "c2",
                    "scores": {"clarity": 82, "appeal": 83, "relevance": 86, "cta_strength": 78},
                    "total": 82.25,
                    "issues": [],
                    "suggestions": [],
                },
            ],
            "max_total": 85.75,
            "pass": True,
            "threshold": 80,
        },
        "Safety Checker": {
            "overall_level": "low",
            "checks": [{"candidate_id": "c1", "level": "low", "issues": []}],
        },
        "Formatter": {
            "variants": [
                {
                    "candidate_id": "c1",
                    "platform": "twitter",
                    "tone": "professional",
                    "content": "还在手写接口文档？截图丢进来，API 直接生成。",
                    "hashtags": ["#buildinpublic"],
                    "score": 85.75,
                    "risk_level": "low",
                },
                {
                    "candidate_id": "c2",
                    "platform": "twitter",
                    "tone": "casual",
                    "content": "演示：一张截图到可用 API 只需 10 秒。",
                    "hashtags": ["#devtools"],
                    "score": 82.25,
                    "risk_level": "low",
                },
            ]
        },
    }
