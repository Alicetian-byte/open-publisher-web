"""Formatter 节点：把通过的候选推文格式化为各平台最终版本。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import FORMATTER_SYSTEM, FORMATTER_USER


def formatter(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在生成平台版本…")
    platforms = state.get("user_input", {}).get("platforms") or ["twitter"]
    user_prompt = FORMATTER_USER.format(
        candidates_json=json.dumps(state.get("candidates", []), ensure_ascii=False),
        safety_json=json.dumps(state.get("safety_report", {}), ensure_ascii=False),
        platforms_json=json.dumps(platforms, ensure_ascii=False),
    )
    data = ctx.llm.complete_json(FORMATTER_SYSTEM, user_prompt)
    variants = data.get("variants")
    if not isinstance(variants, list) or not variants:
        variants = []
    return {"platform_variants": variants, "current_step": "done"}
