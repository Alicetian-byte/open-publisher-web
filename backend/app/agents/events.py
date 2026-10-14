"""Redis 运行事件通道。

- 事件列表：run:{run_id}:events（List，JSON 行）
- 运行状态：run:{run_id}:status（Hash：status / current_node）
- 取消信号：run:{run_id}:cancel（String）
所有 key 1 小时过期，SSE 端点轮询事件列表推送给前端。
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import redis

from app.core.config import get_settings


class RunEventPublisher:
    """向 Redis 写运行事件；读取方法供 SSE 端点使用。"""

    def __init__(self, run_id: str, redis_url: str | None = None) -> None:
        self.run_id = run_id
        url = redis_url or get_settings().redis_url
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._events_key = f"run:{run_id}:events"
        self._status_key = f"run:{run_id}:status"
        self._cancel_key = f"run:{run_id}:cancel"
        self._ttl = 3600

    # ---------- 写 ----------
    def publish(
        self,
        event_type: str,
        *,
        node_id: str | None = None,
        payload: dict | None = None,
        message: str | None = None,
    ) -> None:
        event = {
            "id": uuid4().hex,
            "eventType": event_type,
            "nodeId": node_id,
            "message": message,
            "payload": payload or {},
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        self._redis.rpush(self._events_key, json.dumps(event, ensure_ascii=False))
        self._redis.expire(self._events_key, self._ttl)

    def set_status(self, status: str, current_node: str | None = None) -> None:
        mapping: dict[str, str] = {"status": status}
        if current_node is not None:
            mapping["current_node"] = current_node
        self._redis.hset(self._status_key, mapping=mapping)
        self._redis.expire(self._status_key, self._ttl)

    def request_stop(self) -> None:
        self._redis.set(self._cancel_key, "1", ex=self._ttl)

    # ---------- 读（SSE 用） ----------
    def read_from(self, index: int) -> list[dict]:
        raw = self._redis.lrange(self._events_key, index, -1)
        return [json.loads(item) for item in raw]

    def current_status(self) -> str | None:
        value = self._redis.hget(self._status_key, "status")
        return str(value) if value else None

    # ---------- 节点内取消检查 ----------
    def is_stop_requested(self) -> bool:
        return self._redis.exists(self._cancel_key) == 1
