"""Copywriter 节点：按策略角度生成候选推文。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import COPYWRITER_SYSTEM, COPYWRITER_USER


def copywriter(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在撰写候选推文…")
    user_prompt = COPYWRITER_USER.format(
        strategy_json=json.dumps(state.get("strategy", {}), ensure_ascii=False),
        profile_json=json.dumps(state.get("product_profile", {}), ensure_ascii=False),
        audience_json=json.dumps(state.get("audience_profile", {}), ensure_ascii=False),
    )
    data = ctx.llm.complete_json(COPYWRITER_SYSTEM, user_prompt)
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        candidates = []
    return {"candidates": candidates, "current_step": "critic"}
