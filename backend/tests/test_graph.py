"""LangGraph 图编排测试：循环收敛与条件边。"""

from app.agents.graph import build_workflow_graph, critic_gate
from tests.conftest import FakeLLM


def test_critic_gate_pass():
    assert critic_gate({"critiques": {"pass": True}, "iteration_count": 0}) == "safety_checker"


def test_critic_gate_fail_goes_rewriter():
    assert critic_gate({"critiques": {"pass": False}, "iteration_count": 0}) == "rewriter"


def test_critic_gate_max_iterations():
    state = {"critiques": {"pass": False}, "iteration_count": 3, "_max_iterations": 3}
    assert critic_gate(state) == "safety_checker"


def test_full_graph_reaches_end_when_pass(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    graph = build_workflow_graph(fake)
    final = graph.invoke(
        {
            "run_id": "r1",
            "project_id": "p1",
            "user_input": {"project": {"name": "Shot2API"}, "extra": {}},
            "errors": [],
            "iteration_count": 0,
            "_max_iterations": 3,
        },
        config={"recursion_limit": 30},
    )
    assert final["platform_variants"], "应产出平台版本"
    assert final["safety_report"]["overall_level"] == "low"
    # 通过路径：product → audience → strategy → copy → critic → safety → formatter = 7 次
    assert fake.call_count == 7


def test_full_graph_loop_bounded_when_fail(fake_llm_responses):
    """critic 永远不通过时，最多迭代 max_iterations 轮后仍能到达终点。"""
    responses = dict(fake_llm_responses)
    responses["Critic"] = {
        "reviews": [
            {
                "candidate_id": "c1",
                "scores": {"clarity": 50, "appeal": 50, "relevance": 50, "cta_strength": 50},
                "total": 50,
                "issues": ["太平淡"],
                "suggestions": ["加强钩子"],
            }
        ],
        "max_total": 50,
        "pass": False,
        "threshold": 80,
    }
    fake = FakeLLM(responses)
    graph = build_workflow_graph(fake)
    final = graph.invoke(
        {
            "run_id": "r1",
            "project_id": "p1",
            "user_input": {"project": {"name": "Shot2API"}, "extra": {}},
            "errors": [],
            "iteration_count": 0,
            "_max_iterations": 3,
        },
        config={"recursion_limit": 40},
    )
    assert final["iteration_count"] == 3, "应正好迭代 3 轮后跳出"
    assert final["platform_variants"], "迭代耗尽仍应产出平台版本"
    # 7 个基础调用（含首轮 critic）+ 3 轮 (rewriter+critic) = 13 次
    assert fake.call_count == 13

