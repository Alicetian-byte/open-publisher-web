"""Critic 节点：逐条评审候选推文并决定是否进入改写循环。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import CRITIC_SYSTEM, CRITIC_USER


def critic(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在评审候选推文质量…")
    system = CRITIC_SYSTEM.format(threshold=ctx.score_threshold)
    user_prompt = CRITIC_USER.format(
        candidates_json=json.dumps(state.get("candidates", []), ensure_ascii=False),
        profile_json=json.dumps(state.get("product_profile", {}), ensure_ascii=False),
    )
    critiques = ctx.llm.complete_json(system, user_prompt)
    critiques.setdefault("threshold", ctx.score_threshold)
    critiques.setdefault("pass", False)
    return {"critiques": critiques, "current_step": "critic_gate"}
