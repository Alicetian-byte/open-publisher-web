"""Strategy Planner 节点：制定推文切入角度与 CTA 策略。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import STRATEGY_PLANNER_SYSTEM, STRATEGY_PLANNER_USER


def strategy_planner(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在规划推文策略…")
    user_prompt = STRATEGY_PLANNER_USER.format(
        profile_json=json.dumps(state.get("product_profile", {}), ensure_ascii=False),
        audience_json=json.dumps(state.get("audience_profile", {}), ensure_ascii=False),
        user_json=json.dumps(state.get("user_input", {}), ensure_ascii=False),
    )
    strategy = ctx.llm.complete_json(STRATEGY_PLANNER_SYSTEM, user_prompt)
    return {"strategy": strategy, "current_step": "copywriter"}
