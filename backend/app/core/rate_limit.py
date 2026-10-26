"""进程内滑动窗口限流：登录/注册接口防爆破。

单实例轻量方案：按客户端 IP 维护时间戳环形队列，窗口内超限返回 429。
- 生产多实例部署时应换 Redis 令牌桶（key 相同即可平滑替换）；
- 处于反向代理后时，优先读 X-Forwarded-For 首个地址。
阈值通过环境变量 LOGIN_RATE_LIMIT_MAX / LOGIN_RATE_LIMIT_WINDOW_SECONDS 配置。
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import get_settings

_attempts: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_auth(request: Request) -> None:
    settings = get_settings()
    key = client_ip(request)
    now = time.monotonic()
    window = settings.login_rate_limit_window_seconds
    queue = _attempts[key]
    while queue and now - queue[0] > window:
        queue.popleft()
    if len(queue) >= settings.login_rate_limit_max:
        raise HTTPException(
            status_code=429,
            detail=f"尝试过于频繁，请约 {max(1, int(window // 60))} 分钟后再试",
        )
    queue.append(now)
    # 防止长期运行下 key 无界增长：超大体量时清理孤儿队列
    if len(_attempts) > 10000:
        stale = [k for k, v in _attempts.items() if not v or now - v[-1] > window]
        for k in stale:
            _attempts.pop(k, None)
