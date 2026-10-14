"""LangGraph 工作流图编排。

流程：
START → product_analyst → audience_analyst → strategy_planner → copywriter
      → critic → (gate) ─┬─ 通过/达到迭代上限 → safety_checker → formatter → END
                         └─ 未通过 → rewriter → critic（循环，最多 max_iterations 轮）
"""

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    NodeContext,
    StopWorkflowError,
    audience_analyst,
    copywriter,
    critic,
    formatter,
    product_analyst,
    rewriter,
    safety_checker,
    strategy_planner,
)
from app.agents.state import TweetWorkflowState

__all__ = ["build_workflow_graph", "critic_gate"]


def critic_gate(state: TweetWorkflowState) -> str:
    """Critic 之后的条件边：达标或迭代次数用尽则进入安全检查。"""
    critiques = state.get("critiques") or {}
    iteration = int(state.get("iteration_count", 0))
    max_iterations = int(state.get("_max_iterations", 3))
    if critiques.get("pass", False) or iteration >= max_iterations:
        return "safety_checker"
    return "rewriter"


def build_workflow_graph(llm, events=None) -> object:
    """构建可 invoke/stream 的编译图。

    llm: 实现 complete_json 的客户端（真实 LLMClient 或测试 FakeLLM）。
    events: 可选 RunEventPublisher，节点通过它发进度与检查取消。
    """
    ctx = NodeContext(llm=llm, events=events)

    graph = StateGraph(TweetWorkflowState)
    graph.add_node("product_analyst", lambda s: product_analyst(s, ctx))
    graph.add_node("audience_analyst", lambda s: audience_analyst(s, ctx))
    graph.add_node("strategy_planner", lambda s: strategy_planner(s, ctx))
    graph.add_node("copywriter", lambda s: copywriter(s, ctx))
    graph.add_node("critic", lambda s: critic(s, ctx))
    graph.add_node("rewriter", lambda s: rewriter(s, ctx))
    graph.add_node("safety_checker", lambda s: safety_checker(s, ctx))
    graph.add_node("formatter", lambda s: formatter(s, ctx))

    graph.add_edge(START, "product_analyst")
    graph.add_edge("product_analyst", "audience_analyst")
    graph.add_edge("audience_analyst", "strategy_planner")
    graph.add_edge("strategy_planner", "copywriter")
    graph.add_edge("copywriter", "critic")
    graph.add_conditional_edges(
        "critic",
        critic_gate,
        {"rewriter": "rewriter", "safety_checker": "safety_checker"},
    )
    graph.add_edge("rewriter", "critic")
    graph.add_edge("safety_checker", "formatter")
    graph.add_edge("formatter", END)
    return graph.compile()
