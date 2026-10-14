"""Audience Analyst 节点：基于产品画像分析目标受众。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import AUDIENCE_ANALYST_SYSTEM, AUDIENCE_ANALYST_USER


def audience_analyst(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在分析目标受众…")
    user_prompt = AUDIENCE_ANALYST_USER.format(
        profile_json=json.dumps(state.get("product_profile", {}), ensure_ascii=False),
        user_json=json.dumps(state.get("user_input", {}), ensure_ascii=False),
    )
    audience = ctx.llm.complete_json(AUDIENCE_ANALYST_SYSTEM, user_prompt)
    return {"audience_profile": audience, "current_step": "strategy_planner"}
