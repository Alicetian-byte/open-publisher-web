"""OpenAI 兼容聊天客户端封装。

所有节点只依赖 complete_json 接口，方便测试时用 FakeLLM 替换。
密钥一律来自环境变量（Settings.llm_api_key），不落仓库。
"""

import json
import re

from openai import OpenAI

from app.core.config import get_settings


class LLMError(Exception):
    """LLM 调用或 JSON 解析失败。"""


def parse_json_dict(text: str) -> dict:
    """尽力把模型输出解析为 dict；容忍 markdown 代码块包裹。"""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM 输出不是合法 JSON：{cleaned[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"LLM 输出应为 JSON 对象，实际为 {type(data).__name__}")
    return data


class LLMClient:
    """OpenAI 兼容 chat completions 客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.llm_api_key
        self._base_url = base_url if base_url is not None else settings.llm_base_url
        self.model = model if model is not None else settings.llm_model
        self.timeout_seconds = settings.llm_timeout_seconds
        self.call_count = 0
        self._client = OpenAI(
            api_key=self._api_key or "sk-not-configured",
            base_url=self._base_url,
            timeout=self.timeout_seconds,
        )

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - 统一转为 LLMError
            raise LLMError(f"LLM 调用失败：{exc}") from exc
        self.call_count += 1
        return response.choices[0].message.content or ""

    def complete_json(
        self, system: str, user: str, *, temperature: float = 0.7
    ) -> dict:
        text = self.complete(system, user, json_mode=True, temperature=temperature)
        return parse_json_dict(text)
