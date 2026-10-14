"""Product Analyst 节点：理解产品资料，输出产品画像。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import PRODUCT_ANALYST_SYSTEM, PRODUCT_ANALYST_USER


def product_analyst(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在理解产品资料…")
    user_prompt = PRODUCT_ANALYST_USER.format(
        input_json=json.dumps(state.get("user_input", {}), ensure_ascii=False)
    )
    profile = ctx.llm.complete_json(PRODUCT_ANALYST_SYSTEM, user_prompt)
    return {"product_profile": profile, "current_step": "audience_analyst"}
