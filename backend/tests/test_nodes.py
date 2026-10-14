"""节点级单元测试。"""

from app.agents.events import RunEventPublisher  # noqa: F401  类型引用
from app.agents.nodes import (
    NodeContext,
    copywriter,
    critic,
    formatter,
    product_analyst,
    safety_checker,
)
from tests.conftest import FakeLLM


def _ctx(fake: FakeLLM) -> NodeContext:
    return NodeContext(llm=fake)


def test_product_analyst_returns_profile(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    state = {"user_input": {"project": {"name": "Shot2API"}}}
    updates = product_analyst(state, _ctx(fake))
    assert updates["product_profile"]["summary"].startswith("面向独立开发者")
    assert updates["current_step"] == "audience_analyst"
    assert fake.call_count == 1


def test_copywriter_returns_candidates(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    state = {"strategy": {"angles": []}, "product_profile": {}, "audience_profile": {}}
    updates = copywriter(state, _ctx(fake))
    assert len(updates["candidates"]) == 2
    assert updates["candidates"][0]["id"] == "c1"


def test_critic_uses_threshold(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    ctx = NodeContext(llm=fake, score_threshold=80)
    state = {"candidates": [{"id": "c1", "content": "x"}], "product_profile": {}}
    updates = critic(state, ctx)
    assert updates["critiques"]["pass"] is True
    assert updates["critiques"]["threshold"] == 80


def test_safety_checker_defaults(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    state = {"candidates": [], "product_profile": {}}
    updates = safety_checker(state, _ctx(fake))
    assert updates["safety_report"]["overall_level"] == "low"


def test_formatter_defaults_platform(fake_llm_responses):
    fake = FakeLLM(fake_llm_responses)
    state = {"candidates": [], "safety_report": {}, "user_input": {}}
    updates = formatter(state, _ctx(fake))
    assert updates["platform_variants"][0]["platform"] == "twitter"
