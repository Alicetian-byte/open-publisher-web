"""Safety Checker 节点：夸大宣传/敏感词/事实依据等合规检查。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import SAFETY_CHECKER_SYSTEM, SAFETY_CHECKER_USER


def safety_checker(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    ctx.publish_progress("正在进行风险与合规检查…")
    user_prompt = SAFETY_CHECKER_USER.format(
        candidates_json=json.dumps(state.get("candidates", []), ensure_ascii=False),
        profile_json=json.dumps(state.get("product_profile", {}), ensure_ascii=False),
    )
    report = ctx.llm.complete_json(SAFETY_CHECKER_SYSTEM, user_prompt)
    report.setdefault("overall_level", "low")
    report.setdefault("checks", [])
    return {"safety_report": report, "current_step": "formatter"}
