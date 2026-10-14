"""LangGraph 共享状态定义。"""

import operator
from typing import Annotated, TypedDict


class TweetWorkflowState(TypedDict, total=False):
    """工作流各节点共享的状态。

    errors 使用 Annotated + operator.add 实现 LangGraph 归并累加；
    其余键由各节点直接覆盖写入。
    """

    run_id: str
    project_id: str
    user_input: dict
    product_profile: dict
    audience_profile: dict
    strategy: dict
    candidates: list[dict]
    critiques: dict
    safety_report: dict
    platform_variants: list[dict]
    current_step: str
    errors: Annotated[list[str], operator.add]
    iteration_count: int
