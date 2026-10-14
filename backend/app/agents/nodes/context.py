"""Agent 节点共享上下文。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agents.events import RunEventPublisher


class StopWorkflowError(Exception):
    """用户请求停止工作流。"""


class JSONLLM(Protocol):
    """节点依赖的最小 LLM 接口，便于测试替身。"""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.7) -> dict:
        ...


@dataclass
class NodeContext:
    """节点运行上下文：LLM 客户端 + 可选事件发布器 + 设置。"""

    llm: JSONLLM
    events: RunEventPublisher | None = None
    score_threshold: int = 80
    max_iterations: int = 3
    extras: dict[str, Any] = field(default_factory=dict)

    def check_stop(self) -> None:
        if self.events is not None and self.events.is_stop_requested():
            raise StopWorkflowError(f"run stopped by user")

    def publish_progress(self, message: str, payload: dict | None = None) -> None:
        if self.events is not None:
            self.events.publish("node.progress", message=message, payload=payload or {})
