"""Mock OpenAI 兼容服务器：按 system prompt 的 [NodeName] 标记返回脚本化响应。

用途：无真实 API Key 时的端到端验证与演示（docker-compose.mock.yml）。
只依赖标准库，监听 8001。
"""

import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

PORT = 8001

# 与 tests/conftest.py 的脚本化响应同构；按 system prompt 的 [Marker] 分发
RESPONSES: dict[str, dict] = {
    "Product Analyst": {
        "summary": "面向独立开发者的截图转 API 工具（mock）",
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

# 无 Marker 匹配时（如一键优化）走通用响应
DEFAULT_RESPONSE: dict = {
    "content": "（mock 优化）更精简的推文：截图丢进来，API 直接生成。",
    "notes": "mock 优化，保留核心卖点",
}


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if not self.path.endswith("/chat/completions"):
            self._send(404, {"error": {"message": f"unknown path {self.path}"}})
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages") or []
        system = next(
            (m.get("content", "") for m in messages if m.get("role") == "system"),
            "",
        )

        matched = None
        for marker, value in RESPONSES.items():
            if f"[{marker}]" in system:
                matched = value
                break
        if matched is None:
            matched = DEFAULT_RESPONSE

        time.sleep(0.2)  # 模拟一点延迟，让 SSE 可感知
        self._send(
            200,
            {
                "id": f"chatcmpl-{uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", "mock"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(matched, ensure_ascii=False),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # 静默访问日志
        pass


if __name__ == "__main__":
    print(
        f"mock llm server listening on :{PORT} "
        f"({datetime.now(timezone.utc).isoformat()})",
        flush=True,
    )
    HTTPServer(("0.0.0.0", PORT), MockHandler).serve_forever()
