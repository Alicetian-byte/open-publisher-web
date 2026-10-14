"""Rewriter 节点：按评审意见优化低分候选。"""

import json

from app.agents.nodes.context import NodeContext
from app.agents.prompts import REWRITER_SYSTEM, REWRITER_USER


def rewriter(state: dict, ctx: NodeContext) -> dict:
    ctx.check_stop()
    iteration = int(state.get("iteration_count", 0)) + 1
    ctx.publish_progress(f"第 {iteration} 轮优化低分候选…")
    user_prompt = REWRITER_USER.format(
        candidates_json=json.dumps(state.get("candidates", []), ensure_ascii=False),
        critiques_json=json.dumps(state.get("critiques", {}), ensure_ascii=False),
        iteration=iteration,
    )
    data = ctx.llm.complete_json(REWRITER_SYSTEM, user_prompt)
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        candidates = state.get("candidates", [])
    return {
        "candidates": candidates,
        "iteration_count": iteration,
        "current_step": "critic",
    }
